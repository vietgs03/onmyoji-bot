//! perception.rs - port tu scripts/perception.py (phan state-hash + loading).
//!
//! Cac ham o day phai khop **fixed-point** voi OpenCV/Python o muc bit (da kiem
//! chung: max hamming = 2 tren 105 goldens, nguong fuzzy CANON_THR=12 => an toan).
//!
//! Cong thuc lay tu OpenCV:
//!   - BGR2GRAY: Y = (R*4899 + G*9617 + B*1868 + 8192) >> 14
//!   - resize INTER_LINEAR: fixed-point 11-bit (2048), trong so cvRound doc lap,
//!     ket hop 2 chieu roi >> 22 voi bias (1<<21).

use crate::image::Image;
use crate::md5::md5_hex;

/// Kich thuoc man hinh game chuan (client-area).
pub const W: usize = 1152;
pub const H: usize = 679;

/// Cac VUNG TINH de tinh state-hash (x0,y0,x1,y1) - khop STABLE_REGIONS ben Python.
/// Tranh vung nhan vat dong + cay sakura + chat bar.
pub const STABLE_REGIONS: [(usize, usize, usize, usize); 4] = [
    (0, 55, 1152, 95),    // currency bar tren
    (980, 130, 1130, 560), // cot icon modes phai
    (0, 600, 1152, 660),  // footer text row
    (0, 95, 280, 600),    // ria trai
];

const PER_REGION: usize = 4; // moi vung hash thanh luoi (PER_REGION+1) x PER_REGION

/// Grayscale 1 pixel theo fixed-point cua OpenCV (BGR2GRAY). Tra 0..255.
#[inline]
fn gray_px(r: u8, g: u8, b: u8) -> i32 {
    (r as i32 * 4899 + g as i32 * 9617 + b as i32 * 1868 + 8192) >> 14
}

/// He so resize INTER_LINEAR cho 1 chieu: tra (chi so nguon, alpha0, alpha1) fixed-point.
/// alpha0+alpha1 ~ 2048. Tinh nhu OpenCV: dung f32 cho frac roi cvRound (lam tron
/// half-to-even) tung alpha doc lap.
fn linear_coeffs(src_size: usize, dst_size: usize) -> Vec<(usize, i32, i32)> {
    const SCALE: f32 = 2048.0;
    let scale = src_size as f64 / dst_size as f64;
    let mut out = Vec::with_capacity(dst_size);
    for d in 0..dst_size {
        // dung f32 de khop OpenCV (no tinh fx bang float)
        let fx = ((d as f64 + 0.5) * scale - 0.5) as f32;
        let mut sx = fx.floor() as i32;
        let mut frac = fx - sx as f32;
        if sx < 0 {
            sx = 0;
            frac = 0.0;
        }
        if sx >= src_size as i32 - 1 {
            sx = src_size as i32 - 1;
            frac = 0.0;
        }
        let a0 = cv_round((1.0 - frac) * SCALE);
        let a1 = cv_round(frac * SCALE);
        out.push((sx as usize, a0, a1));
    }
    out
}

/// cvRound: lam tron half-to-even (banker's rounding), khop `cvRound` cua OpenCV.
#[inline]
fn cv_round(x: f32) -> i32 {
    let r = x.round();
    // f32::round la half-away-from-zero; chinh ve half-to-even cho khop cvRound.
    if (x - x.floor() - 0.5).abs() < f32::EPSILON {
        let down = x.floor() as i32;
        if down % 2 == 0 {
            down
        } else {
            down + 1
        }
    } else {
        r as i32
    }
}

/// Resize 1 vung gray (src: mang i32 wxh) ve (dst_w x dst_h) bang bilinear fixed-point.
/// Tra mang i32 (0..255) kich thuoc dst_w*dst_h, row-major.
fn resize_linear(src: &[i32], src_w: usize, src_h: usize, dst_w: usize, dst_h: usize) -> Vec<i32> {
    let xc = linear_coeffs(src_w, dst_w);
    let yc = linear_coeffs(src_h, dst_h);
    let mut out = vec![0i32; dst_w * dst_h];
    for (dy, &(sy0, ya0, ya1)) in yc.iter().enumerate() {
        let sy1 = (sy0 + 1).min(src_h - 1);
        let row0 = &src[sy0 * src_w..sy0 * src_w + src_w];
        let row1 = &src[sy1 * src_w..sy1 * src_w + src_w];
        for (dx, &(sx0, xa0, xa1)) in xc.iter().enumerate() {
            let sx1 = (sx0 + 1).min(src_w - 1);
            // ngang truoc (theo OpenCV): H = s0*a0 + s1*a1  (don vi 2048)
            let h0 = row0[sx0] as i64 * xa0 as i64 + row0[sx1] as i64 * xa1 as i64;
            let h1 = row1[sx0] as i64 * xa0 as i64 + row1[sx1] as i64 * xa1 as i64;
            // doc + bias roi >> 22
            let v = (h0 * ya0 as i64 + h1 * ya1 as i64 + (1 << 21)) >> 22;
            out[dy * dst_w + dx] = v.clamp(0, 255) as i32;
        }
    }
    out
}

/// Crop vung [x0,y0,x1,y1) cua anh -> mang gray i32 (row-major).
fn crop_gray(img: &Image, x0: usize, y0: usize, x1: usize, y1: usize) -> (Vec<i32>, usize, usize) {
    let cw = x1 - x0;
    let ch = y1 - y0;
    let mut g = vec![0i32; cw * ch];
    for yy in 0..ch {
        for xx in 0..cw {
            let (r, gr, b) = img.rgb(x0 + xx, y0 + yy);
            g[yy * cw + xx] = gray_px(r, gr, b);
        }
    }
    (g, cw, ch)
}

/// dHash on dinh theo cac VUNG TINH (khop perception.dhash). Tra chuoi '0'/'1' do dai
/// = so_vung * PER_REGION * PER_REGION (= 4*4*4 = 64). None neu anh nho hon W,H.
pub fn dhash(img: &Image) -> Option<String> {
    if img.width < W || img.height < H {
        return None;
    }
    let mut bits = String::with_capacity(STABLE_REGIONS.len() * PER_REGION * PER_REGION);
    for &(x0, y0, x1, y1) in STABLE_REGIONS.iter() {
        let (g, cw, ch) = crop_gray(img, x0, y0, x1, y1);
        if cw == 0 || ch == 0 {
            return None;
        }
        let small = resize_linear(&g, cw, ch, PER_REGION + 1, PER_REGION);
        // diff: cot[j+1] > cot[j] tren tung hang
        for row in 0..PER_REGION {
            for col in 0..PER_REGION {
                let left = small[row * (PER_REGION + 1) + col];
                let right = small[row * (PER_REGION + 1) + col + 1];
                bits.push(if right > left { '1' } else { '0' });
            }
        }
    }
    Some(bits)
}

/// state_id = md5(dhash)[:10], khop perception.state_id.
pub fn state_id(dhash_bits: &str) -> String {
    md5_hex(dhash_bits.as_bytes())[..10].to_string()
}

/// Khoang cach Hamming giua 2 chuoi bit (do dai bang nhau).
pub fn hamming(a: &str, b: &str) -> usize {
    a.bytes().zip(b.bytes()).filter(|(x, y)| x != y).count()
}

/// is_loading: man hinh loading thuong rat toi. True neu >dark_ratio pixel gray < dark_thr.
/// Khop perception.is_loading (dark_thr=45, dark_ratio=0.7).
pub fn is_loading(img: &Image) -> bool {
    is_loading_params(img, 45, 0.7)
}

pub fn is_loading_params(img: &Image, dark_thr: i32, dark_ratio: f64) -> bool {
    let total = img.width * img.height;
    if total == 0 {
        return false;
    }
    let mut dark = 0usize;
    for i in 0..total {
        let base = i * 3;
        let (r, g, b) = (
            img.data[base],
            img.data[base + 1],
            img.data[base + 2],
        );
        if gray_px(r, g, b) < dark_thr {
            dark += 1;
        }
    }
    (dark as f64 / total as f64) > dark_ratio
}

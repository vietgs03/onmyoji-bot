//! template.rs - Template matching (cv2.matchTemplate TM_CCOEFF_NORMED) cho EYE.
//!
//! Dung de nhan "landmark on dinh" (vd nut menu, chu tieu de) tai 1 vung nho
//! co dinh -> robust hon dhash full-screen voi man DONG/3D. Port faithful tu
//! OAS (RuleImage.match: crop roi_back -> matchTemplate -> max > threshold).
//!
//! TM_CCOEFF_NORMED da kenh (RGB): tru mean THEO TUNG KENH, tu so/mau so gop
//! ca 3 kenh. Cong thuc tai 1 vi tri (x,y):
//!   num = sum_c sum_p (T_c[p]-mean_c(T)) * (W_c[p]-mean_c(W))
//!   den = sqrt( sum_c sum_p (T_c[p]-mean_c(T))^2 * sum_c sum_p (W_c[p]-mean_c(W))^2 )
//!   score = num/den   (den==0 -> 0)
//! Da kiem khop cv2 toi 5 chu so thap phan.

use crate::image::Image;

/// Ket qua match: vi tri tot nhat (goc trai-tren cua template trong anh GOC)
/// + diem TM_CCOEFF_NORMED [-1, 1].
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MatchResult {
    pub x: usize,
    pub y: usize,
    pub score: f64,
}

/// Vung chu nhat (goc trai-tren + kich thuoc), don vi pixel anh GOC.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Roi {
    pub x: usize,
    pub y: usize,
    pub w: usize,
    pub h: usize,
}

impl Roi {
    /// Cat ROI ve trong bien anh (tranh tran). Tra ROI da kep.
    pub fn clamp(&self, img_w: usize, img_h: usize) -> Roi {
        let x = self.x.min(img_w.saturating_sub(1));
        let y = self.y.min(img_h.saturating_sub(1));
        let w = self.w.min(img_w - x).max(1);
        let h = self.h.min(img_h - y).max(1);
        Roi { x, y, w, h }
    }
}

/// Tinh tong + tong binh phuong cua moi kenh trong template (de tru mean 1 lan).
struct TemplStats {
    /// T_c[p] - mean_c(T), luu phang theo (row-major, 3 kenh xen ke nhu Image).
    centered: Vec<f64>,
    /// sum_c sum_p (T_c[p]-mean_c)^2
    ss: f64,
    w: usize,
    h: usize,
}

fn templ_stats(tmpl: &Image) -> TemplStats {
    let (w, h) = (tmpl.width, tmpl.height);
    let n = (w * h) as f64;
    // mean tung kenh
    let mut mean = [0f64; 3];
    for px in tmpl.data.chunks_exact(3) {
        mean[0] += px[0] as f64;
        mean[1] += px[1] as f64;
        mean[2] += px[2] as f64;
    }
    mean[0] /= n;
    mean[1] /= n;
    mean[2] /= n;
    let mut centered = Vec::with_capacity(w * h * 3);
    let mut ss = 0f64;
    for px in tmpl.data.chunks_exact(3) {
        for c in 0..3 {
            let v = px[c] as f64 - mean[c];
            centered.push(v);
            ss += v * v;
        }
    }
    TemplStats { centered, ss, w, h }
}

/// Tong vung [lx,lx+w) x [ly,ly+h) cua kenh c qua integral image (co vien 0).
#[inline]
fn box_sum(ii: &[f64], stride: usize, lx: usize, ly: usize, w: usize, h: usize, c: usize) -> f64 {
    let idx = |x: usize, y: usize| (y * stride + x) * 3 + c;
    let a = ii[idx(lx, ly)];
    let b = ii[idx(lx + w, ly)];
    let cc = ii[idx(lx, ly + h)];
    let d = ii[idx(lx + w, ly + h)];
    d - b - cc + a
}

/// Xay integral image (sum, sumsq) cho ROI, moi kenh rieng. Kich thuoc
/// (rw+1)*(rh+1)*3 (co vien 0 o hang/cot dau). Tra (ii_sum, ii_sq, stride=rw+1).
fn build_integrals(img: &Image, roi: Roi) -> (Vec<f64>, Vec<f64>, usize) {
    let (iw, rw, rh) = (img.width, roi.w, roi.h);
    let stride = rw + 1;
    let mut ii_sum = vec![0f64; stride * (rh + 1) * 3];
    let mut ii_sq = vec![0f64; stride * (rh + 1) * 3];
    for ry in 0..rh {
        let mut run = [0f64; 3];
        let mut run_sq = [0f64; 3];
        let src_row = ((roi.y + ry) * iw + roi.x) * 3;
        for rx in 0..rw {
            let p = src_row + rx * 3;
            for c in 0..3 {
                let v = img.data[p + c] as f64;
                run[c] += v;
                run_sq[c] += v * v;
                let up = (ry * stride + (rx + 1)) * 3 + c;
                let cur = ((ry + 1) * stride + (rx + 1)) * 3 + c;
                ii_sum[cur] = ii_sum[up] + run[c];
                ii_sq[cur] = ii_sq[up] + run_sq[c];
            }
        }
    }
    (ii_sum, ii_sq, stride)
}

/// num = sum(T_centered * W) (1 pass; mean cua W triet tieu vi sum T_centered=0).
fn numerator(img: &Image, ts: &TemplStats, ox: usize, oy: usize) -> f64 {
    let (iw, w, h) = (img.width, ts.w, ts.h);
    let mut num = 0f64;
    let mut ti = 0usize;
    for ry in 0..h {
        let row = ((oy + ry) * iw + ox) * 3;
        let slice = &img.data[row..row + w * 3];
        for px in slice.chunks_exact(3) {
            num += ts.centered[ti] * px[0] as f64;
            num += ts.centered[ti + 1] * px[1] as f64;
            num += ts.centered[ti + 2] * px[2] as f64;
            ti += 3;
        }
    }
    num
}

/// Quet template tren TOAN anh, tra vi tri + diem cao nhat.
/// None neu template lon hon anh.
pub fn match_template(img: &Image, tmpl: &Image) -> Option<MatchResult> {
    if tmpl.width == 0 || tmpl.height == 0 || tmpl.width > img.width || tmpl.height > img.height {
        return None;
    }
    match_template_roi(
        img,
        tmpl,
        Roi {
            x: 0,
            y: 0,
            w: img.width,
            h: img.height,
        },
    )
}

/// Quet template CHI trong vung `roi` cua anh. Vi tri tra ve la TUYET DOI trong
/// anh goc (da cong offset roi). Khop OAS: roi = roi_back.
///
/// Toi uu: window sum + sumsq lay tu integral image (O(1)/vi tri); chi numerator
/// (tuong quan cheo) con O(tw*th). ~3x nhanh so voi 3-pass tho. Ket qua KHOP
/// cv2 (golden max_diff ~1e-6).
pub fn match_template_roi(img: &Image, tmpl: &Image, roi: Roi) -> Option<MatchResult> {
    let roi = roi.clamp(img.width, img.height);
    if tmpl.width > roi.w || tmpl.height > roi.h {
        return None;
    }
    let ts = templ_stats(tmpl);
    let n = (ts.w * ts.h) as f64;
    let (ii_sum, ii_sq, stride) = build_integrals(img, roi);
    let max_x = roi.w - tmpl.width;
    let max_y = roi.h - tmpl.height;
    let mut best = MatchResult {
        x: roi.x,
        y: roi.y,
        score: f64::NEG_INFINITY,
    };
    for dy in 0..=max_y {
        for dx in 0..=max_x {
            // ss_w qua integral image: sumsq - sum^2/n, gop 3 kenh
            let mut ss_w = 0f64;
            for c in 0..3 {
                let s = box_sum(&ii_sum, stride, dx, dy, ts.w, ts.h, c);
                let sq = box_sum(&ii_sq, stride, dx, dy, ts.w, ts.h, c);
                ss_w += sq - s * s / n;
            }
            let den = (ts.ss * ss_w).sqrt();
            let score = if den > 0.0 {
                numerator(img, &ts, roi.x + dx, roi.y + dy) / den
            } else {
                0.0
            };
            if score > best.score {
                best = MatchResult {
                    x: roi.x + dx,
                    y: roi.y + dy,
                    score,
                };
            }
        }
    }
    Some(best)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Template = chinh 1 vung con cua anh -> score tai do phai = 1.0.
    #[test]
    fn match_chinh_no_score_1() {
        // anh 8x8 RGB gia
        let mut data = Vec::new();
        for i in 0..8 * 8 {
            let v = ((i * 7) % 256) as u8;
            data.push(v);
            data.push(v.wrapping_add(40));
            data.push(v.wrapping_add(80));
        }
        let img = Image::from_rgb(8, 8, data).unwrap();
        // cat template 3x3 tai (3,2)
        let mut td = Vec::new();
        for ry in 0..3 {
            for rx in 0..3 {
                let (r, g, b) = img.rgb(3 + rx, 2 + ry);
                td.push(r);
                td.push(g);
                td.push(b);
            }
        }
        let tmpl = Image::from_rgb(3, 3, td).unwrap();
        let m = match_template(&img, &tmpl).unwrap();
        assert_eq!((m.x, m.y), (3, 2));
        assert!((m.score - 1.0).abs() < 1e-9, "score={}", m.score);
    }

    #[test]
    fn template_lon_hon_anh_tra_none() {
        let img = Image::from_rgb(4, 4, vec![0u8; 48]).unwrap();
        let tmpl = Image::from_rgb(5, 5, vec![0u8; 75]).unwrap();
        assert!(match_template(&img, &tmpl).is_none());
    }

    #[test]
    fn roi_thu_hep_van_tim_dung() {
        // anh 12x12 voi pattern gia-ngau-nhien (LCG) -> moi cua so 3x3 duy nhat.
        let mut seed: u32 = 12345;
        let mut rnd = || {
            seed = seed.wrapping_mul(1103515245).wrapping_add(12345);
            (seed >> 16) as u8
        };
        let mut data = Vec::with_capacity(12 * 12 * 3);
        for _ in 0..12 * 12 * 3 {
            data.push(rnd());
        }
        let img = Image::from_rgb(12, 12, data).unwrap();
        // template 3x3 tai (7,6)
        let (tx, ty) = (7usize, 6usize);
        let mut td = Vec::new();
        for ry in 0..3 {
            for rx in 0..3 {
                let (r, g, b) = img.rgb(tx + rx, ty + ry);
                td.push(r);
                td.push(g);
                td.push(b);
            }
        }
        let tmpl = Image::from_rgb(3, 3, td).unwrap();
        let m = match_template_roi(&img, &tmpl, Roi { x: 4, y: 4, w: 8, h: 8 }).unwrap();
        assert_eq!((m.x, m.y), (tx, ty));
        assert!((m.score - 1.0).abs() < 1e-9);
    }
}

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

/// Tinh TM_CCOEFF_NORMED tai vi tri (ox,oy) (goc template trong anh `img`).
/// Gia dinh ox+w <= img.width, oy+h <= img.height (caller dam bao).
fn score_at(img: &Image, ts: &TemplStats, ox: usize, oy: usize) -> f64 {
    let (iw, w, h) = (img.width, ts.w, ts.h);
    let n = (w * h) as f64;
    // mean cua cua so theo tung kenh
    let mut mean = [0f64; 3];
    for ry in 0..h {
        let row = ((oy + ry) * iw + ox) * 3;
        let slice = &img.data[row..row + w * 3];
        for px in slice.chunks_exact(3) {
            mean[0] += px[0] as f64;
            mean[1] += px[1] as f64;
            mean[2] += px[2] as f64;
        }
    }
    mean[0] /= n;
    mean[1] /= n;
    mean[2] /= n;
    // num = sum centered_T * centered_W ; ss_w = sum centered_W^2
    let mut num = 0f64;
    let mut ss_w = 0f64;
    let mut ti = 0usize;
    for ry in 0..h {
        let row = ((oy + ry) * iw + ox) * 3;
        let slice = &img.data[row..row + w * 3];
        for px in slice.chunks_exact(3) {
            for c in 0..3 {
                let wv = px[c] as f64 - mean[c];
                num += ts.centered[ti] * wv;
                ss_w += wv * wv;
                ti += 1;
            }
        }
    }
    let den = (ts.ss * ss_w).sqrt();
    if den > 0.0 {
        num / den
    } else {
        0.0
    }
}

/// Quet template tren TOAN anh, tra vi tri + diem cao nhat.
/// None neu template lon hon anh.
pub fn match_template(img: &Image, tmpl: &Image) -> Option<MatchResult> {
    if tmpl.width == 0 || tmpl.height == 0 || tmpl.width > img.width || tmpl.height > img.height {
        return None;
    }
    let ts = templ_stats(tmpl);
    let max_x = img.width - tmpl.width;
    let max_y = img.height - tmpl.height;
    let mut best = MatchResult {
        x: 0,
        y: 0,
        score: f64::NEG_INFINITY,
    };
    for oy in 0..=max_y {
        for ox in 0..=max_x {
            let s = score_at(img, &ts, ox, oy);
            if s > best.score {
                best = MatchResult {
                    x: ox,
                    y: oy,
                    score: s,
                };
            }
        }
    }
    Some(best)
}

/// Quet template CHI trong vung `roi` cua anh (crop truoc -> nhanh). Vi tri tra
/// ve la TUYET DOI trong anh goc (da cong offset roi). Khop OAS: roi = roi_back.
pub fn match_template_roi(img: &Image, tmpl: &Image, roi: Roi) -> Option<MatchResult> {
    let roi = roi.clamp(img.width, img.height);
    if tmpl.width > roi.w || tmpl.height > roi.h {
        return None;
    }
    let ts = templ_stats(tmpl);
    let max_x = roi.w - tmpl.width;
    let max_y = roi.h - tmpl.height;
    let mut best = MatchResult {
        x: roi.x,
        y: roi.y,
        score: f64::NEG_INFINITY,
    };
    for dy in 0..=max_y {
        for dx in 0..=max_x {
            let s = score_at(img, &ts, roi.x + dx, roi.y + dy);
            if s > best.score {
                best = MatchResult {
                    x: roi.x + dx,
                    y: roi.y + dy,
                    score: s,
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

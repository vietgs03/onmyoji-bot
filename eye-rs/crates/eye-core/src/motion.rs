//! motion.rs - Phat hien CHUYEN DONG / kha nang DI CHUYEN cua man hinh.
//!
//! 2 muc dich cho agent vision hieu man:
//!   1. diff_ratio: 2 frame khac nhau bao nhieu (animation / da doi man).
//!   2. shift_estimate: uoc luong man da DICH CHUYEN bao nhieu (sau khi drag) ->
//!      biet man co SCROLL/DRAG duoc khong (vd list, ban do 3D parallax).
//!
//! Tat ca tren gray (value channel) de re. KHONG phu thuoc OS.

use crate::cv::{self, Mat1};
use crate::image::Image;

/// Vung chu nhat (pixel).
#[derive(Clone, Copy, Debug)]
pub struct Rect {
    pub x: usize,
    pub y: usize,
    pub w: usize,
    pub h: usize,
}

/// Ty le pixel khac nhau giua 2 frame (gray, nguong `thr`) trong vung `roi`
/// (None = toan anh). Tra 0..1. Dung de biet man co DOI / co ANIMATION khong.
pub fn diff_ratio(a: &Image, b: &Image, thr: u8, roi: Option<Rect>) -> f32 {
    if a.width != b.width || a.height != b.height {
        return 1.0; // kich thuoc khac = coi nhu khac hoan toan
    }
    let ga = cv::hsv_value(a);
    let gb = cv::hsv_value(b);
    let r = roi.unwrap_or(Rect {
        x: 0,
        y: 0,
        w: a.width,
        h: a.height,
    });
    let mut diff = 0usize;
    let mut total = 0usize;
    for y in r.y..(r.y + r.h).min(a.height) {
        for x in r.x..(r.x + r.w).min(a.width) {
            let da = ga.at(x, y) as i32 - gb.at(x, y) as i32;
            if da.unsigned_abs() as u8 > thr {
                diff += 1;
            }
            total += 1;
        }
    }
    if total == 0 {
        0.0
    } else {
        diff as f32 / total as f32
    }
}

/// Uoc luong DICH NGANG (dx) giua 2 frame trong vung `roi` bang tuong quan hang
/// gray (chieu ngang). Tra (dx_tot_nhat, score 0..1). |dx| lon + score cao =>
/// man DICH (scroll/drag duoc). dx~0 hoac score thap => man khong scroll ngang.
///
/// Cach: lay 1 dai bang ngang giua roi, thu dich b so voi a trong [-max,max],
/// chon dx co sai khac tuyet doi nho nhat (SAD). score = 1 - sad_min/sad_zero.
pub fn shift_x(a: &Image, b: &Image, roi: Rect, max_dx: i32) -> (i32, f32) {
    if a.width != b.width || a.height != b.height {
        return (0, 0.0);
    }
    let ga = cv::hsv_value(a);
    let gb = cv::hsv_value(b);
    // lay 1 hang giua roi (trung binh vai hang cho on dinh)
    let cy = (roi.y + roi.h / 2).min(a.height - 1);
    let y0 = cy.saturating_sub(4);
    let y1 = (cy + 4).min(a.height);
    let x0 = roi.x;
    let x1 = (roi.x + roi.w).min(a.width);
    if x1 <= x0 + max_dx as usize + 1 {
        return (0, 0.0);
    }
    let sad = |dx: i32| -> f64 {
        let mut s = 0f64;
        let mut n = 0f64;
        for y in y0..y1 {
            for x in (x0 as i32 + max_dx)..(x1 as i32 - max_dx) {
                let xa = x as usize;
                let xb = (x + dx) as usize;
                s += (ga.at(xa, y) as i32 - gb.at(xb, y) as i32).abs() as f64;
                n += 1.0;
            }
        }
        if n > 0.0 {
            s / n
        } else {
            f64::INFINITY
        }
    };
    let sad0 = sad(0);
    let mut best_dx = 0i32;
    let mut best = sad0;
    for dx in -max_dx..=max_dx {
        let s = sad(dx);
        if s < best {
            best = s;
            best_dx = dx;
        }
    }
    // score: muc cai thien so voi khong dich (sad0). 0 = khong scroll, 1 = khop hoan hao
    let score = if sad0 > 1e-6 {
        ((sad0 - best) / sad0).clamp(0.0, 1.0) as f32
    } else {
        0.0
    };
    (best_dx, score)
}

/// Uoc luong DICH DOC (dy), tuong tu shift_x.
pub fn shift_y(a: &Image, b: &Image, roi: Rect, max_dy: i32) -> (i32, f32) {
    if a.width != b.width || a.height != b.height {
        return (0, 0.0);
    }
    let ga = cv::hsv_value(a);
    let gb = cv::hsv_value(b);
    let cx = (roi.x + roi.w / 2).min(a.width - 1);
    let x0 = cx.saturating_sub(4);
    let x1 = (cx + 4).min(a.width);
    let y0 = roi.y;
    let y1 = (roi.y + roi.h).min(a.height);
    if y1 <= y0 + max_dy as usize + 1 {
        return (0, 0.0);
    }
    let sad = |dy: i32| -> f64 {
        let mut s = 0f64;
        let mut n = 0f64;
        for x in x0..x1 {
            for y in (y0 as i32 + max_dy)..(y1 as i32 - max_dy) {
                let ya = y as usize;
                let yb = (y + dy) as usize;
                s += (ga.at(x, ya) as i32 - gb.at(x, yb) as i32).abs() as f64;
                n += 1.0;
            }
        }
        if n > 0.0 {
            s / n
        } else {
            f64::INFINITY
        }
    };
    let sad0 = sad(0);
    let mut best_dy = 0i32;
    let mut best = sad0;
    for dy in -max_dy..=max_dy {
        let s = sad(dy);
        if s < best {
            best = s;
            best_dy = dy;
        }
    }
    let score = if sad0 > 1e-6 {
        ((sad0 - best) / sad0).clamp(0.0, 1.0) as f32
    } else {
        0.0
    };
    (best_dy, score)
}

/// Ket qua probe kha nang di chuyen cua man.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Movability {
    /// dich ngang uoc luong (px) + do tin cay
    pub dx: i32,
    pub dx_score: f32,
    /// dich doc uoc luong (px) + do tin cay
    pub dy: i32,
    pub dy_score: f32,
    /// ty le pixel doi (animation/scroll)
    pub diff: f32,
}

impl Movability {
    /// Man co di chuyen duoc khong: co dich dang ke voi do tin cay cao.
    /// MIN_SHIFT px + score nguong -> tranh nham animation nho.
    pub fn is_movable(&self) -> bool {
        const MIN_SHIFT: i32 = 6;
        const MIN_SCORE: f32 = 0.25;
        (self.dx.abs() >= MIN_SHIFT && self.dx_score >= MIN_SCORE)
            || (self.dy.abs() >= MIN_SHIFT && self.dy_score >= MIN_SCORE)
    }
}

/// Phan tich 2 frame (truoc/sau khi drag) -> Movability. roi = vung quan tam
/// (vd vung giua man, tranh thanh cong cu co dinh). max = bien do tim dich.
pub fn analyze_movability(before: &Image, after: &Image, roi: Rect, max: i32) -> Movability {
    let (dx, dxs) = shift_x(before, after, roi, max);
    let (dy, dys) = shift_y(before, after, roi, max);
    let diff = diff_ratio(before, after, 18, Some(roi));
    Movability {
        dx,
        dx_score: dxs,
        dy,
        dy_score: dys,
        diff,
    }
}

// dung Mat1 de tranh canh bao import thua khi feature off
#[allow(dead_code)]
fn _touch(_: &Mat1) {}

#[cfg(test)]
mod tests {
    use super::*;

    /// Tao anh co soc doc (de test dich ngang).
    fn stripes(w: usize, h: usize, offset: i32, period: i32) -> Image {
        let mut d = vec![0u8; w * h * 3];
        for y in 0..h {
            for x in 0..w {
                let v = if (((x as i32 + offset) / period) % 2) == 0 { 220 } else { 30 };
                let i = (y * w + x) * 3;
                d[i] = v;
                d[i + 1] = v;
                d[i + 2] = v;
            }
        }
        Image::from_rgb(w, h, d).unwrap()
    }

    #[test]
    fn diff_ratio_giong_nhau_la_0() {
        let a = stripes(80, 60, 0, 10);
        let b = a.clone();
        assert!(diff_ratio(&a, &b, 18, None) < 0.01);
    }

    #[test]
    fn shift_x_phat_hien_dich_ngang() {
        let a = stripes(120, 60, 0, 12);
        let b = stripes(120, 60, 8, 12); // dich 8px
        let roi = Rect { x: 0, y: 0, w: 120, h: 60 };
        let (dx, score) = shift_x(&a, &b, roi, 16);
        // soc tuan hoan -> dich co the la +8 hoac -4 (do period). chap nhan khop |dx|>0
        assert!(dx.abs() >= 4 && score > 0.5, "dx={dx} score={score}");
    }

    #[test]
    fn man_tinh_khong_movable() {
        let a = stripes(120, 60, 0, 12);
        let b = a.clone();
        let mv = analyze_movability(&a, &b, Rect { x: 0, y: 0, w: 120, h: 60 }, 16);
        assert!(!mv.is_movable(), "man tinh khong duoc coi la movable: {mv:?}");
    }

    #[test]
    fn man_dich_la_movable() {
        let a = stripes(160, 60, 0, 20);
        let b = stripes(160, 60, 12, 20); // dich 12px (> MIN_SHIFT)
        let mv = analyze_movability(&a, &b, Rect { x: 0, y: 0, w: 160, h: 60 }, 20);
        assert!(mv.is_movable(), "man dich phai movable: {mv:?}");
    }
}

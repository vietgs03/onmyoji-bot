//! page.rs - Page detector (landmark template match) cho man UI game.
//!
//! Khac dhash (hash full-screen, nhay voi man DONG/3D), page detector match 1
//! LANDMARK ON DINH (nut menu/chu tieu de) tai ROI co dinh -> robust. Port tu
//! OAS (xem eye-rs/tools/oas_page_detector.py + extract_oas_pages.py).
//!
//! Asset nap tu manifest JSON + cac PNG template (da scale ve 1136x640):
//!   eye-rs/assets/pages/{manifest.json, <page>.png}
//! Moi entry: page, roi[x,y,w,h], threshold, template PNG.
//!
//! detect(): tra page khop manh nhat (score >= threshold), hoac None.

use crate::image::Image;
use crate::template::{match_template_roi, Roi};

/// 1 page can nhan: ten + ROI tim + template + nguong.
#[derive(Clone)]
pub struct PageTemplate {
    pub page: String,
    pub roi: Roi,
    pub threshold: f64,
    pub template: Image,
}

/// Ket qua detect 1 page: ten + score + vi tri landmark tim thay.
#[derive(Debug, Clone)]
pub struct PageHit {
    pub page: String,
    pub score: f64,
    pub x: usize,
    pub y: usize,
}

/// Bo detector chua nhieu page template.
#[derive(Clone, Default)]
pub struct PageDetector {
    pub pages: Vec<PageTemplate>,
}

impl PageDetector {
    pub fn new() -> Self {
        PageDetector { pages: Vec::new() }
    }

    pub fn add(&mut self, p: PageTemplate) {
        self.pages.push(p);
    }

    /// Tra TAT CA page vuot threshold, sap theo score giam dan.
    pub fn detect_all(&self, img: &Image) -> Vec<PageHit> {
        let mut hits: Vec<PageHit> = self
            .pages
            .iter()
            .filter_map(|p| {
                let m = match_template_roi(img, &p.template, p.roi)?;
                if m.score >= p.threshold {
                    Some(PageHit {
                        page: p.page.clone(),
                        score: m.score,
                        x: m.x,
                        y: m.y,
                    })
                } else {
                    None
                }
            })
            .collect();
        hits.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
        hits
    }

    /// Tra page khop manh nhat (hoac None).
    pub fn detect(&self, img: &Image) -> Option<PageHit> {
        self.detect_all(img).into_iter().next()
    }

    /// Score THO cua moi page (de debug nguong), khong loc threshold.
    pub fn scores(&self, img: &Image) -> Vec<(String, f64)> {
        let mut v: Vec<(String, f64)> = self
            .pages
            .iter()
            .map(|p| {
                let s = match_template_roi(img, &p.template, p.roi)
                    .map(|m| m.score)
                    .unwrap_or(f64::NEG_INFINITY);
                (p.page.clone(), s)
            })
            .collect();
        v.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        v
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn solid(w: usize, h: usize, rgb: (u8, u8, u8)) -> Image {
        let mut d = Vec::with_capacity(w * h * 3);
        for _ in 0..w * h {
            d.push(rgb.0);
            d.push(rgb.1);
            d.push(rgb.2);
        }
        Image::from_rgb(w, h, d).unwrap()
    }

    #[test]
    fn detect_chon_page_score_cao_nhat() {
        // anh 20x20 voi 1 patch dac biet o (5,5). template = patch do.
        let mut seed: u32 = 999;
        let mut rnd = || {
            seed = seed.wrapping_mul(1103515245).wrapping_add(12345);
            (seed >> 16) as u8
        };
        let mut d = Vec::with_capacity(20 * 20 * 3);
        for _ in 0..20 * 20 * 3 {
            d.push(rnd());
        }
        let img = Image::from_rgb(20, 20, d).unwrap();
        let mut td = Vec::new();
        for ry in 0..4 {
            for rx in 0..4 {
                let (r, g, b) = img.rgb(5 + rx, 5 + ry);
                td.push(r);
                td.push(g);
                td.push(b);
            }
        }
        let tmpl = Image::from_rgb(4, 4, td).unwrap();
        let mut det = PageDetector::new();
        det.add(PageTemplate {
            page: "match".into(),
            roi: Roi { x: 0, y: 0, w: 20, h: 20 },
            threshold: 0.9,
            template: tmpl,
        });
        // page khong khop: template solid lac
        det.add(PageTemplate {
            page: "nomatch".into(),
            roi: Roi { x: 0, y: 0, w: 20, h: 20 },
            threshold: 0.9,
            template: solid(4, 4, (123, 45, 67)),
        });
        let hit = det.detect(&img).unwrap();
        assert_eq!(hit.page, "match");
        assert!(hit.score >= 0.99, "score={}", hit.score);
    }

    #[test]
    fn khong_khop_tra_none() {
        let img = solid(20, 20, (10, 20, 30));
        let mut det = PageDetector::new();
        // template ngau nhien khac han -> score thap
        det.add(PageTemplate {
            page: "x".into(),
            roi: Roi { x: 0, y: 0, w: 20, h: 20 },
            threshold: 0.95,
            template: solid(4, 4, (200, 100, 50)),
        });
        // solid vs solid: den == 0 -> score 0 < 0.95 -> None
        assert!(det.detect(&img).is_none());
    }
}

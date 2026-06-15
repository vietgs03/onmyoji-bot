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
use crate::template::{crop, downscale_box, match_template_roi, MatchResult, Roi};

/// 1 page can nhan: ten + ROI tim + template + nguong.
#[derive(Clone)]
pub struct PageTemplate {
    pub page: String,
    pub roi: Roi,
    pub threshold: f64,
    pub template: Image,
    /// template da thu nho (cache theo `scale` cua detector). None = chua build.
    template_ds: Option<Image>,
}

impl PageTemplate {
    pub fn new(page: String, roi: Roi, threshold: f64, template: Image) -> Self {
        PageTemplate {
            page,
            roi,
            threshold,
            template,
            template_ds: None,
        }
    }
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
///
/// `scale` (mac dinh 2): thu nho ca frame-ROI lan template truoc khi match ->
/// nhanh ~scale^4 lan. Landmark UI giu duoc score (do diem dac trung lon), da
/// kiem: page_main 0.989->0.977, page tot nhat khong doi. scale=1 = full (chinh xac).
#[derive(Clone)]
pub struct PageDetector {
    pub pages: Vec<PageTemplate>,
    pub scale: usize,
}

impl Default for PageDetector {
    fn default() -> Self {
        PageDetector {
            pages: Vec::new(),
            scale: 2,
        }
    }
}

impl PageDetector {
    pub fn new() -> Self {
        PageDetector::default()
    }

    /// Dat he so thu nho (1 = full chinh xac, 2 = nhanh ~16x). Build lai cache.
    pub fn with_scale(mut self, scale: usize) -> Self {
        self.scale = scale.max(1);
        for p in &mut self.pages {
            p.template_ds = None;
        }
        self
    }

    pub fn add(&mut self, mut p: PageTemplate) {
        // build cache template thu nho ngay (1 lan)
        if self.scale > 1 {
            p.template_ds = Some(downscale_box(&p.template, self.scale));
        }
        self.pages.push(p);
    }

    /// Tra TAT CA page vuot threshold, sap theo score giam dan.
    /// Song song theo page (moi page doc lap) khi co nhieu page + nhieu CPU.
    pub fn detect_all(&self, img: &Image) -> Vec<PageHit> {
        let mut hits = self.scan_all(img);
        // loc theo threshold rieng cua tung page
        let thr: std::collections::HashMap<&str, f64> =
            self.pages.iter().map(|p| (p.page.as_str(), p.threshold)).collect();
        hits.retain(|h| thr.get(h.page.as_str()).map(|t| h.score >= *t).unwrap_or(false));
        hits.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
        hits
    }

    /// Quet moi page -> PageHit (CHUA loc threshold). Song song theo page.
    fn scan_all(&self, img: &Image) -> Vec<PageHit> {
        // moi page la 1 don vi cong viec nang (template match ROI rong) -> chia
        // deu cho min(num_cpus, so_page) thread. Khong dung nthreads (theo hang).
        let nthreads = crate::par::num_cpus().min(self.pages.len()).max(1);
        if nthreads <= 1 {
            return self
                .pages
                .iter()
                .filter_map(|p| self.scan_one(img, p))
                .collect();
        }
        // chia page thanh `nthreads` lo, moi thread quet 1 lo.
        let chunk = self.pages.len().div_ceil(nthreads);
        let mut out = Vec::with_capacity(self.pages.len());
        std::thread::scope(|s| {
            let mut handles = Vec::new();
            for batch in self.pages.chunks(chunk) {
                handles.push(s.spawn(|| {
                    batch
                        .iter()
                        .filter_map(|p| self.scan_one(img, p))
                        .collect::<Vec<_>>()
                }));
            }
            for h in handles {
                if let Ok(v) = h.join() {
                    out.extend(v);
                }
            }
        });
        out
    }

    fn scan_one(&self, img: &Image, p: &PageTemplate) -> Option<PageHit> {
        let m = self.match_one(img, p)?;
        Some(PageHit {
            page: p.page.clone(),
            score: m.score,
            x: m.x,
            y: m.y,
        })
    }

    /// Match 1 page: dung template thu nho (scale>1) tren ROI da thu nho de nhanh,
    /// roi anh xa vi tri ve toa do GOC. scale=1 -> match truc tiep full.
    fn match_one(&self, img: &Image, p: &PageTemplate) -> Option<MatchResult> {
        if self.scale <= 1 || p.template_ds.is_none() {
            return match_template_roi(img, &p.template, p.roi);
        }
        let f = self.scale;
        let tmpl_ds = p.template_ds.as_ref().unwrap();
        // crop ROI goc -> thu nho -> match. Bo crop chinh xac de downscale_box
        // chia het. ROI da clamp trong bien anh.
        let roi = p.roi.clamp(img.width, img.height);
        let sub = crop(img, roi);
        let sub_ds = downscale_box(&sub, f);
        let m = match_template_roi(
            &sub_ds,
            tmpl_ds,
            Roi {
                x: 0,
                y: 0,
                w: sub_ds.width,
                h: sub_ds.height,
            },
        )?;
        // anh xa vi tri ve goc: roi.xy + (vi tri trong sub_ds)*f
        Some(MatchResult {
            x: roi.x + m.x * f,
            y: roi.y + m.y * f,
            score: m.score,
        })
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
                let s = self
                    .match_one(img, p)
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
        // scale=1 (full) de test logic chinh xac tren anh nho
        let mut det = PageDetector::new().with_scale(1);
        det.add(PageTemplate::new(
            "match".into(),
            Roi { x: 0, y: 0, w: 20, h: 20 },
            0.9,
            tmpl,
        ));
        // page khong khop: template solid lac
        det.add(PageTemplate::new(
            "nomatch".into(),
            Roi { x: 0, y: 0, w: 20, h: 20 },
            0.9,
            solid(4, 4, (123, 45, 67)),
        ));
        let hit = det.detect(&img).unwrap();
        assert_eq!(hit.page, "match");
        assert!(hit.score >= 0.99, "score={}", hit.score);
    }

    #[test]
    fn khong_khop_tra_none() {
        let img = solid(20, 20, (10, 20, 30));
        let mut det = PageDetector::new().with_scale(1);
        // template ngau nhien khac han -> score thap
        det.add(PageTemplate::new(
            "x".into(),
            Roi { x: 0, y: 0, w: 20, h: 20 },
            0.95,
            solid(4, 4, (200, 100, 50)),
        ));
        // solid vs solid: den == 0 -> score 0 < 0.95 -> None
        assert!(det.detect(&img).is_none());
    }
}

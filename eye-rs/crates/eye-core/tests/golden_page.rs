//! golden_page.rs - Kiem page detector (template match) KHOP cv2.matchTemplate.
//!
//! Nap manifest + template PNG (eye-rs/assets/pages), chay match_template_roi tren
//! frame_home.png, so score voi golden sinh tu cv2 (TM_CCOEFF_NORMED). Sai so cho
//! phep nho (Rust f64 vs cv2 f32). Cung kiem: page khop manh nhat == page_main.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

use eye_core::{Image, PageDetector, PageTemplate, Roi};
use serde_json::Value;

fn root() -> std::path::PathBuf {
    // crate dir = eye-rs/crates/eye-core; len 2 cap = eye-rs
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf()
}

fn load_detector(eye_rs: &Path) -> PageDetector {
    let manifest_path = eye_rs.join("assets/pages/manifest.json");
    let txt = fs::read_to_string(&manifest_path)
        .unwrap_or_else(|e| panic!("doc manifest {manifest_path:?}: {e}"));
    let m: Value = serde_json::from_str(&txt).unwrap();
    let mut det = PageDetector::new();
    for p in m["pages"].as_array().unwrap() {
        let page = p["page"].as_str().unwrap().to_string();
        let roi = p["roi"].as_array().unwrap();
        let roi = Roi {
            x: roi[0].as_u64().unwrap() as usize,
            y: roi[1].as_u64().unwrap() as usize,
            w: roi[2].as_u64().unwrap() as usize,
            h: roi[3].as_u64().unwrap() as usize,
        };
        let threshold = p["threshold"].as_f64().unwrap();
        let file = p["file"].as_str().unwrap();
        let png = fs::read(eye_rs.join("assets/pages").join(file)).unwrap();
        let template = Image::decode_png(&png).unwrap();
        det.add(PageTemplate {
            page,
            roi,
            threshold,
            template,
        });
    }
    det
}

#[test]
fn page_detector_khop_cv2_golden() {
    let eye_rs = root();
    let det = load_detector(&eye_rs);
    let frame_png = fs::read(eye_rs.join("tests/goldens/pages/frame_home.png")).unwrap();
    let frame = Image::decode_png(&frame_png).unwrap();

    let golden_txt =
        fs::read_to_string(eye_rs.join("tests/goldens/pages/expected.json")).unwrap();
    let golden: HashMap<String, Value> = serde_json::from_str(&golden_txt).unwrap();

    let mut max_diff = 0f64;
    let mut checked = 0;
    for p in &det.pages {
        let g = &golden[&p.page];
        if g.is_null() {
            continue; // template lon hon roi -> bo qua
        }
        let exp_score = g["score"].as_f64().unwrap();
        let m = eye_core::match_template_roi(&frame, &p.template, p.roi)
            .unwrap_or_else(|| panic!("match_template_roi None cho {}", p.page));
        let diff = (m.score - exp_score).abs();
        assert!(
            diff < 1e-3,
            "page {} score lech: rust={} cv2={} diff={}",
            p.page,
            m.score,
            exp_score,
            diff
        );
        max_diff = max_diff.max(diff);
        checked += 1;
    }
    assert!(checked >= 25, "qua it page kiem: {checked}");
    eprintln!("[golden_page] kiem {checked} page, max_diff={max_diff:.2e}");

    // page khop manh nhat phai la page_main (frame la HOME)
    let hit = det.detect(&frame).expect("phai detect duoc page");
    assert_eq!(hit.page, "page_main", "frame HOME phai ra page_main");
    assert!(hit.score > 0.9, "score page_main qua thap: {}", hit.score);
}

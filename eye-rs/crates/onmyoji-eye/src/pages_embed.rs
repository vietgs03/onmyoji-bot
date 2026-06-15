//! pages_embed.rs - Nap PageDetector tu asset NHUNG SAN trong binary.
//!
//! De onmyoji-eye la .exe doc lap (khong can file ngoai), ta include_bytes!
//! manifest + tung template PNG luc compile. Danh sach template sinh boi
//! tools/gen_pages_embed.py (chay lai khi them/bot page). Parse manifest JSON
//! luc khoi dong -> PageDetector.

use eye_core::{Image, PageDetector, PageTemplate, Roi};
use std::sync::OnceLock;

/// (ten file, bytes PNG) nhung san. Sinh tu tools/gen_pages_embed.py.
mod embedded {
    include!(concat!(env!("CARGO_MANIFEST_DIR"), "/src/pages_data.rs"));
}

/// PageDetector dung chung (nap 1 lan, thread-safe). Asset nhung san nen khong
/// the loi runtime -> an toan giu global.
static DETECTOR: OnceLock<PageDetector> = OnceLock::new();

/// Tra detector dung chung (lazy init lan dau goi).
pub fn detector() -> &'static PageDetector {
    DETECTOR.get_or_init(load_embedded)
}

/// Nap PageDetector tu asset nhung. Panic neu manifest hong (loi compile-time data).
pub fn load_embedded() -> PageDetector {
    let manifest: serde_json::Value =
        serde_json::from_str(embedded::MANIFEST).expect("manifest nhung hong");
    let mut det = PageDetector::new();
    for p in manifest["pages"].as_array().unwrap() {
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
        let bytes = embedded::template_bytes(file)
            .unwrap_or_else(|| panic!("thieu template nhung: {file}"));
        let template = Image::decode_png(bytes).unwrap();
        det.add(PageTemplate {
            page,
            roi,
            threshold,
            template,
        });
    }
    det
}

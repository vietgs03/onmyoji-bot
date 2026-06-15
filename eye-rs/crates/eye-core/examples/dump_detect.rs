//! dump_detect.rs - xuat detection cua Rust cho moi anh golden ra JSON (dev only).
//! Dung de chan doan diem lech giua Rust va Python.
use eye_core::{detect_buttons, Image};
use std::io::Write;

fn main() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(3)
        .unwrap()
        .to_path_buf();
    let gjson = root.join("eye-rs/tests/goldens/perception_goldens_full.json");
    let txt = std::fs::read_to_string(&gjson).unwrap();
    let v: serde_json::Value = serde_json::from_str(&txt).unwrap();
    let obj = v.as_object().unwrap();

    let out_path = std::env::args().nth(1).unwrap_or_else(|| "/tmp/rust_detect.json".into());
    let mut out = std::collections::BTreeMap::new();
    for (key, g) in obj {
        let rel = g["path"].as_str().unwrap();
        let bytes = match std::fs::read(root.join(rel)) {
            Ok(b) => b,
            Err(_) => continue,
        };
        let img = Image::decode_png(&bytes).unwrap();
        let dets: Vec<[f64; 5]> = detect_buttons(&img, false)
            .iter()
            .map(|b| [b.cx as f64, b.cy as f64, b.w as f64, b.h as f64, b.score as f64])
            .collect();
        out.insert(key.clone(), dets);
    }
    let s = serde_json::to_string(&out).unwrap();
    let mut f = std::fs::File::create(&out_path).unwrap();
    f.write_all(s.as_bytes()).unwrap();
    eprintln!("wrote {} ({} imgs)", out_path, out.len());
}

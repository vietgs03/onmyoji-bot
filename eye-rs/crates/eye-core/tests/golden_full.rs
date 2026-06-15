//! golden_full.rs - validate eye-core tren TOAN BO 322 anh full-screen (khong chi 105
//! world.json). Day la tap test lon hon, sat thuc te hon (gom ca man chua hoc).
//!
//! Sinh boi: .venv/bin/python (xem tests/goldens/perception_goldens_full.json).
//! Moi golden co `path` (tuong doi tu repo root) de doc dung file.

use std::collections::HashMap;
use std::path::PathBuf;

use eye_core::{detect_buttons, dhash, hamming, is_loading, Image};
use serde::Deserialize;

#[derive(Deserialize)]
struct Golden {
    path: String,
    dhash: String,
    is_loading: bool,
    buttons: Vec<[f64; 5]>,
}

fn repo_root() -> PathBuf {
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for _ in 0..3 {
        p.pop();
    }
    p
}

fn goldens_path() -> PathBuf {
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.pop();
    p.pop();
    p.push("tests/goldens/perception_goldens_full.json");
    p
}

fn load() -> HashMap<String, Golden> {
    let raw = std::fs::read_to_string(goldens_path())
        .expect("doc perception_goldens_full.json (chay script sinh truoc)");
    serde_json::from_str(&raw).expect("parse goldens full")
}

#[test]
fn dhash_full_within_threshold() {
    const CANON_THR: usize = 12;
    let root = repo_root();
    let goldens = load();
    let mut max_ham = 0;
    let mut sum = 0usize;
    let mut exact = 0;
    let mut n = 0;
    let mut over = 0;
    for g in goldens.values() {
        let bytes = match std::fs::read(root.join(&g.path)) {
            Ok(b) => b,
            Err(_) => continue,
        };
        let img = Image::decode_png(&bytes).unwrap();
        let dh = match dhash(&img) {
            Some(d) => d,
            None => continue,
        };
        let ham = hamming(&dh, &g.dhash);
        if ham == 0 {
            exact += 1;
        }
        if ham > CANON_THR {
            over += 1;
        }
        max_ham = max_ham.max(ham);
        sum += ham;
        n += 1;
    }
    eprintln!(
        "[dhash FULL] n={n} exact={exact} max_ham={max_ham} avg={:.3} over_thr={over}",
        sum as f64 / n as f64
    );
    assert!(n >= 300, "qua it ({n})");
    // moi anh phai trong nguong fuzzy (neu khong world model se nham)
    assert_eq!(over, 0, "{over} anh vuot CANON_THR=12 (world model se MISS)");
    assert!(max_ham <= 6, "max hamming {max_ham} > 6 (nghi lech thuat toan)");
}

#[test]
fn is_loading_full() {
    let root = repo_root();
    let goldens = load();
    let mut n = 0;
    let mut mismatch = 0;
    for g in goldens.values() {
        let bytes = match std::fs::read(root.join(&g.path)) {
            Ok(b) => b,
            Err(_) => continue,
        };
        let img = Image::decode_png(&bytes).unwrap();
        if is_loading(&img) != g.is_loading {
            mismatch += 1;
        }
        n += 1;
    }
    eprintln!("[is_loading FULL] n={n} mismatch={mismatch}");
    assert!(n >= 300);
    assert_eq!(mismatch, 0, "{mismatch} anh is_loading lech");
}

#[test]
fn detect_buttons_coverage_full() {
    const TOL: i32 = 18;
    let root = repo_root();
    let goldens = load();
    let mut tot_m = 0usize;
    let mut tot = 0usize;
    let mut n = 0;
    for g in goldens.values() {
        let bytes = match std::fs::read(root.join(&g.path)) {
            Ok(b) => b,
            Err(_) => continue,
        };
        let img = Image::decode_png(&bytes).unwrap();
        let rs: Vec<(i32, i32)> = detect_buttons(&img, false)
            .iter()
            .map(|b| (b.cx, b.cy))
            .collect();
        for b in &g.buttons {
            let (ax, ay) = (b[0] as i32, b[1] as i32);
            if rs
                .iter()
                .any(|&(bx, by)| (ax - bx).abs() <= TOL && (ay - by).abs() <= TOL)
            {
                tot_m += 1;
            }
        }
        tot += g.buttons.len();
        n += 1;
    }
    eprintln!(
        "[detect_buttons FULL] n={n} coverage={}/{} = {:.1}%",
        tot_m,
        tot,
        100.0 * tot_m as f64 / tot as f64
    );
    assert!(n >= 300);
    assert!(
        tot_m as f64 / tot as f64 >= 0.40,
        "coverage qua thap"
    );
}

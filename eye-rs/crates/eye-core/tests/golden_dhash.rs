//! golden_dhash.rs - validate eye-core khop Python (nguon su that = perception_goldens.json).
//!
//! Goldens sinh boi Python tu 105 screenshot that. Test bao dam:
//!   1. md5_hex khop hashlib (qua state_id)
//!   2. dhash Rust gan Python: hamming <= 12 (nguong fuzzy CANON_THR) cho MOI golden
//!      va trung binh rat nho (muc tieu max <= 2 nhu da do o Python).
//!   3. is_loading khop tuyet doi.
//!
//! Neu test nay fail => perception Rust da lech khoi Python, world model se sai.

use std::collections::HashMap;
use std::path::PathBuf;

use eye_core::md5::md5_hex;
use eye_core::{dhash, hamming, is_loading, state_id, Image};
use serde::Deserialize;

#[derive(Deserialize)]
struct Golden {
    dhash: String,
    state_id: String,
    is_loading: bool,
    stored_dhash: String,
}

fn repo_root() -> PathBuf {
    // CARGO_MANIFEST_DIR = eye-rs/crates/eye-core -> len 3 cap toi root onmyoji-bot
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for _ in 0..3 {
        p.pop();
    }
    p
}

fn goldens_path() -> PathBuf {
    // eye-rs/tests/goldens/perception_goldens.json
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.pop(); // eye-core -> crates
    p.pop(); // crates -> eye-rs
    p.push("tests/goldens/perception_goldens.json");
    p
}

fn load_goldens() -> HashMap<String, Golden> {
    let raw = std::fs::read_to_string(goldens_path())
        .unwrap_or_else(|e| panic!("doc goldens that bai {:?}: {e}", goldens_path()));
    serde_json::from_str(&raw).expect("parse goldens JSON")
}

#[test]
fn md5_matches_python_hashlib() {
    // vector chuan RFC 1321
    assert_eq!(md5_hex(b""), "d41d8cd98f00b204e9800998ecf8427e");
    assert_eq!(md5_hex(b"abc"), "900150983cd24fb0d6963f7d28e17f72");
    assert_eq!(
        md5_hex(b"The quick brown fox jumps over the lazy dog"),
        "9e107d9d372bb6826bd81d3542a419d6"
    );
}

#[test]
fn state_id_matches_python() {
    // state_id = md5(dhash)[:10] - khop voi gia tri Python da luu trong goldens
    let goldens = load_goldens();
    let mut checked = 0;
    for g in goldens.values() {
        // dung dhash da luu cua Python -> state_id phai khop het
        assert_eq!(state_id(&g.stored_dhash), g.state_id, "state_id lech");
        checked += 1;
    }
    assert!(checked >= 100, "qua it golden ({checked})");
}

#[test]
fn dhash_matches_python_within_fuzzy_threshold() {
    const CANON_THR: usize = 12; // nguong fuzzy cua world_model.py
    let root = repo_root();
    let goldens = load_goldens();
    assert!(!goldens.is_empty(), "goldens rong");

    let mut max_ham = 0usize;
    let mut sum_ham = 0usize;
    let mut exact = 0usize;
    let mut n = 0usize;
    let mut worst: Vec<(String, usize)> = Vec::new();

    for (fname, g) in &goldens {
        let png_path = root.join("exploration/screens").join(fname);
        let bytes = match std::fs::read(&png_path) {
            Ok(b) => b,
            Err(_) => continue, // anh khong con -> bo qua
        };
        let img = Image::decode_png(&bytes)
            .unwrap_or_else(|e| panic!("decode {fname}: {e}"));
        let dh = dhash(&img).unwrap_or_else(|| panic!("dhash None cho {fname}"));

        // do dai phai khop Python
        assert_eq!(dh.len(), g.dhash.len(), "do dai dhash lech ({fname})");
        let ham = hamming(&dh, &g.dhash);
        if ham == 0 {
            exact += 1;
        }
        max_ham = max_ham.max(ham);
        sum_ham += ham;
        n += 1;
        worst.push((fname.clone(), ham));

        // YEU CAU CUNG: moi golden phai trong nguong fuzzy
        assert!(
            ham <= CANON_THR,
            "{fname}: hamming {ham} > CANON_THR {CANON_THR} (world model se MISS)"
        );
    }

    worst.sort_by(|a, b| b.1.cmp(&a.1));
    eprintln!(
        "dhash vs Python: n={n} exact={exact} max_ham={max_ham} avg_ham={:.3}",
        sum_ham as f64 / n as f64
    );
    eprintln!("  top lech: {:?}", &worst[..worst.len().min(5)]);

    assert!(n >= 100, "qua it anh test ({n})");
    // muc tieu chat hon nguong fuzzy: max <= 4 (da do Python max=2, cho bien do nho)
    assert!(max_ham <= 4, "max hamming {max_ham} > 4 (nghi ngo lech thuat toan)");
}

#[test]
fn is_loading_matches_python() {
    let root = repo_root();
    let goldens = load_goldens();
    let mut n = 0;
    for (fname, g) in &goldens {
        let png_path = root.join("exploration/screens").join(fname);
        let bytes = match std::fs::read(&png_path) {
            Ok(b) => b,
            Err(_) => continue,
        };
        let img = Image::decode_png(&bytes).unwrap();
        assert_eq!(is_loading(&img), g.is_loading, "is_loading lech ({fname})");
        n += 1;
    }
    assert!(n >= 100, "qua it anh ({n})");
}

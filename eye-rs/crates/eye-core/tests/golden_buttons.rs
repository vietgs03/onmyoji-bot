//! golden_buttons.rs - do COVERAGE detect_buttons Rust so voi Python (KHONG bit-exact).
//!
//! detect_buttons chi dung khi EXPLORE (navigate thi replay toa do da hoc). Vi the
//! tieu chi la RECALL: bao nhieu % button Python (diem cao) co button Rust GAN
//! (<= tol px). Test in ra so lieu de ta danh gia trung thuc, va dat nguong toi
//! thieu de phat hien hoi quy.

use std::collections::HashMap;
use std::path::PathBuf;

use eye_core::{detect_buttons, Image};
use serde::Deserialize;

#[derive(Deserialize)]
struct Golden {
    buttons: Vec<[f64; 5]>, // [cx, cy, w, h, score]
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
    p.push("tests/goldens/perception_goldens.json");
    p
}

fn load() -> HashMap<String, Golden> {
    let raw = std::fs::read_to_string(goldens_path()).expect("doc goldens");
    serde_json::from_str(&raw).expect("parse goldens")
}

/// % button trong A (Python) co 1 button GAN trong B (Rust), trong nguong tol.
fn coverage(py: &[[f64; 5]], rs: &[(i32, i32)], tol: i32) -> (usize, usize) {
    if py.is_empty() {
        return (0, 0);
    }
    let mut matched = 0;
    for b in py {
        let (ax, ay) = (b[0] as i32, b[1] as i32);
        if rs
            .iter()
            .any(|&(bx, by)| (ax - bx).abs() <= tol && (ay - by).abs() <= tol)
        {
            matched += 1;
        }
    }
    (matched, py.len())
}

#[test]
fn detect_buttons_coverage_report() {
    const TOL: i32 = 18; // = world_model.is_tried tol
    let root = repo_root();
    let goldens = load();

    let mut tot_match = 0usize;
    let mut tot_py = 0usize;
    let mut per_screen: Vec<(String, f64, usize, usize)> = Vec::new(); // (name, cov, n_py, n_rs)
    let mut n_screen = 0usize;

    for (fname, g) in &goldens {
        let png = root.join("exploration/screens").join(fname);
        let bytes = match std::fs::read(&png) {
            Ok(b) => b,
            Err(_) => continue,
        };
        let img = Image::decode_png(&bytes).unwrap();
        let rs_btns = detect_buttons(&img, false);
        let rs_pts: Vec<(i32, i32)> = rs_btns.iter().map(|b| (b.cx, b.cy)).collect();
        let (m, n) = coverage(&g.buttons, &rs_pts, TOL);
        tot_match += m;
        tot_py += n;
        n_screen += 1;
        let cov = if n > 0 { m as f64 / n as f64 } else { 1.0 };
        per_screen.push((fname.clone(), cov, n, rs_pts.len()));
    }

    per_screen.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
    let overall = tot_match as f64 / tot_py.max(1) as f64;

    eprintln!("=== detect_buttons COVERAGE (Rust phu Python, tol={TOL}px) ===");
    eprintln!(
        "  tong: {tot_match}/{tot_py} = {:.1}%  tren {n_screen} man hinh",
        overall * 100.0
    );
    eprintln!("  5 man COVERAGE THAP nhat:");
    for (name, cov, npy, nrs) in per_screen.iter().take(5) {
        eprintln!("    {name}: {:.0}% (py={npy} rs={nrs})", cov * 100.0);
    }

    assert!(n_screen >= 100, "qua it man ({n_screen})");
    // Nguong toi thieu de bat hoi quy. Hough Rust khong bit-exact OpenCV nen ky vong
    // thap hon Python; dat nguong bao thu, dieu chinh sau khi do that.
    assert!(
        overall >= 0.40,
        "coverage {:.1}% qua thap (<40%) - nghi ngo detect_buttons hong",
        overall * 100.0
    );
}

//! robustness.rs - chung minh detect_buttons NHAN THEO NOI DUNG (doc lap vi tri).
//!
//! Tra loi cau hoi cua user: "dao nguoc/cat nho/xao ngau nhien thi co con detect
//! dung 1 btn khong?". detect_buttons dua tren Hough+saturation CUC BO -> nut o
//! BAT KY vi tri nao van detect duoc (khac han dhash phu thuoc vi tri tuyet doi).
//!
//! Anh test sinh tu Python (robustness/), de kiem chung Rust khop hanh vi.

use std::path::PathBuf;

use eye_core::{detect_buttons, Image};

fn root_path(rel: &str) -> PathBuf {
    // CARGO_MANIFEST_DIR = eye-rs/crates/eye-core -> pop 3 -> repo root onmyoji-bot
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for _ in 0..3 {
        p.pop();
    }
    p.push(rel);
    p
}

fn detect(rel: &str) -> Vec<(i32, i32, i32, i32)> {
    let bytes = std::fs::read(root_path(rel)).expect("doc anh robustness");
    let img = Image::decode_png(&bytes).unwrap();
    detect_buttons(&img, false)
        .iter()
        .map(|b| (b.cx, b.cy, b.w, b.h))
        .collect()
}

/// Anh lat ngang van detect duoc nhieu nut (khong sup ve 0).
#[test]
fn flipped_image_still_detects() {
    let b = detect("eye-rs/tests/goldens/robustness/flip_h.png");
    eprintln!("[robust] flip_h: Rust detect {} nut", b.len());
    // anh that lat ngang van phai detect duoc nhieu nut (nut o vi tri MOI)
    assert!(
        b.len() >= 40,
        "lat ngang chi detect {} nut (qua it -> nghi phu thuoc vi tri)",
        b.len()
    );
}

/// Nut bi CAT ra va DAN vao vi tri ngau nhien tren nen toi -> van tim thay o cho moi.
/// Day la bang chung manh nhat: detection doc lap vi tri.
#[test]
fn pasted_button_found_at_new_location() {
    let b = detect("eye-rs/tests/goldens/robustness/pasted.png");
    // Python dan nut tai tam (633,433). Rust phai tim thay 1 nut GAN do.
    let (ex, ey) = (633i32, 433i32);
    let found = b
        .iter()
        .any(|&(cx, cy, _, _)| (cx - ex).abs() <= 25 && (cy - ey).abs() <= 25);
    eprintln!(
        "[robust] pasted: Rust detect {} nut, tim nut gan ({ex},{ey}): {}",
        b.len(),
        found
    );
    assert!(
        found,
        "nut dan o vi tri moi ({ex},{ey}) KHONG detect duoc -> detect phu thuoc vi tri"
    );
}

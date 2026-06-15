//! golden_resize.rs - chung minh resize_rgb BIT-EXACT voi cv2.resize INTER_LINEAR.
//!
//! Day la BAT BIEN production quan trong: game ep client 16:9 (vd 1136x640) nhung
//! knowledge base / goldens dung 1152x679. EYE resize client->canon truoc khi dhash
//! de state_id khop KB bat ke resolution. Neu resize lech cv2 -> dhash lech -> bot
//! dieu huong sai. Test khoa byte-exact (MD5 raw RGB) + dhash + state_id.
//!
//! Golden sinh tu Python (scripts/perception.py + cv2): tests/goldens/resize/.

use std::path::PathBuf;

use eye_core::md5::md5_hex;
use eye_core::{dhash, resize_rgb, state_id, Image};

fn root_path(rel: &str) -> PathBuf {
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    for _ in 0..3 {
        p.pop();
    }
    p.push(rel);
    p
}

#[test]
fn resize_rgb_bit_exact_vs_cv2() {
    // doc golden meta
    let meta_path = root_path("eye-rs/tests/goldens/resize/expected.json");
    let meta_raw = std::fs::read_to_string(&meta_path).expect("doc expected.json");
    // parse tho (khong keo serde vao test): lay cac field can thiet
    let want_dhash = json_str(&meta_raw, "dhash");
    let want_sid = json_str(&meta_raw, "state_id");
    let want_md5 = json_str(&meta_raw, "canon_rgb_md5");
    let dst_w = json_num(&meta_raw, "dst_w") as usize;
    let dst_h = json_num(&meta_raw, "dst_h") as usize;

    // doc anh client (input) -> resize ve canon bang Rust
    let bytes = std::fs::read(root_path("eye-rs/tests/goldens/resize/client_1136x640.png"))
        .expect("doc client png");
    let img = Image::decode_png(&bytes).unwrap();
    let canon = resize_rgb(&img, dst_w, dst_h);

    assert_eq!(canon.width, dst_w, "width sai");
    assert_eq!(canon.height, dst_h, "height sai");

    // BYTE-EXACT: MD5 raw RGB phai khop cv2 (chung minh tung pixel giong het)
    let got_md5 = md5_hex(&canon.data);
    eprintln!("[resize] Rust rgb_md5={got_md5} want={want_md5}");
    assert_eq!(got_md5, want_md5, "resize_rgb KHONG byte-exact voi cv2.resize");

    // dhash + state_id phai khop cv2
    let dh = dhash(&canon).expect("dhash canon");
    eprintln!("[resize] Rust state_id={} want={}", state_id(&dh), want_sid);
    assert_eq!(dh, want_dhash, "dhash sau resize lech cv2");
    assert_eq!(state_id(&dh), want_sid, "state_id sau resize lech cv2");
}

/// Resize giu nguyen anh khi src == dst (khong doi byte nao).
#[test]
fn resize_rgb_identity_when_same_size() {
    let bytes = std::fs::read(root_path("eye-rs/tests/goldens/resize/client_1136x640.png"))
        .expect("doc client png");
    let img = Image::decode_png(&bytes).unwrap();
    let same = resize_rgb(&img, img.width, img.height);
    assert_eq!(same.width, img.width);
    assert_eq!(same.height, img.height);
    // resize 1:1 INTER_LINEAR: tam pixel trung khop -> giu nguyen (alpha=2048/0).
    assert_eq!(same.data, img.data, "resize 1:1 phai giu nguyen byte");
}

// --- parser JSON toi gian (chi cho test, tranh keo serde) ---
fn json_str(s: &str, key: &str) -> String {
    let pat = format!("\"{key}\"");
    let i = s.find(&pat).unwrap_or_else(|| panic!("thieu key {key}"));
    let rest = &s[i + pat.len()..];
    let colon = rest.find(':').unwrap();
    let after = &rest[colon + 1..];
    let q0 = after.find('"').unwrap();
    let q1 = after[q0 + 1..].find('"').unwrap();
    after[q0 + 1..q0 + 1 + q1].to_string()
}

fn json_num(s: &str, key: &str) -> i64 {
    let pat = format!("\"{key}\"");
    let i = s.find(&pat).unwrap_or_else(|| panic!("thieu key {key}"));
    let rest = &s[i + pat.len()..];
    let colon = rest.find(':').unwrap();
    let after = rest[colon + 1..].trim_start();
    let end = after
        .find(|c: char| !c.is_ascii_digit() && c != '-')
        .unwrap_or(after.len());
    after[..end].parse().unwrap()
}

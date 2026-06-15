//! prof.rs - do thoi gian tung phan perception (dev only).
use std::time::Instant;
use eye_core::{cv, detect_buttons, dhash, is_loading, Image};

fn bench<F: FnMut()>(name: &str, n: usize, mut f: F) -> f64 {
    for _ in 0..3 { f(); } // warmup
    let mut ts = Vec::with_capacity(n);
    for _ in 0..n { let t = Instant::now(); f(); ts.push(t.elapsed().as_secs_f64()*1000.0); }
    ts.sort_by(|a,b| a.partial_cmp(b).unwrap());
    let p50 = ts[n/2];
    println!("  {name:22} p50={p50:6.2} ms  (min={:.2} max={:.2})", ts[0], ts[n-1]);
    p50
}

fn main() {
    let path = std::env::args().nth(1).expect("PNG");
    let img = Image::decode_png(&std::fs::read(&path).unwrap()).unwrap();
    let bytes = std::fs::read(&path).unwrap();
    let n = 50;
    println!("=== Perception full ===");
    bench("decode_png", n, || { let _ = Image::decode_png(&bytes).unwrap(); });
    bench("dhash", n, || { let _ = dhash(&img); });
    bench("is_loading", n, || { let _ = is_loading(&img); });
    bench("detect_buttons", n, || { let _ = detect_buttons(&img, false); });
    println!("=== Hough chi tiet ===");
    bench("hough_candidates", n, || { let _ = eye_core::hough::hough_circle_candidates(&img); });
    println!("=== Saturation chi tiet ===");
    let sat = cv::hsv_saturation(&img);
    let th = cv::threshold_binary(&sat, 120);
    bench("hsv_saturation", n, || { let _ = cv::hsv_saturation(&img); });
    bench("threshold_binary", n, || { let _ = cv::threshold_binary(&sat, 120); });
    bench("morph_close(9)", n, || { let _ = cv::morph_close(&th, 9); });
    let closed = cv::morph_close(&th, 9);
    bench("connected_components", n, || { let _ = cv::connected_components(&closed); });
}

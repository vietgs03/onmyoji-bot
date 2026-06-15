//! eye-core - perception thuan (port tu scripts/perception.py).
//!
//! Khong I/O he thong, de unit-test. Day la lop CV se chay trong onmyoji-eye.exe.
//! Moi ham co tinh "khop Python" deu duoc validate so voi goldens trong
//! `tests/golden_dhash.rs` (sinh tu Python, nguon su that).

pub mod cv;
pub mod detect;
pub mod hough;
pub mod image;
pub mod md5;
pub mod page;
pub mod par;
pub mod perception;
pub mod template;

pub use detect::{detect_buttons, Button};
pub use image::{Image, ImageError};
pub use page::{PageDetector, PageHit, PageTemplate};
pub use perception::{dhash, hamming, is_loading, resize_rgb, state_id, H, W};
pub use template::{match_template, match_template_roi, MatchResult, Roi};

//! eye-core - perception thuan (port tu scripts/perception.py).
//!
//! Khong I/O he thong, de unit-test. Day la lop CV se chay trong onmyoji-eye.exe.
//! Moi ham co tinh "khop Python" deu duoc validate so voi goldens trong
//! `tests/golden_dhash.rs` (sinh tu Python, nguon su that).

pub mod image;
pub mod md5;
pub mod perception;

pub use image::{Image, ImageError};
pub use perception::{dhash, hamming, is_loading, state_id, H, W};

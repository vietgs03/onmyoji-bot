//! image.rs - bieu dien anh + decode PNG (thuan Rust).
//!
//! Anh luu noi bo theo thu tu **RGB** (3 byte/pixel, row-major). cv2.imread ben
//! Python luu BGR, nhung cong thuc xu ly (gray, HSV) deu tham chieu dung kenh
//! R/G/B nen ta chi can biet kenh nao la gi - khong phu thuoc thu tu luu.

use std::fmt;

/// Anh RGB8 trong bo nho (row-major, 3 byte/pixel).
#[derive(Clone)]
pub struct Image {
    pub width: usize,
    pub height: usize,
    /// RGB, do dai = width*height*3
    pub data: Vec<u8>,
}

#[derive(Debug)]
pub enum ImageError {
    Decode(String),
    Unsupported(String),
}

impl fmt::Display for ImageError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ImageError::Decode(s) => write!(f, "loi decode PNG: {s}"),
            ImageError::Unsupported(s) => write!(f, "PNG khong ho tro: {s}"),
        }
    }
}
impl std::error::Error for ImageError {}

impl Image {
    /// Tao anh tu buffer RGB co san (kiem tra kich thuoc).
    pub fn from_rgb(width: usize, height: usize, data: Vec<u8>) -> Result<Self, ImageError> {
        if data.len() != width * height * 3 {
            return Err(ImageError::Decode(format!(
                "buffer {} != {}*{}*3",
                data.len(),
                width,
                height
            )));
        }
        Ok(Image { width, height, data })
    }

    /// Decode PNG bytes -> Image RGB8. Ho tro Rgb8/Rgba8/Grayscale8 (+ palette qua EXPAND).
    pub fn decode_png(bytes: &[u8]) -> Result<Self, ImageError> {
        let mut decoder = png::Decoder::new(bytes);
        // EXPAND: palette -> RGB, grayscale <8bit -> 8bit. Giup robust voi nhieu PNG.
        decoder.set_transformations(png::Transformations::EXPAND);
        let mut reader = decoder
            .read_info()
            .map_err(|e| ImageError::Decode(e.to_string()))?;
        let mut buf = vec![0u8; reader.output_buffer_size()];
        let info = reader
            .next_frame(&mut buf)
            .map_err(|e| ImageError::Decode(e.to_string()))?;

        let (w, h) = (info.width as usize, info.height as usize);
        if info.bit_depth != png::BitDepth::Eight {
            return Err(ImageError::Unsupported(format!(
                "bit depth {:?} (chi ho tro 8-bit)",
                info.bit_depth
            )));
        }
        let src = &buf[..info.buffer_size()];
        let rgb = match info.color_type {
            png::ColorType::Rgb => src.to_vec(),
            png::ColorType::Rgba => {
                let mut out = Vec::with_capacity(w * h * 3);
                for px in src.chunks_exact(4) {
                    out.extend_from_slice(&px[..3]); // bo alpha
                }
                out
            }
            png::ColorType::Grayscale => {
                let mut out = Vec::with_capacity(w * h * 3);
                for &g in src {
                    out.extend_from_slice(&[g, g, g]);
                }
                out
            }
            png::ColorType::GrayscaleAlpha => {
                let mut out = Vec::with_capacity(w * h * 3);
                for px in src.chunks_exact(2) {
                    out.extend_from_slice(&[px[0], px[0], px[0]]);
                }
                out
            }
            other => {
                return Err(ImageError::Unsupported(format!("color type {other:?}")))
            }
        };
        Image::from_rgb(w, h, rgb)
    }

    /// (R,G,B) tai (x,y). Khong kiem tra bien (goi noi bo da dam bao).
    #[inline]
    pub fn rgb(&self, x: usize, y: usize) -> (u8, u8, u8) {
        let i = (y * self.width + x) * 3;
        (self.data[i], self.data[i + 1], self.data[i + 2])
    }
}

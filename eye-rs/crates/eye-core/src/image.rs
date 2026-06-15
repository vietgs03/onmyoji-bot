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

    /// Tao anh tu buffer **BGR** (vd raw tu LockBits Format24bppRgb cua Windows,
    /// hoac cv2 von BGR). Doi cho B<->R sang RGB noi bo. Kich thuoc = w*h*3.
    pub fn from_bgr(width: usize, height: usize, mut data: Vec<u8>) -> Result<Self, ImageError> {
        if data.len() != width * height * 3 {
            return Err(ImageError::Decode(format!(
                "buffer {} != {}*{}*3",
                data.len(),
                width,
                height
            )));
        }
        // BGR -> RGB tai cho: swap byte 0 va 2 cua moi pixel.
        for px in data.chunks_exact_mut(3) {
            px.swap(0, 2);
        }
        Ok(Image { width, height, data })
    }

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

    /// Encode RGB8 -> PNG bytes. Dung de LUU frame cho LLM agent NHIN (vision),
    /// hoac debug. Nen muc tieu thap (compression nhanh) vi day la hot path.
    pub fn encode_png(&self) -> Result<Vec<u8>, ImageError> {
        let mut out = Vec::new();
        {
            let mut enc = png::Encoder::new(&mut out, self.width as u32, self.height as u32);
            enc.set_color(png::ColorType::Rgb);
            enc.set_depth(png::BitDepth::Eight);
            // nen NHANH (Fast) - frame cho agent xem, khong can nho toi da.
            enc.set_compression(png::Compression::Fast);
            let mut writer = enc
                .write_header()
                .map_err(|e| ImageError::Decode(e.to_string()))?;
            writer
                .write_image_data(&self.data)
                .map_err(|e| ImageError::Decode(e.to_string()))?;
        }
        Ok(out)
    }

    /// Luu PNG ra duong dan (cho agent vision doc bang file path).
    pub fn save_png(&self, path: &str) -> Result<(), ImageError> {
        let bytes = self.encode_png()?;
        std::fs::write(path, bytes).map_err(|e| ImageError::Decode(e.to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn from_bgr_doi_kenh_dung() {
        // 2 pixel BGR: [B0,G0,R0, B1,G1,R1] -> rgb() phai tra (R,G,B)
        let bgr = vec![10, 20, 30, 40, 50, 60];
        let img = Image::from_bgr(2, 1, bgr).unwrap();
        assert_eq!(img.rgb(0, 0), (30, 20, 10)); // R=30,G=20,B=10
        assert_eq!(img.rgb(1, 0), (60, 50, 40));
    }

    #[test]
    fn from_bgr_bang_from_rgb_sau_swap() {
        // from_bgr(data) phai == from_rgb(data da swap B<->R)
        let bgr = vec![1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
        let rgb_eq = vec![3, 2, 1, 6, 5, 4, 9, 8, 7, 12, 11, 10];
        let a = Image::from_bgr(2, 2, bgr).unwrap();
        let b = Image::from_rgb(2, 2, rgb_eq).unwrap();
        assert_eq!(a.data, b.data);
    }

    #[test]
    fn from_bgr_sai_kich_thuoc_loi() {
        assert!(Image::from_bgr(2, 2, vec![0; 10]).is_err());
    }
}


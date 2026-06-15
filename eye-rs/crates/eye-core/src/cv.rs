//! cv.rs - cac phep CV co ban (port tu OpenCV, thuan Rust).
//!
//! Chi nhung gi detect_buttons can: HSV S-channel, threshold, morphology close,
//! connected-components (thay cho findContours RETR_EXTERNAL + boundingRect),
//! medianBlur, Sobel/Hough (cho icon tron).
//!
//! HSV S-channel da kiem chung khop cv2 BGR2HSV o muc bit (fixed-point hsv_shift=12).

use crate::image::Image;

/// Mat anh 1 kenh (u8), row-major.
pub struct Mat1 {
    pub w: usize,
    pub h: usize,
    pub data: Vec<u8>,
}

impl Mat1 {
    pub fn new(w: usize, h: usize) -> Self {
        Mat1 { w, h, data: vec![0u8; w * h] }
    }
    #[inline]
    pub fn at(&self, x: usize, y: usize) -> u8 {
        self.data[y * self.w + x]
    }
    #[inline]
    pub fn set(&mut self, x: usize, y: usize, v: u8) {
        self.data[y * self.w + x] = v;
    }
}

/// Bang sdiv cho HSV S-channel: sdiv[v] = round((255<<12)/v). Tinh 1 lan (const fn khong
/// lam duoc voi f64 nen tinh runtime, re).
fn sdiv_table() -> [i32; 256] {
    let mut t = [0i32; 256];
    for (v, slot) in t.iter_mut().enumerate().skip(1) {
        *slot = (((255i64 << 12) as f64) / v as f64).round() as i32;
    }
    t
}

/// S-channel cua HSV (BGR2HSV 8-bit OpenCV). Khop bit-level voi cv2.
pub fn hsv_saturation(img: &Image) -> Mat1 {
    let sdiv = sdiv_table();
    let mut s = Mat1::new(img.width, img.height);
    const HSV_SHIFT: i32 = 12;
    for i in 0..(img.width * img.height) {
        let base = i * 3;
        let r = img.data[base] as i32;
        let g = img.data[base + 1] as i32;
        let b = img.data[base + 2] as i32;
        let vmax = r.max(g).max(b);
        let vmin = r.min(g).min(b);
        let diff = vmax - vmin;
        let sat = if vmax == 0 {
            0
        } else {
            (diff * sdiv[vmax as usize] + (1 << (HSV_SHIFT - 1))) >> HSV_SHIFT
        };
        s.data[i] = sat.clamp(0, 255) as u8;
    }
    s
}

/// V-channel (max(R,G,B)) cua HSV.
pub fn hsv_value(img: &Image) -> Mat1 {
    let mut v = Mat1::new(img.width, img.height);
    for i in 0..(img.width * img.height) {
        let base = i * 3;
        let r = img.data[base];
        let g = img.data[base + 1];
        let b = img.data[base + 2];
        v.data[i] = r.max(g).max(b);
    }
    v
}

/// H-channel (Hue 0..180) cua HSV - can cho mask mau do (badge/close button).
/// Cong thuc OpenCV fixed-point.
pub fn hsv_full(img: &Image) -> (Mat1, Mat1, Mat1) {
    let sdiv = sdiv_table();
    // hdiv: h = ... dung bang chia tuong tu nhung theo 6 phan vung hue.
    let mut hmat = Mat1::new(img.width, img.height);
    let mut smat = Mat1::new(img.width, img.height);
    let mut vmat = Mat1::new(img.width, img.height);
    const HSV_SHIFT: i32 = 12;
    // hrange = 180; hscale = round(hrange<<hsv_shift / 6)? OpenCV: hdiv table per V.
    let hscale = ((180 << HSV_SHIFT) as f64 / 6.0).round() as i32;
    for i in 0..(img.width * img.height) {
        let base = i * 3;
        let r = img.data[base] as i32;
        let g = img.data[base + 1] as i32;
        let b = img.data[base + 2] as i32;
        let vmax = r.max(g).max(b);
        let vmin = r.min(g).min(b);
        let diff = vmax - vmin;
        let sat = if vmax == 0 {
            0
        } else {
            (diff * sdiv[vmax as usize] + (1 << (HSV_SHIFT - 1))) >> HSV_SHIFT
        };
        // hue
        let mut h = if diff == 0 {
            0
        } else {
            let hdiv = (((6 * 256 << HSV_SHIFT) as f64) / (6.0 * diff as f64)).round() as i32;
            // OpenCV: hdiv per diff. Dung cong thuc chuan:
            let hh = if vmax == r {
                (g - b) * hdiv
            } else if vmax == g {
                (b - r) * hdiv + (2 * 256 << HSV_SHIFT)
            } else {
                (r - g) * hdiv + (4 * 256 << HSV_SHIFT)
            };
            // scale ve 0..180
            (hh * hscale.max(1) / (256 << HSV_SHIFT).max(1) + (1 << (HSV_SHIFT - 1))) >> HSV_SHIFT
        };
        if h < 0 {
            h += 180;
        }
        hmat.data[i] = (h % 180).clamp(0, 179) as u8;
        smat.data[i] = sat.clamp(0, 255) as u8;
        vmat.data[i] = vmax as u8;
    }
    (hmat, smat, vmat)
}

/// threshold nhi phan: pixel > thr -> 255, nguoc lai 0 (khop cv2.THRESH_BINARY).
pub fn threshold_binary(src: &Mat1, thr: u8) -> Mat1 {
    let mut out = Mat1::new(src.w, src.h);
    for (o, &v) in out.data.iter_mut().zip(src.data.iter()) {
        *o = if v > thr { 255 } else { 0 };
    }
    out
}

/// Dilate hinh vuong (k x k) cho anh NHI PHAN (0/255) - O(N) khong phu thuoc k.
///
/// Tach roi (separable: ngang roi doc). Vi input nhi phan, dung PREFIX-SUM dem so
/// pixel foreground trong cua so [x0,x1]: >0 -> 255 (max). Tuong duong hoan toan
/// ban min/max O(N*k) cu nhung nhanh hon khi k lon (k=9: ~2x).
/// Tien dieu kien: src chi gom 0 hoac 255 (dau ra threshold_binary).
fn dilate(src: &Mat1, k: usize) -> Mat1 {
    morph_binary(src, k, true)
}

/// Erode hinh vuong (k x k) cho anh NHI PHAN (0/255) - O(N).
/// Cua so [x0,x1] foreground HET (count == do rong) -> 255, nguoc lai 0 (min).
fn erode(src: &Mat1, k: usize) -> Mat1 {
    morph_binary(src, k, false)
}

/// Loi chung cho dilate/erode nhi phan, separable, prefix-sum.
/// `dilate=true`: out=255 neu CO it nhat 1 foreground; `false` (erode): out=255 neu TOAN BO foreground.
fn morph_binary(src: &Mat1, k: usize, dilate: bool) -> Mat1 {
    let r = (k / 2) as isize;
    let (w, h) = (src.w, src.h);
    if w == 0 || h == 0 {
        return Mat1::new(w, h);
    }
    // pass NGANG: tung hang, prefix-sum so foreground.
    let mut tmp = Mat1::new(w, h);
    let mut pre = vec![0u32; w + 1];
    for y in 0..h {
        let row = &src.data[y * w..y * w + w];
        for x in 0..w {
            pre[x + 1] = pre[x] + (row[x] != 0) as u32;
        }
        let out = &mut tmp.data[y * w..y * w + w];
        for x in 0..w {
            let x0 = (x as isize - r).max(0) as usize;
            let x1 = (x as isize + r).min(w as isize - 1) as usize;
            let cnt = pre[x1 + 1] - pre[x0];
            let span = (x1 - x0 + 1) as u32;
            out[x] = if dilate {
                if cnt > 0 { 255 } else { 0 }
            } else if cnt == span {
                255
            } else {
                0
            };
        }
    }
    // pass DOC: tung cot, prefix-sum so foreground.
    let mut out = Mat1::new(w, h);
    let mut prec = vec![0u32; h + 1];
    for x in 0..w {
        for y in 0..h {
            prec[y + 1] = prec[y] + (tmp.data[y * w + x] != 0) as u32;
        }
        for y in 0..h {
            let y0 = (y as isize - r).max(0) as usize;
            let y1 = (y as isize + r).min(h as isize - 1) as usize;
            let cnt = prec[y1 + 1] - prec[y0];
            let span = (y1 - y0 + 1) as u32;
            out.data[y * w + x] = if dilate {
                if cnt > 0 { 255 } else { 0 }
            } else if cnt == span {
                255
            } else {
                0
            };
        }
    }
    out
}

/// morphologyEx CLOSE = dilate roi erode (kernel vuong k x k).
/// Luu y: OpenCV xu ly bien bang BORDER_CONSTANT mac dinh khac chut, nhung voi
/// anh game (bien it doi tuong) anh huong khong dang ke - validate bang coverage.
pub fn morph_close(src: &Mat1, k: usize) -> Mat1 {
    let d = dilate(src, k);
    erode(&d, k)
}

/// Bounding box + dien tich cua connected component.
#[derive(Clone, Copy, Debug)]
pub struct CompBox {
    pub x: usize,
    pub y: usize,
    pub w: usize,
    pub h: usize,
    pub area: usize, // so pixel thuc (khong phai w*h)
}

/// Connected-components (8 lien thong) tren anh nhi phan (>0 = foreground).
/// Tra danh sach bounding box - tuong duong findContours(RETR_EXTERNAL)+boundingRect
/// cho phan lon truong hop (validate bang coverage).
pub fn connected_components(src: &Mat1) -> Vec<CompBox> {
    let w = src.w;
    let h = src.h;
    let mut label = vec![0u32; w * h];
    let mut boxes: Vec<CompBox> = Vec::new();
    let mut stack: Vec<(usize, usize)> = Vec::new();
    let mut cur = 0u32;
    for sy in 0..h {
        for sx in 0..w {
            if src.at(sx, sy) == 0 || label[sy * w + sx] != 0 {
                continue;
            }
            cur += 1;
            // flood fill 8-conn
            let (mut minx, mut miny, mut maxx, mut maxy) = (sx, sy, sx, sy);
            let mut area = 0usize;
            stack.clear();
            stack.push((sx, sy));
            label[sy * w + sx] = cur;
            while let Some((x, y)) = stack.pop() {
                area += 1;
                if x < minx {
                    minx = x;
                }
                if x > maxx {
                    maxx = x;
                }
                if y < miny {
                    miny = y;
                }
                if y > maxy {
                    maxy = y;
                }
                let y0 = y.saturating_sub(1);
                let y1 = (y + 1).min(h - 1);
                let x0 = x.saturating_sub(1);
                let x1 = (x + 1).min(w - 1);
                for ny in y0..=y1 {
                    for nx in x0..=x1 {
                        if (nx != x || ny != y)
                            && src.at(nx, ny) > 0
                            && label[ny * w + nx] == 0
                        {
                            label[ny * w + nx] = cur;
                            stack.push((nx, ny));
                        }
                    }
                }
            }
            boxes.push(CompBox {
                x: minx,
                y: miny,
                w: maxx - minx + 1,
                h: maxy - miny + 1,
                area,
            });
        }
    }
    boxes
}

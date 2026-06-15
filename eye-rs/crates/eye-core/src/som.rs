//! som.rs - Set-of-Mark visual prompting cho LLM agent vision.
//!
//! Ky thuat chuan cua GUI agent hien dai: thay vi gui hint text (LLM hay doan sai
//! toa do), ta VE BOX DANH SO len chinh anh -> LLM chi chon SO, he thong tra toa
//! do CHINH XAC tu legend. LLM tap trung vao viec no gioi (hieu NGU NGHIA), khong
//! phai dinh vi pixel.
//!
//! Luong:
//!   detect element (button/icon) -> Mark{id, bbox, center}
//!   -> render box+so len anh -> PNG cho agent NHIN
//!   -> legend [{id,x,y,w,h}] de map so -> toa do click
//!
//! Khop triet ly self-learning: eye-rust (CV) biet O DAU (pixel chinh xac),
//! LLM (vision) hieu CAI GI (ngu nghia) -> tu gan label, KHONG hardcode template.

use crate::detect::{detect_buttons, Button};
use crate::image::Image;

/// 1 mark: phan tu clickable da danh so. Toa do theo client-area (khop click).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Mark {
    pub id: u32,
    /// bbox goc trai-tren + kich thuoc
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
    /// tam (toa do click)
    pub cx: i32,
    pub cy: i32,
    pub score: f32,
}

/// Mau ve (RGB).
const MARK_RGB: (u8, u8, u8) = (255, 40, 40); // do tuoi - noi bat tren game
const LABEL_BG: (u8, u8, u8) = (255, 220, 0); // nen so: vang
const LABEL_FG: (u8, u8, u8) = (0, 0, 0); // chu so: den

/// Sinh danh sach Mark tu detect_buttons (loc + danh so theo thu tu tren->duoi,
/// trai->phai de LLM doc tu nhien). Tra Vec<Mark>.
pub fn marks_from_buttons(img: &Image) -> Vec<Mark> {
    let btns = detect_buttons(img, false);
    sort_and_number(btns)
}

/// Sap xep button theo lo (row band) roi trai->phai, danh so 1..n.
fn sort_and_number(mut btns: Vec<Button>) -> Vec<Mark> {
    // gom theo hang: sap theo y truoc, x sau (band 60px de cung hang ~ gan nhau)
    const BAND: i32 = 60;
    btns.sort_by(|a, b| {
        let ra = a.cy / BAND;
        let rb = b.cy / BAND;
        ra.cmp(&rb).then(a.cx.cmp(&b.cx))
    });
    btns.into_iter()
        .enumerate()
        .map(|(i, b)| Mark {
            id: (i + 1) as u32,
            x: b.cx - b.w / 2,
            y: b.cy - b.h / 2,
            w: b.w,
            h: b.h,
            cx: b.cx,
            cy: b.cy,
            score: b.score,
        })
        .collect()
}

/// Ve 1 hinh chu nhat vien (do day `t`) mau `rgb` len anh.
fn draw_rect(img: &mut Image, x: i32, y: i32, w: i32, h: i32, rgb: (u8, u8, u8), t: i32) {
    let (iw, ih) = (img.width as i32, img.height as i32);
    for ty in 0..t {
        hline(img, x, x + w, y + ty, rgb, iw, ih);
        hline(img, x, x + w, y + h - 1 - ty, rgb, iw, ih);
    }
    for tx in 0..t {
        vline(img, y, y + h, x + tx, rgb, iw, ih);
        vline(img, y, y + h, x + w - 1 - tx, rgb, iw, ih);
    }
}

fn put_px(img: &mut Image, x: i32, y: i32, rgb: (u8, u8, u8), iw: i32, ih: i32) {
    if x < 0 || y < 0 || x >= iw || y >= ih {
        return;
    }
    let i = (y as usize * img.width + x as usize) * 3;
    img.data[i] = rgb.0;
    img.data[i + 1] = rgb.1;
    img.data[i + 2] = rgb.2;
}

fn hline(img: &mut Image, x0: i32, x1: i32, y: i32, rgb: (u8, u8, u8), iw: i32, ih: i32) {
    for x in x0..x1 {
        put_px(img, x, y, rgb, iw, ih);
    }
}

fn vline(img: &mut Image, y0: i32, y1: i32, x: i32, rgb: (u8, u8, u8), iw: i32, ih: i32) {
    for y in y0..y1 {
        put_px(img, x, y, rgb, iw, ih);
    }
}

/// Ve mot hinh chu nhat dac (fill).
fn fill_rect(img: &mut Image, x: i32, y: i32, w: i32, h: i32, rgb: (u8, u8, u8)) {
    let (iw, ih) = (img.width as i32, img.height as i32);
    for yy in y..y + h {
        for xx in x..x + w {
            put_px(img, xx, yy, rgb, iw, ih);
        }
    }
}

// Font 3x5 bitmap cho chu so 0-9 (de ve so mark, khong phu thuoc font he thong).
// Moi so = 5 hang, moi hang 3 bit (cot trai->phai).
const DIGITS: [[u8; 5]; 10] = [
    [0b111, 0b101, 0b101, 0b101, 0b111], // 0
    [0b010, 0b110, 0b010, 0b010, 0b111], // 1
    [0b111, 0b001, 0b111, 0b100, 0b111], // 2
    [0b111, 0b001, 0b111, 0b001, 0b111], // 3
    [0b101, 0b101, 0b111, 0b001, 0b001], // 4
    [0b111, 0b100, 0b111, 0b001, 0b111], // 5
    [0b111, 0b100, 0b111, 0b101, 0b111], // 6
    [0b111, 0b001, 0b010, 0b010, 0b010], // 7
    [0b111, 0b101, 0b111, 0b101, 0b111], // 8
    [0b111, 0b101, 0b111, 0b001, 0b111], // 9
];

/// Ve 1 chu so tai (x,y) voi he so phong to `sc` (pixel/cell).
fn draw_digit(img: &mut Image, d: u8, x: i32, y: i32, sc: i32, rgb: (u8, u8, u8)) {
    let (iw, ih) = (img.width as i32, img.height as i32);
    let pat = &DIGITS[(d % 10) as usize];
    for (ry, row) in pat.iter().enumerate() {
        for cx in 0..3 {
            if row & (1 << (2 - cx)) != 0 {
                for sy in 0..sc {
                    for sx in 0..sc {
                        put_px(
                            img,
                            x + cx * sc + sx,
                            y + ry as i32 * sc + sy,
                            rgb,
                            iw,
                            ih,
                        );
                    }
                }
            }
        }
    }
}

/// Ve nhan so (vd "12") tren nen, goc tren-trai cua bbox mark.
fn draw_label(img: &mut Image, n: u32, x: i32, y: i32) {
    let sc = 3; // phong to 3x -> moi so rong 9px, cao 15px
    let digits: Vec<u8> = n.to_string().bytes().map(|b| b - b'0').collect();
    let dw = 3 * sc + 1; // be rong 1 so + khoang cach
    let pad = 2;
    let box_w = dw * digits.len() as i32 + pad;
    let box_h = 5 * sc + pad * 2;
    // nen nhan (vang) ngay tren bbox; neu sat mep tren thi day xuong trong box
    let ly = if y - box_h >= 0 { y - box_h } else { y };
    fill_rect(img, x, ly, box_w, box_h, LABEL_BG);
    let mut dx = x + pad;
    for d in digits {
        draw_digit(img, d, dx, ly + pad, sc, LABEL_FG);
        dx += dw;
    }
}

/// Render Set-of-Mark: ve box + so cho moi mark len BAN SAO cua anh. Tra anh moi.
pub fn render_marks(img: &Image, marks: &[Mark]) -> Image {
    let mut out = img.clone();
    for m in marks {
        draw_rect(&mut out, m.x, m.y, m.w, m.h, MARK_RGB, 2);
        draw_label(&mut out, m.id, m.x, m.y);
    }
    out
}

/// Tien ich: tu anh -> (marks, anh da annotate). Dung cho agent vision.
pub fn annotate(img: &Image) -> (Vec<Mark>, Image) {
    let marks = marks_from_buttons(img);
    let annotated = render_marks(img, &marks);
    (marks, annotated)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn blank(w: usize, h: usize) -> Image {
        Image::from_rgb(w, h, vec![30u8; w * h * 3]).unwrap()
    }

    #[test]
    fn danh_so_theo_hang_roi_cot() {
        // 3 button: 2 hang tren (trai, phai) + 1 hang duoi
        let btns = vec![
            Button { cx: 200, cy: 100, w: 40, h: 40, score: 0.9 }, // hang 1 phai
            Button { cx: 50, cy: 100, w: 40, h: 40, score: 0.8 },  // hang 1 trai
            Button { cx: 100, cy: 400, w: 40, h: 40, score: 0.7 }, // hang 2
        ];
        let marks = sort_and_number(btns);
        assert_eq!(marks.len(), 3);
        // mark 1 = hang1-trai (50,100), mark 2 = hang1-phai (200,100), mark 3 = hang2
        assert_eq!((marks[0].cx, marks[0].id), (50, 1));
        assert_eq!((marks[1].cx, marks[1].id), (200, 2));
        assert_eq!((marks[2].cy, marks[2].id), (400, 3));
    }

    #[test]
    fn render_khong_doi_kich_thuoc() {
        let img = blank(100, 80);
        let marks = vec![Mark { id: 1, x: 10, y: 10, w: 20, h: 20, cx: 20, cy: 20, score: 0.9 }];
        let out = render_marks(&img, &marks);
        assert_eq!((out.width, out.height), (100, 80));
        // co pixel mau do (vien mark) o dau do
        let has_red = out.data.chunks_exact(3).any(|p| p[0] > 200 && p[1] < 100);
        assert!(has_red, "phai co vien mark mau do");
    }

    #[test]
    fn draw_digit_ve_dung_pixel() {
        let mut img = blank(30, 30);
        draw_digit(&mut img, 1, 5, 5, 2, (255, 255, 255));
        // so 1 phai co it nhat vai pixel trang
        let white = img.data.chunks_exact(3).filter(|p| p[0] == 255).count();
        assert!(white > 0, "phai ve duoc chu so");
    }
}

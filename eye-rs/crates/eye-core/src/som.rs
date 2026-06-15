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

use crate::cv;
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

/// Sinh danh sach Mark tu detect element (loc + danh so theo thu tu tren->duoi,
/// trai->phai de LLM doc tu nhien). Tra Vec<Mark>.
///
/// Detect element cho SoM uu tien COVERAGE (bat het cai clickable) hon la precision:
///   1. detect_buttons (icon tron + nut mau) - chinh xac cho nut
///   2. vung SANG/tuong phan cao (icon/chu tren nen toi) - bat menu/panel
/// Gop NMS, loc kich thuoc UI hop ly.
pub fn marks_from_buttons(img: &Image) -> Vec<Mark> {
    let mut cands: Vec<Button> = detect_buttons(img, false);
    cands.extend(bright_region_elements(img));
    let merged = nms_buttons(cands, 0.45);
    sort_and_number(merged, img.width as i32, img.height as i32)
}

/// Element tu vung SANG/tuong phan (value channel cao) - bat icon/chu/panel ma
/// detect_buttons (tron + saturation) bo sot. Loc theo kich thuoc UI element.
fn bright_region_elements(img: &Image) -> Vec<Button> {
    let val = cv::hsv_value(img);
    // nguong sang: element UI (chu/icon trang, panel sang) noi tren nen toi game
    let th = cv::threshold_binary(&val, 170);
    // close de gom net chu/icon roi rac thanh 1 khoi
    let closed = cv::morph_close(&th, 11);
    let comps = cv::connected_components(&closed);
    // tran dien tich = 8% man -> loai art nhan vat/nen lon (false positive)
    let max_area = (img.width * img.height) as i32 * 8 / 100;
    let mut out = Vec::new();
    for c in comps {
        let (w, h) = (c.w as i32, c.h as i32);
        let area = w * h;
        let aspect = w as f32 / h.max(1) as f32;
        // fill ratio: pixel thuc / bbox -> loai vung rong (vien)
        let fill = c.area as f32 / area.max(1) as f32;
        if (700..max_area).contains(&area) && (0.18..7.0).contains(&aspect) && fill > 0.30 {
            out.push(Button {
                cx: c.x as i32 + w / 2,
                cy: c.y as i32 + h / 2,
                w,
                h,
                score: 0.6,
            });
        }
    }
    out
}

/// NMS tren Button (theo score giam) - gop ung vien trung tu nhieu detector.
fn nms_buttons(mut bs: Vec<Button>, iou_thr: f32) -> Vec<Button> {
    bs.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
    let mut keep: Vec<Button> = Vec::new();
    for b in bs {
        if keep.iter().all(|k| iou_btn(&b, k) < iou_thr) {
            keep.push(b);
        }
    }
    keep
}

fn iou_btn(a: &Button, b: &Button) -> f32 {
    let (ax0, ay0) = (a.cx - a.w / 2, a.cy - a.h / 2);
    let (bx0, by0) = (b.cx - b.w / 2, b.cy - b.h / 2);
    let x1 = ax0.max(bx0);
    let y1 = ay0.max(by0);
    let x2 = (ax0 + a.w).min(bx0 + b.w);
    let y2 = (ay0 + a.h).min(by0 + b.h);
    let inter = (x2 - x1).max(0) * (y2 - y1).max(0);
    if inter == 0 {
        return 0.0;
    }
    let union = a.w * a.h + b.w * b.h - inter;
    inter as f32 / union.max(1) as f32
}

/// Sap xep button theo lo (row band) roi trai->phai, danh so 1..n.
/// CLAMP bbox vao trong anh (tranh toa do am/tran mep -> nhan ve sai cho).
fn sort_and_number(mut btns: Vec<Button>, iw: i32, ih: i32) -> Vec<Mark> {
    // gom theo hang: sap theo y truoc, x sau (band 60px de cung hang ~ gan nhau)
    const BAND: i32 = 60;
    btns.sort_by(|a, b| {
        let ra = a.cy / BAND;
        let rb = b.cy / BAND;
        ra.cmp(&rb).then(a.cx.cmp(&b.cx))
    });
    btns.into_iter()
        .enumerate()
        .map(|(i, b)| {
            // clamp bbox vao [0,iw)x[0,ih) - element co the tran mep man
            let mut x = b.cx - b.w / 2;
            let mut y = b.cy - b.h / 2;
            let mut w = b.w;
            let mut h = b.h;
            if x < 0 {
                w += x; // thu hep theo phan bi cat
                x = 0;
            }
            if y < 0 {
                h += y;
                y = 0;
            }
            if x + w > iw {
                w = iw - x;
            }
            if y + h > ih {
                h = ih - y;
            }
            w = w.max(1);
            h = h.max(1);
            Mark {
                id: (i + 1) as u32,
                x,
                y,
                w,
                h,
                cx: b.cx.clamp(0, iw - 1),
                cy: b.cy.clamp(0, ih - 1),
                score: b.score,
            }
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

/// Ve nhan so cho 1 mark. Nhan dat trong/canh bbox, CLAMP vao trong anh de
/// khong bi cat mep. Tra (lx,ly,box_w,box_h) da ve (de tranh chong neu can).
fn draw_label(img: &mut Image, n: u32, bx: i32, by: i32, _bw: i32, bh: i32) {
    let sc = 3; // phong to 3x -> moi so rong 9px, cao 15px
    let digits: Vec<u8> = n.to_string().bytes().map(|b| b - b'0').collect();
    let dw = 3 * sc + 1; // be rong 1 so + khoang cach
    let pad = 2;
    let box_w = dw * digits.len() as i32 + pad;
    let box_h = 5 * sc + pad * 2;
    let (iw, ih) = (img.width as i32, img.height as i32);
    // dat nhan o goc tren-trai cua bbox (trong box neu vua, neu khong day ra ngoai
    // tren). Sau do CLAMP toan bo nhan vao trong anh.
    let mut lx = bx;
    let mut ly = if by - box_h >= 0 { by - box_h } else { by };
    // neu box du cao, dat nhan ben trong goc tren de khong che element ke ben
    if bh >= box_h && by - box_h < 0 {
        ly = by;
    }
    lx = lx.clamp(0, (iw - box_w).max(0));
    ly = ly.clamp(0, (ih - box_h).max(0));
    fill_rect(img, lx, ly, box_w, box_h, LABEL_BG);
    let mut dx = lx + pad;
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
        draw_label(&mut out, m.id, m.x, m.y, m.w, m.h);
    }
    out
}

/// Tien ich: tu anh -> (marks, anh da annotate). Dung cho agent vision.
pub fn annotate(img: &Image) -> (Vec<Mark>, Image) {
    let marks = marks_from_buttons(img);
    let annotated = render_marks(img, &marks);
    (marks, annotated)
}

/// Ket qua snap: toa do tinh (snapped) + nguon.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Snap {
    pub x: i32,
    pub y: i32,
    /// "mark" = trung tam element CV gan nhat; "raw" = giu nguyen (khong co element gan)
    pub snapped: bool,
    /// khoang cach tu diem tho toi element snapped (px)
    pub dist: f32,
}

/// SNAP toa do THO cua agent ve TAM element gan nhat (trong ban kinh `radius`).
/// Dung khi agent uoc toa do tu anh -> snap ve element that de click chinh xac.
///
/// 2 nguon (uu tien giam dan):
///   1. mark gan nhat (element CV da detect) trong radius / chua diem.
///   2. neu khong co mark: snap ve TAM cum tuong phan cuc bo quanh diem (bat ca
///      element CV SOT nhu Explore/Summon - khong gioi han marks).
///   3. khong co gi: giu nguyen toa do tho (raw).
pub fn snap_to_element(img: &Image, rx: i32, ry: i32, radius: i32) -> Snap {
    let marks = marks_from_buttons(img);
    let mut best: Option<(f32, &Mark)> = None;
    for m in &marks {
        // trong bbox -> distance = 0 (uu tien tuyet doi)
        let inside = rx >= m.x && rx < m.x + m.w && ry >= m.y && ry < m.y + m.h;
        let dx = (rx - m.cx) as f32;
        let dy = (ry - m.cy) as f32;
        let d = if inside { 0.0 } else { (dx * dx + dy * dy).sqrt() };
        if d <= radius as f32 && best.map(|(bd, _)| d < bd).unwrap_or(true) {
            best = Some((d, m));
        }
    }
    if let Some((d, m)) = best {
        return Snap {
            x: m.cx,
            y: m.cy,
            snapped: true,
            dist: d,
        };
    }
    // khong co mark gan -> snap ve tam cum tuong phan cuc bo (element CV sot)
    if let Some((sx, sy)) = local_contrast_center(img, rx, ry, radius) {
        let dx = (rx - sx) as f32;
        let dy = (ry - sy) as f32;
        return Snap {
            x: sx,
            y: sy,
            snapped: true,
            dist: (dx * dx + dy * dy).sqrt(),
        };
    }
    Snap {
        x: rx.clamp(0, img.width as i32 - 1),
        y: ry.clamp(0, img.height as i32 - 1),
        snapped: false,
        dist: f32::INFINITY,
    }
}

/// Tam "khoi luong" cua tuong phan cuc bo quanh (rx,ry) trong cua so `radius`.
/// Tinh gradient (|dx|+|dy| tho) lam trong so -> centroid. Bat element CV sot.
/// None neu vung phang (khong co element -> khong nen snap).
fn local_contrast_center(img: &Image, rx: i32, ry: i32, radius: i32) -> Option<(i32, i32)> {
    let (iw, ih) = (img.width as i32, img.height as i32);
    let x0 = (rx - radius).max(1);
    let y0 = (ry - radius).max(1);
    let x1 = (rx + radius).min(iw - 2);
    let y1 = (ry + radius).min(ih - 2);
    if x1 <= x0 || y1 <= y0 {
        return None;
    }
    let lum = |x: i32, y: i32| -> i32 {
        let i = ((y as usize) * img.width + x as usize) * 3;
        img.data[i] as i32 + img.data[i + 1] as i32 + img.data[i + 2] as i32
    };
    let mut sw = 0f64;
    let mut sx = 0f64;
    let mut sy = 0f64;
    for y in y0..=y1 {
        for x in x0..=x1 {
            let gx = (lum(x + 1, y) - lum(x - 1, y)).abs();
            let gy = (lum(x, y + 1) - lum(x, y - 1)).abs();
            let g = (gx + gy) as f64;
            sw += g;
            sx += g * x as f64;
            sy += g * y as f64;
        }
    }
    // nguong: tong gradient phai du lon (co element), tranh snap vao vung phang.
    // vung phang gradient ~0; element (vien + text/texture) gradient lon. area*4
    // du de loai phang ma van bat element vien mong.
    let area = ((x1 - x0 + 1) * (y1 - y0 + 1)) as f64;
    if sw < area * 4.0 {
        return None; // vung phang -> khong snap
    }
    Some(((sx / sw).round() as i32, (sy / sw).round() as i32))
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
        let marks = sort_and_number(btns, 1136, 640);
        assert_eq!(marks.len(), 3);
        // mark 1 = hang1-trai (50,100), mark 2 = hang1-phai (200,100), mark 3 = hang2
        assert_eq!((marks[0].cx, marks[0].id), (50, 1));
        assert_eq!((marks[1].cx, marks[1].id), (200, 2));
        assert_eq!((marks[2].cy, marks[2].id), (400, 3));
    }

    #[test]
    fn clamp_bbox_tran_mep() {
        // button tran mep tren-trai: cx=10,cy=10,w=100,h=100 -> bbox (-40,-40)..
        let btns = vec![Button { cx: 10, cy: 10, w: 100, h: 100, score: 0.9 }];
        let marks = sort_and_number(btns, 1136, 640);
        let m = marks[0];
        assert!(m.x >= 0 && m.y >= 0, "bbox phai clamp >=0: {m:?}");
        assert!(m.x + m.w <= 1136 && m.y + m.h <= 640, "bbox trong anh: {m:?}");
        assert!(m.cx >= 0 && m.cy >= 0, "tam trong anh");
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

    #[test]
    fn snap_vung_phang_giu_raw() {
        // anh phang (khong element) -> snap giu nguyen toa do tho
        let img = blank(200, 200);
        let s = snap_to_element(&img, 100, 100, 40);
        assert!(!s.snapped, "vung phang khong nen snap: {s:?}");
        assert_eq!((s.x, s.y), (100, 100));
    }

    #[test]
    fn snap_ve_tam_element_sang() {
        // nen toi + 1 o sang 20x20 tai (120..140, 60..80) -> tam (130,70).
        // diem tho (110,55) gan do -> snap ve ~tam o sang.
        let mut d = vec![20u8; 200 * 200 * 3];
        for y in 60..80 {
            for x in 120..140 {
                let i = (y * 200 + x) * 3;
                d[i] = 240;
                d[i + 1] = 240;
                d[i + 2] = 240;
            }
        }
        let img = Image::from_rgb(200, 200, d).unwrap();
        let s = snap_to_element(&img, 110, 55, 50);
        assert!(s.snapped, "phai snap vao element sang: {s:?}");
        // tam snap nam trong/gan o sang (120..140, 60..80)
        assert!((110..150).contains(&s.x) && (50..90).contains(&s.y), "snap sai: {s:?}");
    }
}

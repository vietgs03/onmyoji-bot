//! detect.rs - detect_buttons (port tu perception.detect_buttons).
//!
//! Tim cac UNG VIEN NUT (clickable) bang dac trung HINH HOC + MAU, KHONG template:
//!   1. icon tron (Hough circles) - cac nut ria man (chat/mail/settings/modes)
//!   2. vung saturation cao (nut mau cam/do dac trung Onmyoji)
//! Gop trung lap bang NMS. Tra (cx, cy, w, h, score).
//!
//! LUU Y robust: detect_buttons CHI dung khi EXPLORE man moi. Khi navigate, bot
//! replay toa do da hoc trong world.json (khong re-detect). Vi the tieu chi dung la
//! COVERAGE/recall, khong phai bit-exact voi OpenCV.

use crate::cv;
use crate::image::Image;
use crate::perception::{H, W};

/// 1 ung vien nut: tam (cx,cy), kich thuoc (w,h), diem tin cay score.
#[derive(Clone, Copy, Debug)]
pub struct Button {
    pub cx: i32,
    pub cy: i32,
    pub w: i32,
    pub h: i32,
    pub score: f32,
}

/// Hop ung vien (x,y,w,h,score) truoc khi quy ve tam - dung chung giua cac detector.
#[derive(Clone, Copy)]
pub struct BoxCandidate {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
    pub s: f32,
}

type Box = BoxCandidate;

fn iou(a: &Box, b: &Box) -> f32 {
    let x1 = a.x.max(b.x);
    let y1 = a.y.max(b.y);
    let x2 = (a.x + a.w).min(b.x + b.w);
    let y2 = (a.y + a.h).min(b.y + b.h);
    let inter = (x2 - x1).max(0) * (y2 - y1).max(0);
    if inter == 0 {
        return 0.0;
    }
    let union = a.w * a.h + b.w * b.h - inter;
    inter as f32 / union as f32
}

/// Non-max suppression theo score giam dan (khop perception._nms).
fn nms(mut boxes: Vec<Box>, iou_thr: f32) -> Vec<Box> {
    boxes.sort_by(|a, b| b.s.partial_cmp(&a.s).unwrap_or(std::cmp::Ordering::Equal));
    let mut keep: Vec<Box> = Vec::new();
    for b in boxes {
        if keep.iter().all(|k| iou(&b, k) < iou_thr) {
            keep.push(b);
        }
    }
    keep
}

/// Ung vien tu vung SATURATION cao (nut mau dac trung).
/// Khop perception.detect_buttons phan 2.
fn saturation_candidates(img: &Image) -> Vec<Box> {
    let sat = cv::hsv_saturation(img);
    let th = cv::threshold_binary(&sat, 120);
    let closed = cv::morph_close(&th, 9);
    let comps = cv::connected_components(&closed);
    let mut out = Vec::new();
    for c in comps {
        let area = (c.w * c.h) as i32; // boundingRect area (khop cv2)
        let aspect = c.w as f32 / c.h.max(1) as f32;
        if (900..60000).contains(&area) && aspect > 0.25 && aspect < 6.0 {
            out.push(Box {
                x: c.x as i32,
                y: c.y as i32,
                w: c.w as i32,
                h: c.h as i32,
                s: 0.7,
            });
        }
    }
    out
}

/// detect_buttons: tra danh sach Button (cx,cy,w,h,score) sap theo score giam.
/// `suppress_center=true` ha diem cac box roi vao vung nhan vat (HOME).
pub fn detect_buttons(img: &Image, suppress_center: bool) -> Vec<Button> {
    let mut cands: Vec<Box> = Vec::new();

    // 1) icon tron (Hough circles)
    cands.extend(crate::hough::hough_circle_candidates(img));

    // 2) saturation
    cands.extend(saturation_candidates(img));

    let boxes = nms(cands, 0.35);

    // vung nhieu (nhan vat san HOME)
    const NOISE: (i32, i32, i32, i32) = (250, 130, 880, 540);

    let mut out: Vec<Button> = Vec::new();
    for b in boxes {
        let cx = b.x + b.w / 2;
        let cy = b.y + b.h / 2;
        if !(0..W as i32).contains(&cx) || !(0..H as i32).contains(&cy) {
            continue;
        }
        let mut s = b.s;
        if suppress_center {
            let (nx0, ny0, nx1, ny1) = NOISE;
            if cx >= nx0 && cx <= nx1 && cy >= ny0 && cy <= ny1 {
                s *= 0.3;
            }
        }
        out.push(Button {
            cx,
            cy,
            w: b.w,
            h: b.h,
            score: (s * 100.0).round() / 100.0,
        });
    }
    out.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
    out
}

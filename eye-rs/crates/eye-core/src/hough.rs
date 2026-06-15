//! hough.rs - Hough circle detection (port HOUGH_GRADIENT cua OpenCV).
//!
//! perception.py goi:
//!   blur = medianBlur(gray, 5)
//!   HoughCircles(blur, HOUGH_GRADIENT, dp=1.2, minDist=30, param1=120, param2=40,
//!                minRadius=14, maxRadius=55)
//!
//! HOUGH_GRADIENT: Canny(param1/2, param1) -> tai moi edge pixel, vote doc theo huong
//! gradient (Sobel) tu minR den maxR vao accumulator do phan giai dp -> tim tam la
//! local-max > param2 -> moi tam chon ban kinh nhieu vote nhat.
//!
//! KHONG bit-exact voi OpenCV (Canny hysteresis + thu tu vote khac chut), nhung muc
//! tieu la COVERAGE cac icon tron. Validate bang test coverage.

use crate::cv::Mat1;
use crate::detect::Button;
use crate::image::Image;

/// Tham so HoughCircles dung trong perception.py.
const DP: f32 = 1.2;
const MIN_DIST: f32 = 30.0;
const PARAM1: f32 = 120.0; // Canny high
const PARAM2: i32 = 40; // nguong accumulator
const MIN_RADIUS: i32 = 14;
const MAX_RADIUS: i32 = 55;

/// Gray (BGR2GRAY fixed-point) -> Mat1.
fn to_gray(img: &Image) -> Mat1 {
    let mut g = Mat1::new(img.width, img.height);
    for i in 0..(img.width * img.height) {
        let base = i * 3;
        let r = img.data[base] as i32;
        let gr = img.data[base + 1] as i32;
        let b = img.data[base + 2] as i32;
        g.data[i] = (((r * 4899 + gr * 9617 + b * 1868 + 8192) >> 14).clamp(0, 255)) as u8;
    }
    g
}

/// medianBlur kernel 5x5 (khop cv2.medianBlur ksize=5). Bien: nhan ban (replicate).
///
/// Thuat toan Huang (sliding histogram): thay vi sort 25 phan tu MOI pixel
/// (cham), giu 1 histogram 256-bin truot ngang. Moi buoc chi them/bot 1 cot (5px)
/// va dich trung vi (mdn) vai bac. Ket qua BIT-EXACT voi ban sort cu (cung la
/// thong ke thu tu thu 13), nhung nhanh hon nhieu (73ms -> ~10ms).
fn median_blur5(src: &Mat1) -> Mat1 {
    let (w, h) = (src.w, src.h);
    let mut out = Mat1::new(w, h);
    if w == 0 || h == 0 {
        return out;
    }
    const TH: i32 = 13; // trung vi cua 25 = thong ke thu tu thu 13
    let wi = w as i32;
    let hi = h as i32;
    let mut hist = [0i32; 256];
    for y in 0..h {
        // 5 hang trong cua so (clamp doc theo BORDER_REPLICATE)
        let ry = [
            (y as i32 - 2).clamp(0, hi - 1) as usize,
            (y as i32 - 1).clamp(0, hi - 1) as usize,
            y,
            (y as i32 + 1).clamp(0, hi - 1) as usize,
            (y as i32 + 2).clamp(0, hi - 1) as usize,
        ];
        // reset histogram
        hist.iter_mut().for_each(|c| *c = 0);
        // nap cua so tai x=0: cac cot clamp(-2..2)
        for dx in -2i32..=2 {
            let cx = dx.clamp(0, wi - 1) as usize;
            for &yy in &ry {
                hist[src.at(cx, yy) as usize] += 1;
            }
        }
        // trung vi ban dau (di tu 0 len)
        let mut mdn: i32 = 0;
        let mut ltcount: i32 = 0; // so pixel < mdn
        while ltcount + hist[mdn as usize] < TH {
            ltcount += hist[mdn as usize];
            mdn += 1;
        }
        out.set(0, y, mdn as u8);

        // truot ngang: x = 1..w-1
        for x in 1..w {
            let xi = x as i32;
            // bot cot roi khoi cua so = clamp(x-3); them cot moi = clamp(x+2)
            let lcol = (xi - 3).clamp(0, wi - 1) as usize;
            let rcol = (xi + 2).clamp(0, wi - 1) as usize;
            for &yy in &ry {
                let v = src.at(lcol, yy) as i32;
                hist[v as usize] -= 1;
                if v < mdn {
                    ltcount -= 1;
                }
                let v2 = src.at(rcol, yy) as i32;
                hist[v2 as usize] += 1;
                if v2 < mdn {
                    ltcount += 1;
                }
            }
            // dich trung vi ve dung vi tri thu 13
            while ltcount >= TH {
                mdn -= 1;
                ltcount -= hist[mdn as usize];
            }
            while ltcount + hist[mdn as usize] < TH {
                ltcount += hist[mdn as usize];
                mdn += 1;
            }
            out.set(x, y, mdn as u8);
        }
    }
    out
}

/// Sobel 3x3 -> (dx, dy) dang i16 (BORDER_REPLICATE).
fn sobel(src: &Mat1) -> (Vec<i32>, Vec<i32>) {
    let (w, h) = (src.w, src.h);
    let mut dx = vec![0i32; w * h];
    let mut dy = vec![0i32; w * h];
    let at = |x: i32, y: i32| -> i32 {
        let xx = x.clamp(0, w as i32 - 1) as usize;
        let yy = y.clamp(0, h as i32 - 1) as usize;
        src.at(xx, yy) as i32
    };
    for y in 0..h as i32 {
        for x in 0..w as i32 {
            let p00 = at(x - 1, y - 1);
            let p01 = at(x, y - 1);
            let p02 = at(x + 1, y - 1);
            let p10 = at(x - 1, y);
            let p12 = at(x + 1, y);
            let p20 = at(x - 1, y + 1);
            let p21 = at(x, y + 1);
            let p22 = at(x + 1, y + 1);
            let gx = (p02 + 2 * p12 + p22) - (p00 + 2 * p10 + p20);
            let gy = (p20 + 2 * p21 + p22) - (p00 + 2 * p01 + p02);
            dx[(y as usize) * w + x as usize] = gx;
            dy[(y as usize) * w + x as usize] = gy;
        }
    }
    (dx, dy)
}

/// Canny don gian (L1 magnitude + double-threshold + hysteresis) dung dx,dy co san.
/// low = high/2 (theo perception: param1=high, OpenCV mac dinh low=high/2).
fn canny_edges(dx: &[i32], dy: &[i32], w: usize, h: usize, high: f32) -> Mat1 {
    let low = high / 2.0;
    let mag: Vec<f32> = dx
        .iter()
        .zip(dy.iter())
        .map(|(&gx, &gy)| ((gx * gx + gy * gy) as f32).sqrt())
        .collect();

    // non-maximum suppression theo huong gradient
    let mut strong = vec![0u8; w * h]; // 0 = none, 1 = weak, 2 = strong
    for y in 1..h - 1 {
        for x in 1..w - 1 {
            let i = y * w + x;
            let m = mag[i];
            if m < low {
                continue;
            }
            let gx = dx[i] as f32;
            let gy = dy[i] as f32;
            // huong -> chon 2 lang gieng theo octant
            let (ax, ay) = (gx.abs(), gy.abs());
            let (m1, m2);
            if ax >= ay {
                // ngang chiem uu the
                let slope = if ax == 0.0 { 0.0 } else { ay / ax };
                let sign = if (gx > 0.0) == (gy > 0.0) { 1i32 } else { -1i32 };
                let a = mag[i + 1];
                let b = mag[i - 1];
                let c = mag[(y as i32 + sign) as usize * w + x + 1];
                let d = mag[(y as i32 - sign) as usize * w + x - 1];
                m1 = a * (1.0 - slope) + c * slope;
                m2 = b * (1.0 - slope) + d * slope;
            } else {
                let slope = if ay == 0.0 { 0.0 } else { ax / ay };
                let sign = if (gx > 0.0) == (gy > 0.0) { 1i32 } else { -1i32 };
                let a = mag[(y + 1) * w + x];
                let b = mag[(y - 1) * w + x];
                let c = mag[(y + 1) * w + (x as i32 + sign) as usize];
                let d = mag[(y - 1) * w + (x as i32 - sign) as usize];
                m1 = a * (1.0 - slope) + c * slope;
                m2 = b * (1.0 - slope) + d * slope;
            }
            if m >= m1 && m >= m2 {
                strong[i] = if m >= high { 2 } else { 1 };
            }
        }
    }

    // hysteresis: weak noi voi strong -> strong
    let mut out = Mat1::new(w, h);
    let mut stack: Vec<usize> = Vec::new();
    for i in 0..w * h {
        if strong[i] == 2 {
            out.data[i] = 255;
            stack.push(i);
        }
    }
    while let Some(i) = stack.pop() {
        let x = i % w;
        let y = i / w;
        let y0 = y.saturating_sub(1);
        let y1 = (y + 1).min(h - 1);
        let x0 = x.saturating_sub(1);
        let x1 = (x + 1).min(w - 1);
        for ny in y0..=y1 {
            for nx in x0..=x1 {
                let j = ny * w + nx;
                if strong[j] == 1 && out.data[j] == 0 {
                    out.data[j] = 255;
                    stack.push(j);
                }
            }
        }
    }
    out
}

/// Hough gradient: tra danh sach (cx, cy, r) cac vong tron tim duoc.
fn hough_gradient(gray: &Mat1) -> Vec<(i32, i32, i32)> {
    let (w, h) = (gray.w, gray.h);
    let (dx, dy) = sobel(gray);
    let edges = canny_edges(&dx, &dy, w, h, PARAM1);

    // accumulator do phan giai dp (1/dp)
    let inv_dp = 1.0 / DP;
    let aw = ((w as f32 * inv_dp).ceil() as usize).max(1);
    let ah = ((h as f32 * inv_dp).ceil() as usize).max(1);
    let mut accum = vec![0i32; aw * ah];

    // vote: tai moi edge pixel, di doc gradient tu minR den maxR (ca 2 chieu).
    // Toi uu: buoc bang FIXED-POINT i64 (16 bit phan le) thay vi float -> tranh
    // 2 lan float->int (cvttss2si) moi buoc, von la phan dat nhat. Toa do vote
    // luon duong nen (q >> 16) = floor = truncate, khop ban float cu.
    const FP: i64 = 16;
    const ONE: f32 = 65536.0;
    let aw_i = aw as i32;
    let ah_i = ah as i32;
    for y in 0..h {
        for x in 0..w {
            let i = y * w + x;
            if edges.data[i] == 0 {
                continue;
            }
            let gx = dx[i] as f32;
            let gy = dy[i] as f32;
            let mag2 = gx * gx + gy * gy;
            if mag2 < 1e-6 {
                continue;
            }
            let inv_mag = 1.0 / mag2.sqrt();
            // delta cho moi buoc r (don vi accumulator), dang fixed-point
            let ddx_q = (gx * inv_mag * inv_dp * ONE) as i64;
            let ddy_q = (gy * inv_mag * inv_dp * ONE) as i64;
            for &sign in &[1i64, -1i64] {
                let ddx = sign * ddx_q;
                let ddy = sign * ddy_q;
                // diem bat dau tai r = MIN_RADIUS (fixed-point)
                let mut fx = ((x as f32
                    + sign as f32 * gx * inv_mag * MIN_RADIUS as f32)
                    * inv_dp
                    * ONE) as i64;
                let mut fy = ((y as f32
                    + sign as f32 * gy * inv_mag * MIN_RADIUS as f32)
                    * inv_dp
                    * ONE) as i64;
                for _ in MIN_RADIUS..=MAX_RADIUS {
                    let ax = (fx >> FP) as i32;
                    let ay = (fy >> FP) as i32;
                    if ax >= 0 && ay >= 0 && ax < aw_i && ay < ah_i {
                        accum[ay as usize * aw + ax as usize] += 1;
                    }
                    fx += ddx;
                    fy += ddy;
                }
            }
        }
    }

    // tim tam: cell > PARAM2 va la local-max trong 3x3
    let mut centers: Vec<(i32, i32, i32)> = Vec::new(); // (vote, ax, ay)
    for ay in 1..ah - 1 {
        for ax in 1..aw - 1 {
            let v = accum[ay * aw + ax];
            if v <= PARAM2 {
                continue;
            }
            let mut is_max = true;
            'nb: for dy2 in -1i32..=1 {
                for dx2 in -1i32..=1 {
                    if dx2 == 0 && dy2 == 0 {
                        continue;
                    }
                    let nx = (ax as i32 + dx2) as usize;
                    let ny = (ay as i32 + dy2) as usize;
                    if accum[ny * aw + nx] > v {
                        is_max = false;
                        break 'nb;
                    }
                }
            }
            if is_max {
                centers.push((v, ax as i32, ay as i32));
            }
        }
    }
    // sap theo vote giam
    centers.sort_by(|a, b| b.0.cmp(&a.0));

    // loc minDist + chon ban kinh tot nhat moi tam
    let mut result: Vec<(i32, i32, i32)> = Vec::new();
    let min_dist2 = MIN_DIST * MIN_DIST;
    for (_v, ax, ay) in centers {
        let cx = (ax as f32 + 0.5) * DP;
        let cy = (ay as f32 + 0.5) * DP;
        // minDist so voi tam da nhan
        if result
            .iter()
            .any(|&(rx, ry, _)| {
                let ddx = rx as f32 - cx;
                let ddy = ry as f32 - cy;
                ddx * ddx + ddy * ddy < min_dist2
            })
        {
            continue;
        }
        // chon ban kinh: histogram khoang cach tu tam toi cac edge pixel
        if let Some(r) = best_radius(&edges, cx, cy) {
            result.push((cx as i32, cy as i32, r));
        }
    }
    result
}

/// Tim ban kinh tot nhat cho 1 tam: dem edge pixel theo khoang cach, lay r co nhieu nhat.
fn best_radius(edges: &Mat1, cx: f32, cy: f32) -> Option<i32> {
    let (w, h) = (edges.w, edges.h);
    let mut hist = vec![0i32; (MAX_RADIUS + 1) as usize];
    // quet vung bao quanh tam
    let x0 = ((cx - MAX_RADIUS as f32).floor() as i32).max(0);
    let x1 = ((cx + MAX_RADIUS as f32).ceil() as i32).min(w as i32 - 1);
    let y0 = ((cy - MAX_RADIUS as f32).floor() as i32).max(0);
    let y1 = ((cy + MAX_RADIUS as f32).ceil() as i32).min(h as i32 - 1);
    for y in y0..=y1 {
        for x in x0..=x1 {
            if edges.at(x as usize, y as usize) == 0 {
                continue;
            }
            let ddx = x as f32 - cx;
            let ddy = y as f32 - cy;
            let d = (ddx * ddx + ddy * ddy).sqrt().round() as i32;
            if (MIN_RADIUS..=MAX_RADIUS).contains(&d) {
                hist[d as usize] += 1;
            }
        }
    }
    let mut best = (0i32, -1i32);
    for (r, &cnt) in hist.iter().enumerate() {
        if cnt > best.0 {
            best = (cnt, r as i32);
        }
    }
    if best.1 >= MIN_RADIUS {
        Some(best.1)
    } else {
        None
    }
}

/// API cho detect.rs: tra cac Box (qua Button) tu Hough circles.
/// Moi vong tron (cx,cy,r) -> box (x=cx-r, y=cy-r, w=h=2r, score=1.0) khop perception.py.
pub fn hough_circle_candidates(img: &Image) -> Vec<crate::detect::BoxCandidate> {
    let gray = to_gray(img);
    let blur = median_blur5(&gray);
    hough_gradient(&blur)
        .into_iter()
        .map(|(cx, cy, r)| crate::detect::BoxCandidate {
            x: cx - r,
            y: cy - r,
            w: 2 * r,
            h: 2 * r,
            s: 1.0,
        })
        .collect()
}

/// Convenience: tra Button truc tiep (debug).
pub fn detect_circles_as_buttons(img: &Image) -> Vec<Button> {
    hough_circle_candidates(img)
        .into_iter()
        .map(|b| Button {
            cx: b.x + b.w / 2,
            cy: b.y + b.h / 2,
            w: b.w,
            h: b.h,
            score: 1.0,
        })
        .collect()
}

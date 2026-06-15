//! capture.rs - truu tuong hoa NGUON ANH + DIEU KHIEN game.
//!
//! EYE can: (1) chup man hinh game -> RGB, (2) thuc thi click/drag/key.
//! Tach thanh trait de:
//!   - test duoc tren WSL ngay bay gio (FileCapture doc 1 PNG co san),
//!   - tai su dung server PowerShell da kiem chung (PsBridge) cho ban WSL,
//!   - de cam native Win32 (#[cfg(windows)]) sau nay ma khong dung server.rs.

use std::time::{SystemTime, UNIX_EPOCH};

use eye_core::Image;

use crate::protocol::{Action, ActionKind, ActionResult, Observation, Size};

/// epoch seconds hien tai (cho truong `ts`).
pub fn now_ts() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

/// Backend chup man + dieu khien game. Moi platform/che do co 1 impl.
pub trait Backend {
    /// Chup man hinh game hien tai. None = game khong chay / anh stale.
    fn grab(&mut self) -> Option<Image>;

    /// Thuc thi 1 action len game. Tra Err(msg) neu loi.
    fn dispatch(&mut self, action: &Action) -> Result<(), String>;

    /// observe = grab + chay perception. Mac dinh, impl khong can override.
    fn observe(&mut self) -> Observation {
        self.observe_opts(true)
    }

    /// observe co tuy chon: with_buttons=false -> tier "nav" (~9x nhanh, bo
    /// detect_buttons), chi dhash/state_id/loading cho dieu huong.
    fn observe_opts(&mut self, with_buttons: bool) -> Observation {
        self.observe_full(with_buttons, false)
    }

    /// observe day du: them with_page (landmark template match, ~300ms - CHI khi
    /// can xac dinh man/dieu huong, KHONG dung moi frame).
    fn observe_full(&mut self, with_buttons: bool, with_page: bool) -> Observation {
        let ts = now_ts();
        match self.grab() {
            Some(img) => Observation::from_frame_full(&img, ts, None, with_buttons, with_page),
            None => Observation::dead(ts, Size { w: 0, h: 0 }),
        }
    }

    /// observe cho LLM agent vision: tao Set-of-Mark (danh so element + luu anh
    /// marked vao `som_dir`). Tra Observation co marks + marked_path de agent NHIN
    /// roi chon SO. with_page tuy chon (xac dinh man).
    fn observe_som(&mut self, som_dir: &str, with_page: bool) -> Observation {
        let ts = now_ts();
        match self.grab() {
            Some(img) => Observation::perceive(
                &img,
                ts,
                &crate::protocol::PerceiveOpts {
                    frame_path: None,
                    with_buttons: true,
                    with_page,
                    som_dir: Some(som_dir.to_string()),
                },
            ),
            None => Observation::dead(ts, Size { w: 0, h: 0 }),
        }
    }

    /// SNAP toa do tho -> tam element gan nhat (cho agent click chinh xac khi CV
    /// sot element). Tra (x,y,snapped,dist). None neu khong chup duoc.
    fn snap(&mut self, rx: i32, ry: i32, radius: i32) -> Option<eye_core::Snap> {
        let img = self.grab()?;
        Some(eye_core::snap_to_element(&img, rx, ry, radius))
    }

    /// PROBE kha nang di chuyen man (active motion probe - cach SENIOR thay vi doan).
    /// Drag thu NGANG roi DOC tu giua man, do shift moi truc, sau do KEO VE de
    /// khong lam xe dich. Cho agent biet man co scroll/keo duoc khong (ban do
    /// exploration, list menu Shop/Souls). amp = bien do keo thu (px). None neu
    /// khong chup duoc / khong drag duoc.
    fn probe(&mut self, amp: i32) -> Option<crate::protocol::ProbeResult> {
        use crate::protocol::ProbeResult;
        use eye_core::{analyze_movability, motion::Rect};
        // amp vua phai: keo qua xa -> content dich > vung tim shift -> rail bien
        // (score thap, am tinh gia). 150px du de phat hien, van trong tam tim.
        let amp = amp.clamp(60, 200);
        let base = self.grab()?;
        let (w, h) = (base.width as i32, base.height as i32);
        let (cx, cy) = (w / 2, h / 2);
        // ROI CAO/RONG (8%..90%) de vung tim shift (+-max quanh bien) con du hang
        // hop le sau khi tru le 2*max. ROI nho qua -> khong tim duoc dich lon.
        let roi = Rect {
            x: (base.width * 5 / 100),
            y: (base.height * 8 / 100),
            w: (base.width * 90 / 100),
            h: (base.height * 82 / 100),
        };
        // tim shift trong khoang [-max,max] voi max hoi > amp (content co the dich
        // ~1:1 voi ngon tay, doi khi hon chut do quan tinh).
        let max = amp + 30;

        // --- truc NGANG: keo trai amp, do, roi keo phai amp (ve cho cu) ---
        let after_x = self.drag_then_grab(cx, cy, cx - amp, cy)?;
        let mv_x = analyze_movability(&base, &after_x, roi, max);
        let _ = self.drag_then_grab(cx - amp, cy, cx, cy); // keo VE
        std::thread::sleep(std::time::Duration::from_millis(150));

        // --- truc DOC: keo len amp, do, roi keo xuong amp (ve cho cu) ---
        let base_y = self.grab().unwrap_or_else(|| base.clone());
        let after_y = self.drag_then_grab(cx, cy, cx, cy - amp)?;
        let mv_y = analyze_movability(&base_y, &after_y, roi, max);
        let _ = self.drag_then_grab(cx, cy - amp, cx, cy); // keo VE

        // movable: dich dang ke (>=15% bien do keo) voi do tin cay cao. Dung
        // diff lam phu tro: man tinh keo -> diff ~0; co dich -> diff cao + shift ro.
        let min_shift = (amp / 6).max(8); // ~15% amp, toi thieu 8px
        const MIN_SCORE: f32 = 0.25;
        let can_x = mv_x.dx.abs() >= min_shift && mv_x.dx_score >= MIN_SCORE;
        let can_y = mv_y.dy.abs() >= min_shift && mv_y.dy_score >= MIN_SCORE;
        Some(ProbeResult {
            movable: can_x || can_y,
            can_x,
            can_y,
            dx: mv_x.dx,
            dx_score: mv_x.dx_score as f64,
            dy: mv_y.dy,
            dy_score: mv_y.dy_score as f64,
            diff: (mv_x.diff.max(mv_y.diff)) as f64,
        })
    }

    /// drag (x0,y0)->(x1,y1), cho man on dinh, chup lai. Dung trong probe.
    fn drag_then_grab(&mut self, x0: i32, y0: i32, x1: i32, y1: i32) -> Option<Image> {
        let a = Action {
            kind: ActionKind::Drag,
            x: Some(x0),
            y: Some(y0),
            x1: Some(x1),
            y1: Some(y1),
            steps: Some(12),
            key: None,
            duration_ms: None,
        };
        self.dispatch(&a).ok()?;
        std::thread::sleep(std::time::Duration::from_millis(280));
        self.grab()
    }

    /// act = dispatch + observe lai (giong PythonEye.act).
    fn act(&mut self, action: &Action) -> ActionResult {
        match self.dispatch(action) {
            Ok(()) => ActionResult {
                ok: true,
                error: None,
                observation: Some(self.observe()),
            },
            Err(e) => ActionResult {
                ok: false,
                error: Some(e),
                observation: None,
            },
        }
    }
}

/// FileCapture - doc anh tu 1 file PNG (cho test/dev tren WSL).
///
/// `grab` doc lai file moi lan (de test co the thay anh giua cac lan goi).
/// `dispatch` chi ghi log (khong co game that) -> cho phep chay full pipeline
/// socket ma khong can Windows.
pub struct FileCapture {
    path: std::path::PathBuf,
    /// neu true: dispatch tra Ok im lang (mo phong). false: tra Err.
    pub accept_actions: bool,
}

impl FileCapture {
    pub fn new(path: impl Into<std::path::PathBuf>) -> Self {
        FileCapture {
            path: path.into(),
            accept_actions: true,
        }
    }
}

impl Backend for FileCapture {
    fn grab(&mut self) -> Option<Image> {
        let bytes = std::fs::read(&self.path).ok()?;
        Image::decode_png(&bytes).ok()
    }

    fn dispatch(&mut self, action: &Action) -> Result<(), String> {
        if matches!(action.kind, ActionKind::Noop | ActionKind::Wait) {
            if action.kind == ActionKind::Wait {
                if let Some(ms) = action.duration_ms {
                    std::thread::sleep(std::time::Duration::from_millis(ms.max(0) as u64));
                }
            }
            return Ok(());
        }
        if self.accept_actions {
            eprintln!("[FileCapture] (mo phong) action = {:?}", action.kind);
            Ok(())
        } else {
            Err("FileCapture khong dieu khien game that".to_string())
        }
    }
}

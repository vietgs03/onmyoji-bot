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

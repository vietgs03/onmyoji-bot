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
        let ts = now_ts();
        match self.grab() {
            Some(img) => Observation::from_frame(&img, ts, None),
            None => Observation::dead(ts, Size { w: 0, h: 0 }),
        }
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

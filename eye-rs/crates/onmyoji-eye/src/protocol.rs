//! protocol.rs - cac kieu JSON cho socket EYE<->BRAIN, khop 1-1 voi
//! `contracts/schema.json`. Doi schema = sua ca file nay lan Python entities.
//!
//! Giao thuc: NDJSON tren TCP localhost. Moi dong la 1 JSON.
//!   BRAIN -> EYE: `Request` (op = observe|act|ping|shutdown)
//!   EYE -> BRAIN: `Response` (boc Observation / ActionResult / loi)

use serde::{Deserialize, Serialize};

use eye_core::{detect_buttons, dhash, is_loading, state_id, Image};

/// Mot vung click duoc (EYE phat hien bang CV). Khop schema `Button`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Button {
    /// tam X (toa do client-area)
    pub x: i32,
    /// tam Y (toa do client-area)
    pub y: i32,
    pub w: i32,
    pub h: i32,
    /// do tin cay 0..1
    pub score: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
}

/// Tai nguyen OCR (vang/AP/ngoc). null = chua doc duoc. Khop schema `Resources`.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Resources {
    #[serde(default)]
    pub gold: Option<i64>,
    #[serde(default)]
    pub ap: Option<i64>,
    #[serde(default)]
    pub jade: Option<i64>,
}

/// Kich thuoc man hinh. Khop schema `Size`.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Size {
    pub w: i32,
    pub h: i32,
}

/// EYE -> BRAIN: 1 quan sat. KHONG chua anh raw. Khop schema `Observation`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Observation {
    /// epoch seconds khi chup
    pub ts: f64,
    pub state_id: String,
    /// 64-bit dhash chuoi '0'/'1'. BRAIN dung de khop mo (hamming<=12) khi
    /// state_id khong trung (md5 khuech dai 1 bit). None neu anh sai kich thuoc.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dhash: Option<String>,
    pub loading: bool,
    pub size: Size,
    #[serde(default)]
    pub buttons: Vec<Button>,
    #[serde(default = "default_true")]
    pub alive: bool,
    #[serde(default)]
    pub resources: Resources,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub frame_path: Option<String>,
}

fn default_true() -> bool {
    true
}

impl Observation {
    /// Observation "chet": game khong chay / anh stale.
    pub fn dead(ts: f64, size: Size) -> Self {
        Observation {
            ts,
            state_id: "DEAD".to_string(),
            dhash: None,
            loading: false,
            size,
            buttons: Vec::new(),
            alive: false,
            resources: Resources::default(),
            frame_path: None,
        }
    }

    /// Phan tich 1 frame RGB -> Observation day du (state_id, loading, buttons).
    /// Day la "bo nao" cua EYE: chay perception thuan tren anh da chup.
    pub fn from_frame(img: &Image, ts: f64, frame_path: Option<String>) -> Self {
        let size = Size {
            w: img.width as i32,
            h: img.height as i32,
        };
        let dh = dhash(img);
        let sid = dh.as_deref().map(state_id).unwrap_or_default();
        let loading = is_loading(img);
        // man dang loading -> bo qua detect (giong PythonEye)
        let buttons = if loading {
            Vec::new()
        } else {
            detect_buttons(img, false)
                .into_iter()
                .map(|b| Button {
                    x: b.cx,
                    y: b.cy,
                    w: b.w,
                    h: b.h,
                    score: b.score as f64,
                    text: None,
                })
                .collect()
        };
        Observation {
            ts,
            state_id: sid,
            dhash: dh,
            loading,
            size,
            buttons,
            alive: true,
            resources: Resources::default(),
            frame_path,
        }
    }
}

/// Loai hanh dong. Khop enum schema `Action.kind`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ActionKind {
    Click,
    PoliteClick,
    FgClick,
    Drag,
    Key,
    Wait,
    Noop,
}

/// BRAIN -> EYE: 1 hanh dong. Khop schema `Action`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Action {
    pub kind: ActionKind,
    #[serde(default)]
    pub x: Option<i32>,
    #[serde(default)]
    pub y: Option<i32>,
    #[serde(default)]
    pub x1: Option<i32>,
    #[serde(default)]
    pub y1: Option<i32>,
    #[serde(default)]
    pub steps: Option<i32>,
    #[serde(default)]
    pub key: Option<String>,
    #[serde(default)]
    pub duration_ms: Option<i64>,
}

/// EYE -> BRAIN: ket qua sau act + observation moi. Khop schema `ActionResult`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionResult {
    pub ok: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub observation: Option<Observation>,
}

/// Op cua request socket.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Op {
    Observe,
    Act,
    Ping,
    Shutdown,
}

/// BRAIN -> EYE qua socket (1 dong NDJSON). Khop schema `Request`.
#[derive(Debug, Clone, Deserialize)]
pub struct Request {
    pub op: Op,
    #[serde(default)]
    pub action: Option<Action>,
    #[serde(default)]
    pub id: Option<serde_json::Value>,
}

/// EYE -> BRAIN qua socket (1 dong NDJSON). Khop schema `Response`.
#[derive(Debug, Clone, Serialize)]
pub struct Response {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub observation: Option<Observation>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<ActionResult>,
}

impl Response {
    pub fn err(id: Option<serde_json::Value>, msg: impl Into<String>) -> Self {
        Response {
            ok: false,
            id,
            error: Some(msg.into()),
            observation: None,
            result: None,
        }
    }

    pub fn obs(id: Option<serde_json::Value>, observation: Observation) -> Self {
        Response {
            ok: true,
            id,
            error: None,
            observation: Some(observation),
            result: None,
        }
    }

    pub fn act(id: Option<serde_json::Value>, result: ActionResult) -> Self {
        Response {
            ok: result.ok,
            id,
            error: None,
            observation: None,
            result: Some(result),
        }
    }
}

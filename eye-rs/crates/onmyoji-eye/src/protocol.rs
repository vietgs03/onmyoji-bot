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

/// 1 Set-of-Mark element cho LLM agent vision: id + tam (toa do click) + bbox.
/// Agent chon SO trong anh marked -> he thong tra toa do (cx,cy) chinh xac.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Mark {
    pub id: u32,
    /// tam = diem click (toa do client-area)
    pub cx: i32,
    pub cy: i32,
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
    pub score: f64,
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
    /// Page UI nhan duoc bang landmark template match (vd "page_main"). Robust
    /// hon dhash voi man DONG. None neu khong khop page nao da biet.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub page: Option<String>,
    /// Score template cua page (TM_CCOEFF_NORMED) neu co `page`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub page_score: Option<f64>,
    /// Set-of-Mark: cac element da danh so (cho LLM agent vision chon SO).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub marks: Vec<Mark>,
    /// Duong dan anh DA DANH SO (marked) de agent NHIN. None neu khong render SoM.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub marked_path: Option<String>,
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
            page: None,
            page_score: None,
            marks: Vec::new(),
            marked_path: None,
            alive: false,
            resources: Resources::default(),
            frame_path: None,
        }
    }

    /// Phan tich 1 frame RGB -> Observation day du (state_id, loading, buttons).
    /// Day la "bo nao" cua EYE: chay perception thuan tren anh da chup.
    pub fn from_frame(img: &Image, ts: f64, frame_path: Option<String>) -> Self {
        Self::from_frame_opts(img, ts, frame_path, true)
    }

    /// Nhu from_frame nhung co the BO QUA detect_buttons (nang ~88% chi phi).
    /// `with_buttons=false` -> tier "nav" (~19ms): chi dhash/state_id/loading,
    /// dung cho dieu huong khi chua can toa do nut. `true` = day du (default).
    ///
    /// Page detection (landmark, ~300ms cho 32 page) KHONG chay o day vi qua nang
    /// cho hot loop. Goi rieng `with_page` qua Backend::observe_full neu can.
    pub fn from_frame_opts(
        img: &Image,
        ts: f64,
        frame_path: Option<String>,
        with_buttons: bool,
    ) -> Self {
        Self::from_frame_full(img, ts, frame_path, with_buttons, false)
    }

    /// Day du nhat: co the bat `with_page` (landmark template match, ~300ms - CHI
    /// dung khi can dieu huong/xac dinh man, KHONG dung moi frame).
    pub fn from_frame_full(
        img: &Image,
        ts: f64,
        frame_path: Option<String>,
        with_buttons: bool,
        with_page: bool,
    ) -> Self {
        Self::perceive(
            img,
            ts,
            &PerceiveOpts {
                frame_path,
                with_buttons,
                with_page,
                som_dir: None,
            },
        )
    }

    /// perceive: ham loi, dieu khien bang `PerceiveOpts`. Tao Set-of-Mark cho LLM
    /// agent vision khi opts.som_dir = Some(dir) (luu anh marked + tra marks).
    pub fn perceive(img: &Image, ts: f64, opts: &PerceiveOpts) -> Self {
        let size = Size {
            w: img.width as i32,
            h: img.height as i32,
        };
        // dhash/state_id la VAN TAY DIEU HUONG -> tinh tren anh CHUAN (resize ve
        // WxH=1152x679) de khop knowledge base bat ke resolution game thuc te.
        // Game ep client 16:9 (1136x640); resize client->canon cho hamming=0.
        // dhash resize ve 9x8 ben trong nen khong anh huong toa do.
        let canon;
        let dh = if img.width == eye_core::W && img.height == eye_core::H {
            dhash(img)
        } else {
            canon = eye_core::resize_rgb(img, eye_core::W, eye_core::H);
            dhash(&canon)
        };
        let sid = dh.as_deref().map(state_id).unwrap_or_default();
        // loading + buttons tinh tren anh GOC (native client) -> toa do click
        // khop 1:1 voi client area, khong bi scale lech.
        let loading = is_loading(img);
        // Page detection (landmark template match) CHI khi with_page=true (nang
        // ~300ms cho 32 page). Robust hon dhash voi man DONG/3D. Default OFF.
        let (page, page_score) = if opts.with_page {
            match crate::pages_embed::detector().detect(img) {
                Some(h) => (Some(h.page), Some(h.score)),
                None => (None, None),
            }
        } else {
            (None, None)
        };
        // man dang loading HOAC tier nav (with_buttons=false) -> bo qua detect.
        let buttons = if loading || !opts.with_buttons {
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
        // Set-of-Mark cho LLM agent vision (chi khi som_dir Some): danh so element
        // + ve box+so len anh -> luu PNG cho agent NHIN. Tra marks (so->toa do).
        let (marks, marked_path) = if let Some(dir) = &opts.som_dir {
            let (ms, annotated) = eye_core::annotate(img);
            let path = format!("{dir}/eye_som_{}.png", (ts * 1000.0) as i64);
            let marked = annotated.save_png(&path).ok().map(|_| path);
            let marks_out = ms
                .into_iter()
                .map(|m| Mark {
                    id: m.id,
                    cx: m.cx,
                    cy: m.cy,
                    x: m.x,
                    y: m.y,
                    w: m.w,
                    h: m.h,
                    score: m.score as f64,
                })
                .collect();
            (marks_out, marked)
        } else {
            (Vec::new(), None)
        };
        Observation {
            ts,
            state_id: sid,
            dhash: dh,
            loading,
            size,
            buttons,
            page,
            page_score,
            marks,
            marked_path,
            alive: true,
            resources: Resources::default(),
            frame_path: opts.frame_path.clone(),
        }
    }
}

/// Tuy chon perceive: bat/tat tung tang chi phi.
#[derive(Debug, Clone, Default)]
pub struct PerceiveOpts {
    /// duong dan anh debug (khong bat buoc)
    pub frame_path: Option<String>,
    /// chay detect_buttons (false = tier nav nhanh)
    pub with_buttons: bool,
    /// chay page detection (landmark, ~300ms)
    pub with_page: bool,
    /// Some(dir) = tao Set-of-Mark, luu anh marked vao dir cho LLM agent vision.
    pub som_dir: Option<String>,
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
    /// SNAP toa do tho -> tam element gan nhat (cho agent click chinh xac khi CV
    /// sot element). Tra ket qua trong Response.snap.
    Snap,
    /// PROBE kha nang di chuyen: drag thu (ngang + doc) -> do shift -> biet man co
    /// scroll/keo duoc khong (ban do exploration, list menu Shop/Souls...). Tu keo
    /// VE de khong lam xe dich man. Tra ket qua trong Response.probe.
    Probe,
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
    /// observe: false = tier "nav" (bo detect_buttons, ~9x nhanh). Mac dinh true.
    #[serde(default = "default_true")]
    pub with_buttons: bool,
    /// observe: true = chay page detection (landmark, ~300ms). Mac dinh false
    /// (nang, chi bat khi can xac dinh man/dieu huong).
    #[serde(default)]
    pub with_page: bool,
    /// observe: true = tao Set-of-Mark (danh so element + luu anh marked) cho LLM
    /// agent vision. Mac dinh false (chi bat khi agent can NHIN de quyet dinh).
    #[serde(default)]
    pub with_som: bool,
    /// snap: toa do tho can snap (op=snap). radius = ban kinh tim element.
    #[serde(default)]
    pub x: Option<i32>,
    #[serde(default)]
    pub y: Option<i32>,
    #[serde(default)]
    pub radius: Option<i32>,
}

/// Ket qua snap toa do tho -> tam element gan nhat. Khop schema `SnapResult`.
#[derive(Debug, Clone, Serialize)]
pub struct SnapResult {
    pub x: i32,
    pub y: i32,
    pub snapped: bool,
    pub dist: f64,
}

/// Ket qua probe kha nang di chuyen man (drag thu -> do shift). Cho agent biet
/// man co scroll/keo duoc khong de kham pha het content (ban do, list menu).
#[derive(Debug, Clone, Serialize, Default)]
pub struct ProbeResult {
    /// man co keo duoc khong (ngang HOAC doc dat nguong shift+score).
    pub movable: bool,
    pub can_x: bool,
    pub can_y: bool,
    pub dx: i32,
    pub dx_score: f64,
    pub dy: i32,
    pub dy_score: f64,
    pub diff: f64,
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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub snap: Option<SnapResult>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub probe: Option<ProbeResult>,
}

impl Response {
    pub fn err(id: Option<serde_json::Value>, msg: impl Into<String>) -> Self {
        Response {
            ok: false,
            id,
            error: Some(msg.into()),
            observation: None,
            result: None,
            snap: None,
            probe: None,
        }
    }

    pub fn obs(id: Option<serde_json::Value>, observation: Observation) -> Self {
        Response {
            ok: true,
            id,
            error: None,
            observation: Some(observation),
            result: None,
            snap: None,
            probe: None,
        }
    }

    pub fn act(id: Option<serde_json::Value>, result: ActionResult) -> Self {
        Response {
            ok: result.ok,
            id,
            error: None,
            observation: None,
            result: Some(result),
            snap: None,
            probe: None,
        }
    }

    /// Response cho op snap.
    pub fn snap(id: Option<serde_json::Value>, snap: SnapResult) -> Self {
        Response {
            ok: true,
            id,
            error: None,
            observation: None,
            result: None,
            snap: Some(snap),
            probe: None,
        }
    }

    /// Response cho op probe (kha nang di chuyen man).
    pub fn probe(id: Option<serde_json::Value>, probe: ProbeResult) -> Self {
        Response {
            ok: true,
            id,
            error: None,
            observation: None,
            result: None,
            snap: None,
            probe: Some(probe),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use eye_core::Image;

    /// Anh test 1136x640 (client) toan mau de chay perception that.
    fn test_img() -> Image {
        // doc anh that neu co, neu khong tao anh phang
        if let Ok(bytes) = std::fs::read("/tmp/xval.png") {
            if let Ok(img) = Image::decode_png(&bytes) {
                return img;
            }
        }
        Image::from_rgb(1136, 640, vec![128u8; 1136 * 640 * 3]).unwrap()
    }

    #[test]
    fn nav_tier_bo_buttons_giu_state_id() {
        let img = test_img();
        let full = Observation::from_frame_opts(&img, 0.0, None, true);
        let nav = Observation::from_frame_opts(&img, 0.0, None, false);
        // nav PHAI giong state_id/dhash/loading nhung KHONG co buttons
        assert_eq!(full.state_id, nav.state_id);
        assert_eq!(full.dhash, nav.dhash);
        assert_eq!(full.loading, nav.loading);
        assert!(nav.buttons.is_empty(), "nav khong duoc co buttons");
    }

    #[test]
    fn request_with_buttons_mac_dinh_true() {
        // thieu truong -> default true (tuong thich nguoc)
        let r: Request = serde_json::from_str(r#"{"op":"observe"}"#).unwrap();
        assert!(r.with_buttons);
        // co truong false -> nav
        let r2: Request =
            serde_json::from_str(r#"{"op":"observe","with_buttons":false}"#).unwrap();
        assert!(!r2.with_buttons);
    }
}

//! server.rs - socket server NDJSON cho EYE.
//!
//! Lang nghe TCP localhost. Moi ket noi: doc tung dong JSON (`Request`), chay
//! op tren Backend, ghi 1 dong JSON (`Response`). Don luong (serialize) vi
//! Backend dung chung 1 game + 1 server PowerShell -> khong the chay song song.

use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};

use crate::capture::Backend;
use crate::protocol::{Op, Request, Response};

/// Chay server tren `addr` (vd "127.0.0.1:8765") voi `backend` cho truoc.
/// Block mai mai (tru khi nhan op shutdown). Tra Err neu khong bind duoc.
pub fn serve(addr: &str, mut backend: impl Backend) -> Result<(), String> {
    let listener =
        TcpListener::bind(addr).map_err(|e| format!("bind {addr} that bai: {e}"))?;
    eprintln!("[onmyoji-eye] dang nghe tren {addr}");
    for conn in listener.incoming() {
        match conn {
            Ok(stream) => {
                // tung ket noi xu ly tuan tu (1 game -> khong song song).
                if handle_conn(stream, &mut backend) {
                    eprintln!("[onmyoji-eye] nhan shutdown, dong server");
                    break;
                }
            }
            Err(e) => eprintln!("[onmyoji-eye] loi accept: {e}"),
        }
    }
    Ok(())
}

/// Xu ly 1 ket noi den khi client dong. Tra true neu nhan op shutdown.
fn handle_conn(stream: TcpStream, backend: &mut impl Backend) -> bool {
    let peer = stream
        .peer_addr()
        .map(|a| a.to_string())
        .unwrap_or_else(|_| "?".to_string());
    eprintln!("[onmyoji-eye] client ket noi: {peer}");
    let mut writer = match stream.try_clone() {
        Ok(w) => w,
        Err(e) => {
            eprintln!("[onmyoji-eye] clone stream loi: {e}");
            return false;
        }
    };
    let reader = BufReader::new(stream);
    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(e) => {
                eprintln!("[onmyoji-eye] doc dong loi: {e}");
                break;
            }
        };
        if line.trim().is_empty() {
            continue;
        }
        let (resp, shutdown) = process_line(&line, backend);
        if let Err(e) = write_response(&mut writer, &resp) {
            eprintln!("[onmyoji-eye] ghi response loi: {e}");
            break;
        }
        if shutdown {
            return true;
        }
    }
    eprintln!("[onmyoji-eye] client {peer} ngat");
    false
}

/// Thu muc luu anh Set-of-Mark cho LLM agent vision. Mac dinh /tmp (WSL ext4
/// nhanh; agent doc duoc qua file path). Chinh qua env ONMYOJI_EYE_SOM_DIR.
fn som_dir() -> &'static str {
    use std::sync::OnceLock;
    static D: OnceLock<String> = OnceLock::new();
    D.get_or_init(|| std::env::var("ONMYOJI_EYE_SOM_DIR").unwrap_or_else(|_| "/tmp".to_string()))
}

/// Phan tich 1 dong JSON, chay op, tao Response. Tra (resp, can_shutdown).
fn process_line(line: &str, backend: &mut impl Backend) -> (Response, bool) {
    let req: Request = match serde_json::from_str(line) {
        Ok(r) => r,
        Err(e) => return (Response::err(None, format!("JSON khong hop le: {e}")), false),
    };
    let id = req.id.clone();
    match req.op {
        Op::Ping => (Response::obs(id, backend.observe()), false),
        Op::Observe => {
            // with_som -> tao Set-of-Mark cho LLM agent vision (luu anh marked
            // vao thu muc tam). Nguoc lai: observe thuong (buttons/page).
            let obs = if req.with_som {
                backend.observe_som(som_dir(), req.with_page)
            } else {
                backend.observe_full(req.with_buttons, req.with_page)
            };
            (Response::obs(id, obs), false)
        }
        Op::Act => match req.action {
            Some(a) => (Response::act(id, backend.act(&a)), false),
            None => (Response::err(id, "op=act thieu truong 'action'"), false),
        },
        Op::Shutdown => (
            Response {
                ok: true,
                id,
                error: None,
                observation: None,
                result: None,
            },
            true,
        ),
    }
}

fn write_response(writer: &mut impl Write, resp: &Response) -> std::io::Result<()> {
    let mut s = serde_json::to_string(resp).unwrap_or_else(|e| {
        format!("{{\"ok\":false,\"error\":\"serialize loi: {e}\"}}")
    });
    s.push('\n');
    writer.write_all(s.as_bytes())?;
    writer.flush()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::{Action, ActionKind};

    /// Backend gia: tra observation co dinh, ghi nho action cuoi.
    struct MockBackend {
        last: Option<ActionKind>,
    }
    impl Backend for MockBackend {
        fn grab(&mut self) -> Option<eye_core::Image> {
            None
        }
        fn dispatch(&mut self, action: &Action) -> Result<(), String> {
            self.last = Some(action.kind);
            Ok(())
        }
    }

    #[test]
    fn ping_tra_observation() {
        let mut b = MockBackend { last: None };
        let (r, sd) = process_line(r#"{"op":"ping"}"#, &mut b);
        assert!(r.ok && !sd && r.observation.is_some());
    }

    #[test]
    fn observe_grab_none_thi_dead() {
        let mut b = MockBackend { last: None };
        let (r, _) = process_line(r#"{"op":"observe","id":7}"#, &mut b);
        let obs = r.observation.unwrap();
        assert_eq!(obs.state_id, "DEAD");
        assert!(!obs.alive);
        assert_eq!(r.id, Some(serde_json::json!(7)));
    }

    #[test]
    fn act_goi_dispatch() {
        let mut b = MockBackend { last: None };
        let (r, _) = process_line(r#"{"op":"act","action":{"kind":"click","x":10,"y":20}}"#, &mut b);
        assert!(r.ok);
        assert_eq!(b.last, Some(ActionKind::Click));
        assert!(r.result.is_some());
    }

    #[test]
    fn act_thieu_action_loi() {
        let mut b = MockBackend { last: None };
        let (r, _) = process_line(r#"{"op":"act"}"#, &mut b);
        assert!(!r.ok && r.error.is_some());
    }

    #[test]
    fn json_hong_tra_loi_khong_panic() {
        let mut b = MockBackend { last: None };
        let (r, sd) = process_line("{khong phai json", &mut b);
        assert!(!r.ok && !sd && r.error.is_some());
    }

    #[test]
    fn shutdown_set_co() {
        let mut b = MockBackend { last: None };
        let (r, sd) = process_line(r#"{"op":"shutdown"}"#, &mut b);
        assert!(r.ok && sd);
    }
}

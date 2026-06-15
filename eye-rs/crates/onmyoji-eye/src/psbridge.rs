//! psbridge.rs - Backend dung lai server PowerShell da kiem chung (`ps/server.ps1`).
//!
//! Ly do: server.ps1 da xu ly dung PrintWindow + cat dung CLIENT area + cac loai
//! click (send/fg/polite) ma CV da duoc validate tren dung anh do. Thay vi viet
//! lai Win32 capture (de lech pixel -> hong dhash), EYE-rs lai server nay qua
//! stdin/stdout pipe (giong control_client.py), roi tu chay perception bang Rust.
//!
//! Ket qua: ban WSL chay duoc NGAY voi game that. Khi can .exe thuan Windows
//! khong phu thuoc PowerShell, them backend native #[cfg(windows)] sau (P5+).

use std::io::{BufRead, BufReader, Read, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::time::{Duration, Instant};

use eye_core::Image;

use crate::capture::Backend;
use crate::protocol::{Action, ActionKind};

/// Duong dan server + file anh tren Windows (khop control_client.py).
const WIN_SERVER: &str = r"C:\Users\Public\onmyoji_server.ps1";
const WIN_SHOT: &str = r"C:\Users\Public\onmyoji_srv.png";
/// Doc anh tu phia WSL (mount /mnt/c).
const WIN_SHOT_WSL: &str = "/mnt/c/Users/Public/onmyoji_srv.png";

pub struct PsBridge {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    /// true: dung bgshot_raw (raw BGR qua pipe, nhanh ~17x). Mac dinh bat.
    use_raw: bool,
}

impl PsBridge {
    /// Khoi dong powershell.exe chay server.ps1, doi dong "OK ready".
    pub fn spawn() -> Result<Self, String> {
        let mut child = Command::new("powershell.exe")
            .args([
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                WIN_SERVER,
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("spawn powershell that bai: {e}"))?;
        let stdin = child.stdin.take().ok_or("khong lay duoc stdin")?;
        let stdout = BufReader::new(child.stdout.take().ok_or("khong lay duoc stdout")?);
        let mut br = PsBridge {
            child,
            stdin,
            stdout,
            use_raw: true,
        };
        let line = br.read_line(Duration::from_secs(20))?;
        if !line.starts_with("OK") {
            return Err(format!("server khong san sang: {line:?}"));
        }
        Ok(br)
    }

    /// Doc 1 dong tu server. (Blocking read; timeout chi gioi han tong qua deadline
    /// kiem o vong lap doc - du dung cho pipe stdout PowerShell on dinh.)
    fn read_line(&mut self, timeout: Duration) -> Result<String, String> {
        let deadline = Instant::now() + timeout;
        let mut buf = String::new();
        // BufRead::read_line blocking; ta dua vao server luon tra 1 dong / lenh.
        let n = self
            .stdout
            .read_line(&mut buf)
            .map_err(|e| format!("doc stdout loi: {e}"))?;
        if n == 0 {
            return Err("server dong stdout (EOF)".to_string());
        }
        if Instant::now() > deadline {
            // van tra ve dong doc duoc, chi canh bao
            eprintln!("[PsBridge] canh bao: doc qua deadline");
        }
        Ok(buf.trim().to_string())
    }

    /// Gui 1 lenh + doc 1 dong tra ve.
    fn cmd(&mut self, line: &str) -> Result<String, String> {
        self.stdin
            .write_all(line.as_bytes())
            .and_then(|_| self.stdin.write_all(b"\n"))
            .and_then(|_| self.stdin.flush())
            .map_err(|e| format!("ghi stdin loi: {e}"))?;
        self.read_line(Duration::from_secs(15))
    }

    /// Chup NHANH qua bgshot_raw: nhan 'RAW <w> <h> <n>\n' + n byte BGR thang
    /// qua pipe, bo qua PNG encode + file 9P + decode. BufReader::read_line lay
    /// header (da buffer san phan binary phia sau), roi read_exact lay dung n byte.
    ///
    /// Tra:
    ///   Ok(Some(img)) = chup duoc
    ///   Ok(None)      = server HIEU lenh (header "RAW") nhung game khong chay (0x0)
    ///   Err(())       = server KHONG hieu lenh (header khac) -> caller ha xuong PNG
    fn grab_raw(&mut self) -> Result<Option<Image>, ()> {
        self.stdin
            .write_all(b"bgshot_raw\n")
            .and_then(|_| self.stdin.flush())
            .map_err(|_| ())?;
        let hdr = self.read_line(Duration::from_secs(15)).map_err(|_| ())?;
        if !hdr.starts_with("RAW") {
            return Err(()); // server cu / khong ho tro raw
        }
        let parts: Vec<&str> = hdr.split_whitespace().collect();
        if parts.len() != 4 {
            return Err(());
        }
        let w = parts[1].parse::<usize>().map_err(|_| ())?;
        let h = parts[2].parse::<usize>().map_err(|_| ())?;
        let n = parts[3].parse::<usize>().map_err(|_| ())?;
        if w == 0 || h == 0 || n == 0 {
            return Ok(None); // game khong chay (RAW 0 0 0) - KHONG ha xuong PNG
        }
        if n != w * h * 3 {
            return Err(()); // header bat thuong
        }
        let mut buf = vec![0u8; n];
        // read_exact tren BufReader: tu drain buffer noi bo roi doc tiep tu pipe.
        self.stdout.read_exact(&mut buf).map_err(|_| ())?;
        Ok(Image::from_bgr(w, h, buf).ok())
    }

    /// Chup qua PNG file (duong cu, fallback). Giu lai de so sanh / khi raw loi.
    fn grab_png(&mut self) -> Option<Image> {
        let r = self.cmd(&format!("bgshot {WIN_SHOT}")).ok()?;
        if !r.starts_with("OK") {
            return None;
        }
        // "OK <w>x<h> ..." - kiem 0x0 (game khong chay -> tranh doc anh STALE).
        if let Some(dim) = r.split_whitespace().nth(1) {
            if let Some((w, h)) = dim.split_once('x') {
                let wv = w.parse::<i32>().unwrap_or(0);
                let hv = h.parse::<i32>().unwrap_or(0);
                if wv <= 0 || hv <= 0 {
                    return None;
                }
            }
        }
        let bytes = std::fs::read(WIN_SHOT_WSL).ok()?;
        Image::decode_png(&bytes).ok()
    }
}

impl Backend for PsBridge {
    fn grab(&mut self) -> Option<Image> {
        if self.use_raw {
            match self.grab_raw() {
                Ok(opt) => return opt, // chup duoc HOAC game khong chay (0x0)
                Err(()) => {
                    // server khong ho tro raw -> ha xuong PNG vinh vien.
                    eprintln!("[PsBridge] bgshot_raw khong duoc ho tro, ha xuong PNG file");
                    self.use_raw = false;
                }
            }
        }
        self.grab_png()
    }

    fn dispatch(&mut self, action: &Action) -> Result<(), String> {
        let reply = match action.kind {
            ActionKind::Click => {
                // NeoX bo qua PostMessage -> dung sendclick (SendMessage dong bo).
                self.cmd(&format!("sendclick {} {}", xy(action.x), xy(action.y)))?
            }
            ActionKind::PoliteClick => {
                self.cmd(&format!("politeclick {} {}", xy(action.x), xy(action.y)))?
            }
            ActionKind::FgClick => {
                self.cmd(&format!("fgclick {} {}", xy(action.x), xy(action.y)))?
            }
            ActionKind::Drag => self.cmd(&format!(
                "senddrag {} {} {} {} {}",
                xy(action.x),
                xy(action.y),
                xy(action.x1),
                xy(action.y1),
                action.steps.unwrap_or(14)
            ))?,
            ActionKind::Key => {
                let k = action.key.as_deref().unwrap_or("");
                self.cmd(&format!("key {k}"))?
            }
            ActionKind::Wait => {
                let ms = action.duration_ms.unwrap_or(0).max(0) as u64;
                std::thread::sleep(Duration::from_millis(ms));
                return Ok(());
            }
            ActionKind::Noop => return Ok(()),
        };
        if reply.starts_with("OK") {
            Ok(())
        } else {
            Err(format!("server tra: {reply}"))
        }
    }
}

/// Lay toa do (mac dinh 0 neu thieu).
fn xy(v: Option<i32>) -> i32 {
    v.unwrap_or(0)
}

impl Drop for PsBridge {
    fn drop(&mut self) {
        let _ = self.cmd("quit");
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

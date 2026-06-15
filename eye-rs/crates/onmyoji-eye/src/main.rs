//! onmyoji-eye - binary EYE (capture + CV + socket server).
//!
//! Lop perception (port tu perception.py) chay thuan Rust. Binary nay boc no
//! thanh 1 service: chup man hinh game -> phan tich -> phuc vu BRAIN (Python)
//! qua socket NDJSON theo `contracts/schema.json`.
//!
//! Subcommands:
//!   onmyoji-eye inspect <anh.png>      in state_id/dhash/loading/buttons (doi chieu Python)
//!   onmyoji-eye serve [addr] [--file P | --ps]
//!                                       chay socket server
//!         --ps          : dung server PowerShell that (game that, mac dinh tren WSL)
//!         --file <PNG>  : doc anh tu file (dev/test, khong can game)

use std::process::ExitCode;

mod capture;
mod pages_embed;
mod protocol;
mod psbridge;
mod server;

use capture::FileCapture;
use eye_core::Image;
use psbridge::PsBridge;

const DEFAULT_ADDR: &str = "127.0.0.1:8765";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str);
    match cmd {
        Some("inspect") => cmd_inspect(&args),
        Some("serve") => cmd_serve(&args),
        Some("bench") => cmd_bench(&args),
        // tuong thich nguoc: `onmyoji-eye <anh.png>` = inspect
        Some(p) if !p.starts_with('-') && p.ends_with(".png") => {
            cmd_inspect_path(p)
        }
        _ => {
            usage();
            ExitCode::from(2)
        }
    }
}

fn usage() {
    eprintln!("dung:");
    eprintln!("  onmyoji-eye inspect <anh.png>          in state_id/dhash/loading/buttons");
    eprintln!("  onmyoji-eye serve [addr] --ps          socket server, game that (PowerShell)");
    eprintln!("  onmyoji-eye serve [addr] --file <PNG>   socket server, doc anh tu file (dev)");
    eprintln!("  onmyoji-eye bench [N]                   do thoi gian grab+observe qua PsBridge (game that)");
    eprintln!("  (mac dinh addr = {DEFAULT_ADDR})");
}

/// bench: chup N lan qua PsBridge (raw capture) + chay observe, in thoi gian
/// tach pha grab vs perception. Validate live duong raw thuc te.
fn cmd_bench(args: &[String]) -> ExitCode {
    use crate::capture::Backend;
    use std::time::Instant;
    let n: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(20);
    let mut bridge = match PsBridge::spawn() {
        Ok(b) => b,
        Err(e) => {
            eprintln!("spawn PsBridge that bai: {e}");
            return ExitCode::FAILURE;
        }
    };
    // warmup (JIT .NET module lan dau)
    for _ in 0..3 {
        let _ = bridge.grab();
    }
    let mut t_grab = Vec::with_capacity(n);
    let mut t_obs = Vec::with_capacity(n);
    let mut last = String::new();
    for _ in 0..n {
        let t0 = Instant::now();
        let img = match bridge.grab() {
            Some(i) => i,
            None => {
                eprintln!("grab tra None (game khong chay?)");
                return ExitCode::FAILURE;
            }
        };
        let t1 = Instant::now();
        let obs = crate::protocol::Observation::from_frame(&img, 0.0, None);
        let t2 = Instant::now();
        t_grab.push((t1 - t0).as_secs_f64() * 1000.0);
        t_obs.push((t2 - t1).as_secs_f64() * 1000.0);
        last = format!(
            "{}x{} state_id={} page={} buttons={}",
            img.width,
            img.height,
            obs.state_id,
            obs.page.as_deref().unwrap_or("(none)"),
            obs.buttons.len()
        );
    }
    let stat = |v: &mut Vec<f64>| {
        v.sort_by(|a, b| a.partial_cmp(b).unwrap());
        (v[0], v[v.len() / 2], v[v.len() - 1])
    };
    let (gmin, gmed, gmax) = stat(&mut t_grab);
    let (omin, omed, omax) = stat(&mut t_obs);
    println!("=== bench N={n} (raw capture qua PsBridge) ===");
    println!("grab    : min={gmin:5.1} med={gmed:5.1} max={gmax:5.1} ms");
    println!("observe : min={omin:5.1} med={omed:5.1} max={omax:5.1} ms");
    println!("tong med: {:5.1} ms  ({last})", gmed + omed);
    ExitCode::SUCCESS
}

/// inspect: chay perception tren 1 PNG, in ket qua de doi chieu Python.
fn cmd_inspect(args: &[String]) -> ExitCode {
    match args.get(2) {
        Some(p) => cmd_inspect_path(p),
        None => {
            usage();
            ExitCode::from(2)
        }
    }
}

fn cmd_inspect_path(path: &str) -> ExitCode {
    let bytes = match std::fs::read(path) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("khong doc duoc {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let img = match Image::decode_png(&bytes) {
        Ok(i) => i,
        Err(e) => {
            eprintln!("decode that bai: {e}");
            return ExitCode::FAILURE;
        }
    };
    // dung CHINH duong from_frame (resize ve canon cho dhash neu can) de inspect
    // khop production. detect_buttons/loading tinh tren anh GOC -> toa do dung.
    let t_pg = std::time::Instant::now();
    let pg = crate::pages_embed::detector().detect(&img);
    let dt_pg = t_pg.elapsed().as_secs_f64() * 1000.0;
    let obs = crate::protocol::Observation::from_frame(&img, 0.0, None);
    if obs.dhash.is_none() {
        eprintln!("dhash None (anh < {}x{})", eye_core::W, eye_core::H);
        return ExitCode::FAILURE;
    }
    println!("state_id={}", obs.state_id);
    println!("dhash={}", obs.dhash.as_deref().unwrap_or(""));
    println!("is_loading={}", obs.loading);
    println!("size={}x{}", img.width, img.height);
    println!(
        "page={} score={:.3} ({:.1}ms)",
        pg.as_ref().map(|h| h.page.as_str()).unwrap_or("(none)"),
        pg.as_ref().map(|h| h.score).unwrap_or(0.0),
        dt_pg
    );
    println!("buttons={}", obs.buttons.len());
    for b in obs.buttons.iter().take(8) {
        println!("  ({},{}) {}x{} score={:.3}", b.x, b.y, b.w, b.h, b.score);
    }
    ExitCode::SUCCESS
}

/// serve: chon backend roi chay socket server.
fn cmd_serve(args: &[String]) -> ExitCode {
    // parse: serve [addr] [--ps | --file PNG]
    let mut addr = DEFAULT_ADDR.to_string();
    let mut use_ps = false;
    let mut file: Option<String> = None;
    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "--ps" => use_ps = true,
            "--file" => {
                i += 1;
                match args.get(i) {
                    Some(p) => file = Some(p.clone()),
                    None => {
                        eprintln!("--file thieu duong dan");
                        return ExitCode::from(2);
                    }
                }
            }
            a if !a.starts_with('-') => addr = a.to_string(),
            other => {
                eprintln!("tham so la: {other}");
                return ExitCode::from(2);
            }
        }
        i += 1;
    }

    let result = if let Some(path) = file {
        eprintln!("[onmyoji-eye] backend = FileCapture({path})");
        server::serve(&addr, FileCapture::new(path))
    } else if use_ps {
        eprintln!("[onmyoji-eye] backend = PsBridge (server PowerShell)");
        match PsBridge::spawn() {
            Ok(b) => server::serve(&addr, b),
            Err(e) => Err(e),
        }
    } else {
        eprintln!("can chon backend: --ps (game that) hoac --file <PNG> (dev)");
        return ExitCode::from(2);
    };

    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("[onmyoji-eye] loi: {e}");
            ExitCode::FAILURE
        }
    }
}

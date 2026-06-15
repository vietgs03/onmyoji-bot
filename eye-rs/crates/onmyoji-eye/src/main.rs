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
mod protocol;
mod psbridge;
mod server;

use capture::FileCapture;
use eye_core::{detect_buttons, dhash, is_loading, state_id, Image};
use psbridge::PsBridge;

const DEFAULT_ADDR: &str = "127.0.0.1:8765";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str);
    match cmd {
        Some("inspect") => cmd_inspect(&args),
        Some("serve") => cmd_serve(&args),
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
    eprintln!("  (mac dinh addr = {DEFAULT_ADDR})");
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
    match dhash(&img) {
        Some(dh) => {
            println!("state_id={}", state_id(&dh));
            println!("dhash={dh}");
            println!("is_loading={}", is_loading(&img));
            println!("size={}x{}", img.width, img.height);
            let btns = detect_buttons(&img, false);
            println!("buttons={}", btns.len());
            for b in btns.iter().take(8) {
                println!("  ({},{}) {}x{} score={:.3}", b.cx, b.cy, b.w, b.h, b.score);
            }
            ExitCode::SUCCESS
        }
        None => {
            eprintln!("dhash None (anh < {}x{})", eye_core::W, eye_core::H);
            ExitCode::FAILURE
        }
    }
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

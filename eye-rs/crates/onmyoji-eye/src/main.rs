//! onmyoji-eye - binary EYE (capture + CV + socket).
//!
//! TAM THOI (P1): chi la CLI dev de chay perception tren 1 file PNG va in dhash/
//! state_id - dung kiem tra nhanh + so sanh voi Python. Socket server + capture
//! Windows se them o P3.

use std::process::ExitCode;

use eye_core::{dhash, is_loading, state_id, Image};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("dung: onmyoji-eye <anh.png>");
        eprintln!("  in ra: state_id, dhash, is_loading (de doi chieu voi Python)");
        return ExitCode::from(2);
    }
    let path = &args[1];
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
            ExitCode::SUCCESS
        }
        None => {
            eprintln!("dhash None (anh < {}x{})", eye_core::W, eye_core::H);
            ExitCode::FAILURE
        }
    }
}

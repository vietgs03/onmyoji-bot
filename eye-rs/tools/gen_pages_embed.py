"""gen_pages_embed.py - Sinh src/pages_data.rs (nhung manifest + template PNG).

Doc eye-rs/assets/pages/{manifest.json, *.png} -> sinh file Rust co:
  pub const MANIFEST: &str = "...";
  pub fn template_bytes(name: &str) -> Option<&'static [u8]> { match ... }
voi moi PNG nhung qua include_bytes!. Chay lai khi them/bot/cap nhat page.

Chay: python3 eye-rs/tools/gen_pages_embed.py
"""
import json
import os

ROOT = "/home/viethx/onmyoji-bot/eye-rs"
ASSETS = os.path.join(ROOT, "assets/pages")
OUT = os.path.join(ROOT, "crates/onmyoji-eye/src/pages_data.rs")


def main():
    manifest_path = os.path.join(ASSETS, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest_txt = f.read()
    manifest = json.loads(manifest_txt)
    files = [p["file"] for p in manifest["pages"]]

    lines = [
        "// FILE TU DONG SINH boi tools/gen_pages_embed.py - DUNG SUA TAY.",
        "// Nhung manifest + template PNG vao binary (.exe doc lap).",
        "",
    ]
    # MANIFEST: nhung truc tiep tu file (de dong bo tuyet doi)
    lines.append('pub const MANIFEST: &str = include_str!(')
    lines.append(f'    concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/manifest.json"));')
    lines.append("")
    # moi template -> 1 const include_bytes
    for i, fn in enumerate(files):
        rel = f"/../../assets/pages/{fn}"
        lines.append(
            f'const T{i}: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "{rel}"));'
        )
    lines.append("")
    # ham tra bytes theo ten file
    lines.append("pub fn template_bytes(name: &str) -> Option<&'static [u8]> {")
    lines.append("    match name {")
    for i, fn in enumerate(files):
        lines.append(f'        "{fn}" => Some(T{i}),')
    lines.append("        _ => None,")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"da sinh {OUT} voi {len(files)} template nhung")


if __name__ == "__main__":
    main()

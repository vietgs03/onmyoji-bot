#!/usr/bin/env bash
# Onmyoji bot CLI - wrapper around PowerShell control core.
# Coordinates are relative to game window top-left.
#
#   ./onmyoji.sh info
#   ./onmyoji.sh focus
#   ./onmyoji.sh shot [name]          # saves to captures/<name>.png (default: latest)
#   ./onmyoji.sh click X Y
#   ./onmyoji.sh dclick X Y
#   ./onmyoji.sh move X Y
#   ./onmyoji.sh drag X Y X2 Y2 [dur_ms]
#   ./onmyoji.sh key NAME             # e.g. ESC, ENTER, F1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PS_SRC="$ROOT/ps/control.ps1"
WIN_PS="C:\\Users\\Public\\onmyoji_control.ps1"
WIN_PS_WSL="/mnt/c/Users/Public/onmyoji_control.ps1"
CAP_DIR="$ROOT/captures"

# keep windows copy in sync
if [[ ! -f "$WIN_PS_WSL" || "$PS_SRC" -nt "$WIN_PS_WSL" ]]; then
  cp "$PS_SRC" "$WIN_PS_WSL"
fi

run() { powershell.exe -ExecutionPolicy Bypass -File "$WIN_PS" "$@" 2>&1; }

cmd="${1:-info}"; shift || true

case "$cmd" in
  info)   run -Action info ;;
  focus)  run -Action focus ;;
  shot)
    name="${1:-latest}"
    win_out="C:\\Users\\Public\\onmyoji_${name}.png"
    wsl_out="/mnt/c/Users/Public/onmyoji_${name}.png"
    run -Action shot -Out "$win_out" >/dev/null
    cp "$wsl_out" "$CAP_DIR/${name}.png"
    echo "$CAP_DIR/${name}.png"
    ;;
  click)  run -Action click  -X "$1" -Y "$2" ;;
  dclick) run -Action dclick -X "$1" -Y "$2" ;;
  move)   run -Action move   -X "$1" -Y "$2" ;;
  drag)   run -Action drag   -X "$1" -Y "$2" -X2 "$3" -Y2 "$4" -Dur "${5:-500}" ;;
  key)    run -Action key    -Key "$1" ;;
  *) echo "unknown cmd: $cmd"; exit 1 ;;
esac

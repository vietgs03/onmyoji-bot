#!/usr/bin/env bash
# run_full_decompile.sh - Pipeline tu dong dump + dich toan bo code object Onmyoji.
#
# CACH DUNG:
#   ./run_full_decompile.sh            # dump tu game + dich tat ca
#   ./run_full_decompile.sh --decompile-only   # chi dich file dump da co
#
# YEU CAU:
#   - Game Onmyoji dang chay (process Client.exe)
#   - Docker image py27rotor (python:2.7 + rotor)
#   - WSL voi powershell.exe truy cap duoc
set -euo pipefail

cd "$(dirname "$0")/.."
export DOCKER_CONFIG="${DOCKER_CONFIG:-/tmp/dockercfg}"
mkdir -p "$DOCKER_CONFIG"; [ -f "$DOCKER_CONFIG/config.json" ] || echo '{}' > "$DOCKER_CONFIG/config.json"

WORK=/tmp/py27/work
DUMP="$WORK/all_code_dump.txt"
mkdir -p "$WORK"
cp research/npk/opmap_ne.py research/npk/decompiler3.py "$WORK/"

# --- Buoc 1: dump tu RAM game ---
if [ "${1:-}" != "--decompile-only" ]; then
    echo "=== [1/2] Dump code object tu RAM game ==="
    timeout 1800 powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
        "\\\\wsl.localhost\\Ubuntu\\home\\viethx\\onmyoji-bot\\research\\npk\\dump_all_code.ps1" \
        2>&1 | tail -5
    if [ ! -f "$DUMP" ]; then
        echo "LOI: dump that bai (game chua chay?)"; exit 1
    fi
    wc -l "$DUMP"
else
    [ -f "$DUMP" ] || { echo "LOI: khong co $DUMP"; exit 1; }
fi

# --- Buoc 2: dich toan bo ---
echo "=== [2/2] Dich toan bo $(wc -l < "$DUMP") dong dump ==="
docker run --rm -v "$WORK:/work" -w /work py27rotor python2 decompiler3.py /work/all_code_dump.txt \
    > research/npk/notes/decompiled_ALL.py 2>/dev/null

echo "=== Ket qua ==="
echo "  Ham da dich: $(grep -c '^def ' research/npk/notes/decompiled_ALL.py)"
echo "  File: research/npk/notes/decompiled_ALL.py"

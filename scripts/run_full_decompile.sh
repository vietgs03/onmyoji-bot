#!/usr/bin/env bash
# run_full_decompile.sh - Dump RAM game Onmyoji + dich toan bo code + dump toan bo data table.
#
# CACH DUNG:
#   ./scripts/run_full_decompile.sh              # dump code + data tu game, roi decompile
#   ./scripts/run_full_decompile.sh --offline    # chi decompile/merge tu file dump da co
#
# YEU CAU:
#   - Game Onmyoji (client.exe) dang chay, da vao sanh (de nap het module)
#   - Docker image py27unc (python:2.7 + uncompyle6 3.9.2), xem research/npk/README
#   - WSL co powershell.exe
#
# OUTPUT:
#   /tmp/py27/work/codes.jsonl          code object day du (bytecode+consts+lnotab)
#   /tmp/py27/work/src/**.py            source da decompile (uncompyle6 sau khi remap opcode)
#   research/npk/data/cdata/*.json      toan bo data table com.data.* (bindict/taggeddict)
set -euo pipefail
cd "$(dirname "$0")/.."
export DOCKER_CONFIG="${DOCKER_CONFIG:-/tmp/dockercfg}"
mkdir -p "$DOCKER_CONFIG"; [ -f "$DOCKER_CONFIG/config.json" ] || echo '{}' > "$DOCKER_CONFIG/config.json"

WORK=/tmp/py27/work
NPK=research/npk
WINNPK='\\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\research\npk'
mkdir -p "$WORK"
cp "$NPK/decompile_all.py" "$NPK/dc.env" "$WORK/"
cp "$NPK/opmap_ne_learned.json" "$WORK/opmap_final2.json"

if [ "${1:-}" != "--offline" ]; then
  echo "=== [1/4] Dump code objects ==="
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$WINNPK\\pyobj_dump.ps1" \
      -Mode codes -Out '\\wsl.localhost\Ubuntu\tmp\py27\work\codes.jsonl' | tail -2

  echo "=== [2/4] Tim sys.modules + dump data tables ==="
  SM=$(powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$WINNPK\\pyobj_dump.ps1" \
      -Mode sysmodules -Name com.data.cdata_en.equip_attr | grep -o 'sys.modules = 0x[0-9A-F]*' | awk '{print $3}')
  echo "sys.modules=$SM"
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$WINNPK\\pyobj_dump.ps1" \
      -Mode bindicts -Addr "$SM" -Out "$WINNPK\\data\\cdata_raw" | tail -2
fi

echo "=== [3/4] Merge data tables -> $NPK/data/cdata ==="
python3 "$NPK/merge_cdata.py" "$NPK/data/cdata_raw" "$NPK/data/cdata"

echo "=== [4/4] Decompile (uncompyle6) -> $WORK/src ==="
docker run --rm -u "$(id -u):$(id -g)" --env-file "$WORK/dc.env" -v "$WORK:/work" py27unc \
    python2 /work/decompile_all.py /work/src

#!/bin/bash
# run_result_test.sh - 1 lenh: refresh sid+version tu RAM -> cap nhat authmsg ->
#   dungeon_rune_attack (lay rewardId that) -> dungeon_rune_attack_result (GUI THAT).
# Dung cho tai khoan dev test. Do day_limit_pc va stamina truoc/sau.
set -e
cd "$(dirname "$0")"
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
PY=.venv-net/bin/python
WROOT='\\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\research\npk'
DUNGEON_ID="${1:-3}"
HEROES="${2:-5f025569d8459fd8d4bc337c,5f025569d8459fd8d4bc337b,5f0bd6c1ce06853ba8880e90,5e3232384e8e6879c8cf2a53,5f900c59d8459f7fd78b2323,60b39933d8459fb53ad17011,5f025e88d8459fd8d4bc4ac0}"

echo "== [1/3] Doc sid + versions + stamina tu RAM game =="
OUT="$(timeout 300 $PS -NoProfile -ExecutionPolicy Bypass -File "$WROOT\\read_versions.ps1" 2>&1 | tr -d '\r')"
echo "$OUT" | grep -E 'VERSIONS=|SID=|STAMINA=' || true
SID="$(echo "$OUT" | sed -n 's/^SID=//p' | head -1)"
VER="$(echo "$OUT" | sed -n 's/^VERSIONS=//p' | head -1)"

if [ -z "$SID" ] || [ -z "$VER" ]; then
  echo
  echo "[X] CHUA LAY DUOC sid/versions -> game chua chay hoac chua vao sanh."
  echo "    Mo game, dang nhap tai khoan dev test, vao toi man chinh roi chay lai lenh nay."
  exit 1
fi
echo "[OK] sid=$SID versions=$VER"

echo "== [2/3] Cap nhat authmsg_live.bson + session_live.json =="
$PY - "$SID" "$VER" <<'PYEOF'
import bson, json, os, sys
sid, ver = sys.argv[1], sys.argv[2]
d = bson.decode(open('data/authmsg_live.bson','rb').read()) if os.path.exists('data/authmsg_live.bson') else bson.decode(open('data/authmsg.bson','rb').read())
d['session'] = sid; d['versions'] = ver
open('data/authmsg_live.bson','wb').write(bson.encode(d))
s = json.load(open('data/session_live.json')) if os.path.exists('data/session_live.json') else json.load(open('data/session.json'))
s['sid'] = sid; s['authmsg_file'] = 'authmsg_live.bson'
json.dump(s, open('data/session_live.json','w'), indent=1)
print("  authmsg.session =", sid, "| versions =", ver, "| gate", s['gate_port'], "entity", s['entityid'])
PYEOF

echo "== [3/3] attack + GUI result (dungeon_id=$DUNGEON_ID) =="
echo "    (tool resume se da game client ra - binh thuong)"
exec $PY rune_result_demo.py --session data/session_live.json \
  --dungeon-id "$DUNGEON_ID" --attack-first --heroes "$HEROES" --send --listen 20

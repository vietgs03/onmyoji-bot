#!/usr/bin/env bash
# Map toan game: chay NHIEU phien auto_explore lien tiep, moi phien merge vao
# explore_graph_global.json. Theo doi node/frontier tang dan.
#
#   bash scripts/map_loop.sh [SO_PHIEN] [BUDGET_GIAY] [MAX_ACTIONS] [MAX_DEPTH]
#
# Mac dinh: 8 phien x 120s. Log moi phien -> logs/map_loop.log (cong don).
# Sau moi phien in tom tat (node tong, frontier) tu global graph.
set -u
cd "$(dirname "$0")/.." || exit 1

N=${1:-8}
BUDGET=${2:-120}
ACTIONS=${3:-18}
DEPTH=${4:-2}
LOG=logs/map_loop.log
PY=.venv/bin/python3

echo "=== MAP LOOP: $N phien x ${BUDGET}s (actions=$ACTIONS depth=$DEPTH) ===" | tee -a "$LOG"

for i in $(seq 1 "$N"); do
  ts=$(date +%H:%M:%S)
  echo "" | tee -a "$LOG"
  echo "--- [phien $i/$N] $ts ---" | tee -a "$LOG"
  # don server cu (tranh tranh chap PS server)
  bash scripts/kill_server.sh >/dev/null 2>&1
  sleep 1
  # chay 1 phien (foreground, co timeout cung de khong treo)
  timeout $((BUDGET + 60)) "$PY" automation/auto_explore.py \
      --max-actions "$ACTIONS" --max-depth "$DEPTH" --budget-sec "$BUDGET" \
      >> "$LOG" 2>&1
  rc=$?
  echo "[phien $i] exit=$rc" | tee -a "$LOG"
  # tom tat global sau phien
  "$PY" - <<'EOF' | tee -a "$LOG"
import json, os
p = "logs/explore_graph_global.json"
if os.path.exists(p):
    g = json.load(open(p))
    ne = sum(len(n["edges"]) for n in g["nodes"].values())
    front = sum(1 for n in g["nodes"].values()
                if set(n.get("cands", [])) - set(n.get("tried", {})))
    print(f"  GLOBAL: {len(g['nodes'])} node, {ne} edges, {front} node frontier")
EOF
done

echo "" | tee -a "$LOG"
echo "=== XONG. Frontier cuoi: ===" | tee -a "$LOG"
"$PY" automation/auto_explore.py --show-frontier | tee -a "$LOG"

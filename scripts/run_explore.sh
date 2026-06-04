#!/usr/bin/env bash
# Launcher tin cay cho auto_explore (tranh Bash tool nuot setsid).
# Dung: bash scripts/run_explore.sh "<args>"  -> chay nen, log ra logs/explore_run.log
cd "$(dirname "$0")/.." || exit 1
LOG=logs/explore_run.log
: > "$LOG"
setsid .venv/bin/python3 automation/auto_explore.py $@ >> "$LOG" 2>&1 </dev/null &
disown
echo "launched: pid=$! log=$LOG args=$@"

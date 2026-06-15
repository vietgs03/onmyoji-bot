#!/usr/bin/env bash
# scripts/onmyoji-mcp.sh - Khoi dong MCP server cho jcode/Claude.
#
# Mac dinh ONMYOJI_EYE=python (game that). Doi sang fake de test:
#   ONMYOJI_EYE=fake scripts/onmyoji-mcp.sh
#
# Dang ky voi jcode (qua MCP management tool, trong jcode):
#   connect server="onmyoji" command="/home/viethx/onmyoji-bot/scripts/onmyoji-mcp.sh" args=[]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export ONMYOJI_EYE="${ONMYOJI_EYE:-python}"
exec "$ROOT/.venv/bin/python" -m onmyoji.interface.mcp_server

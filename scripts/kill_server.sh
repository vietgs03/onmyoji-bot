#!/bin/bash
# kill_server.sh - Don sach server PowerShell cu + process python cua bot.
# Dung TRUOC moi live run de tranh contention (server cu giu pipe -> Agent() treo).
pkill -9 -f auto_explore 2>/dev/null
pkill -9 -f "automation/_" 2>/dev/null
# kill server PowerShell tren Windows theo command-line (taskkill khong tu sat)
powershell.exe -NoProfile -Command \
  "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { \$_.CommandLine -like '*onmyoji_server*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" \
  >/dev/null 2>&1
sleep 2
n=$(powershell.exe -NoProfile -Command \
  "(Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { \$_.CommandLine -like '*onmyoji_server*' }).Count" 2>/dev/null | tr -d '\r')
echo "servers con lai: ${n:-?}"

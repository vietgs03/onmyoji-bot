#!/usr/bin/env powershell
<#
.SYNOPSIS
  capture_net.ps1 - Bat goi mang cua tien trinh Onmyoji de lay API key / token.

.CACH DUNG
  1. Mo PowerShell (user thuong cung duoc), chay:
       powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\docs\capture_net.ps1
  2. Script TU NANG QUYEN (hien UAC) -> bam Yes.
  3. Doi ~30-60s. Script bat goi cua Client.exe theo PID.
  4. Ket qua: C:\Users\Public\onmyoji_capture.etl  -> chuyen sang text bang:
       pktmon etl2txt C:\Users\Public\onmyoji_capture.etl -o C:\Users\Public\onmyoji_capture.txt

.GHI CHU
  - pktmon la cong cu co san cua Windows, KHONG can cai Wireshark.
  - Bat goi CAN quyen Administrator -> script tu nang quyen.
  - Chi bat goi CUA TIEN TRINH GAME (khong bat ca may) -> nhe va gon hon.
  - LUU Y: luu luong la TLS (443) nen noi dung MA HOA. Tool nay cho:
      + Dia chi IP + cong dich (biet game noi toi dau)
      + Kich thuoc + thoi diem goi (biet luc nao tai bang du lieu)
    Muon doc NOI DUNG ma hoa thi can them buoc MITM (phuc tap hon, xem cuoi file).
#>

$ErrorActionPreference = "Stop"

# --- tu nang quyen ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Can quyen Administrator -> hien UAC, bam Yes..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList @(
        "-NoExit","-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`""
    )
    Write-Host "Da mo cua so moi (quyen Admin). Xem tien do o CUA SO MOI." -ForegroundColor Green
    exit
}

Write-Host "=== BAT GOI MANG - Onmyoji ===" -ForegroundColor Cyan

# --- tim PID game ---
$proc = Get-Process -Name Client,onmyoji -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { Write-Error "Khong thay tien trinh game (Client/onmyoji). Mo game truoc."; exit 1 }
$pid_ = $proc.Id
Write-Host ("Game: {0} PID={1}" -f $proc.ProcessName, $pid_)

# --- ket noi hien tai (chup lai de doi chieu) ---
Write-Host "`nKet noi hien tai cua game:"
Get-NetTCPConnection -OwningProcess $pid_ -EA SilentlyContinue |
    Where-Object { $_.State -eq 'Established' } |
    Select-Object RemoteAddress, RemotePort |
    Sort-Object RemoteAddress -Unique | Format-Table -Auto | Out-String | Write-Host

$etl = "C:\Users\Public\onmyoji_capture.etl"

# --- bat dau bat goi, loc theo PID ---
Write-Host "Bat dau bat goi (chi cua game)... " -ForegroundColor Green
pktmon stop 2>&1 | Out-Null
pktmon filter remove 2>&1 | Out-Null
pktmon start --capture --pkt-size 0 --file-name $etl --comp nics 2>&1 | Out-Null

Write-Host "DANG BAT. Bay gio lam trong game thao tac can do (vd mo man cuong hoa ngự hồn," -ForegroundColor Yellow
Write-Host "cuong hoa 1 lan, mo shop...). Doi 60 giay..." -ForegroundColor Yellow

# --- doi va bao tien do ---
for ($i = 1; $i -le 6; $i++) {
    Start-Sleep -Seconds 10
    $conns = Get-NetTCPConnection -OwningProcess $pid_ -EA SilentlyContinue |
             Where-Object { $_.State -eq 'Established' }
    Write-Host ("  {0}s: {1} ket noi dang mo" -f ($i*10), $conns.Count)
}

# --- dung lai ---
pktmon stop 2>&1 | Out-Null
Write-Host "`nDa dung bat goi." -ForegroundColor Green

if (Test-Path $etl) {
    $mb = (Get-Item $etl).Length / 1MB
    Write-Host ("File: {0}  ({1:N1} MB)" -f $etl, $mb)
    Write-Host "`nChuyen sang text de doc:"
    Write-Host ("  pktmon etl2txt {0} -o C:\Users\Public\onmyoji_capture.txt" -f $etl)
} else {
    Write-Warning "Khong thay file etl. Co the pktmon bi chan (can build/version ho tro)."
}

Write-Host @"

=== BUOC TIEP THEO ===
1. Chuyen etl -> txt:
     pktmon etl2txt $etl -o C:\Users\Public\onmyoji_capture.txt
2. Doc ket qua:
     Select-String -Path C:\Users\Public\onmyoji_capture.txt -Pattern 'IP|Port' | Select -First 50

=== NEU CAN DOC NOI DUNG (TLS ma hoa) ===
Bat goi thuong CHI thay dia chi + kich thuoc, KHONG thay noi dung (TLS).
De doc noi dung can MOT trong hai:
  a) MITM proxy (mitmproxy/Fiddler) + cai cert cua proxy vao Windows trust store.
     Game dung cert pinning? -> co the that bai.
  b) Doc TRUC TIEP tu bo nho tien trinh (khong dung mang) - xem docs/api_probe.md
"@ -ForegroundColor Cyan

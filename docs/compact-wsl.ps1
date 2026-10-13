# compact-wsl.ps1 - Thu hoi dung luong THAT cua o C bang cach nén file ext4.vhdx.
#
# BOI CANH (da kiem chung tren may nay):
#   - vhdx = 497.5 GB, Linux chi dung 340 GB -> ~157 GB block "mo coi" bi giu vo ich.
#   - diskpart compact CHI cat duoc block ma Windows BIET la trong.
#   - Windows biet nho tin hieu TRIM -> phai chay 'sudo fstrim -v /' trong WSL TRUOC.
#   - diskpart BAT BUOC quyen Administrator. Chay bang user thuong se loi:
#       "Program 'diskpart.exe' failed to run: requires elevation"
#     Script nay TU NANG QUYEN (hien hop thoai UAC).
#
# CACH DUNG: mo PowerShell (user thuong cung duoc), chay:
#     powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\docs\compact-wsl.ps1
#
# CANH BAO:
#   - Se TAT WSL (wsl --shutdown) => moi phien WSL dang chay se DUNG.
#   - Du lieu KHONG mat: nén chi cat block trong, khong dung toi du lieu.

$ErrorActionPreference = "Stop"

# --- tu nang quyen Administrator neu chua co ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Can quyen Administrator -> dang hien hop thoai UAC..." -ForegroundColor Yellow
    # mo lai chinh script nay bang quyen admin, giu nguyen cua so
    $args2 = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", "`"$PSCommandPath`"")
    Start-Process powershell -Verb RunAs -ArgumentList $args2
    Write-Host "Da mo cua so PowerShell moi voi quyen Admin. Xem tien do o CUA SO MOI." -ForegroundColor Green
    Write-Host "Cua so nay co the dong." -ForegroundColor Green
    exit
}

Write-Host "=== NEN WSL VHDX (dang chay voi quyen Admin) ===" -ForegroundColor Cyan

# --- tim vhdx cua distro Ubuntu tu registry ---
$base = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss\*' -EA SilentlyContinue |
         Where-Object { $_.DistributionName -like '*Ubuntu*' } |
         Select-Object -First 1).BasePath
if ($base) { $Vhdx = Join-Path $base 'ext4.vhdx' }
else { $Vhdx = "C:\Users\HASAKI\AppData\Local\wsl\{8ea5b67a-f025-4b43-afa7-551446527223}\ext4.vhdx" }

Write-Host "File: $Vhdx"
if (-not (Test-Path $Vhdx)) { Write-Error "Khong tim thay vhdx: $Vhdx"; exit 1 }

$cBefore = (Get-PSDrive C).Free
$vBefore = (Get-Item $Vhdx).Length
Write-Host ("vhdx truoc : {0:N1} GB" -f ($vBefore/1GB))
Write-Host ("o C trong  : {0:N1} GB" -f ($cBefore/1GB))
Write-Host ""

Write-Host "Buoc 1/3: tat WSL..."
wsl --shutdown
Start-Sleep -Seconds 5

Write-Host "Buoc 2/3: nén vhdx (co the mat 1-10 phut)..."
$dp = @"
select vdisk file="$Vhdx"
attach vdisk readonly
compact vdisk
detach vdisk
exit
"@
$tmp = Join-Path $env:TEMP "compact_vhdx.txt"
$dp | Set-Content -Path $tmp -Encoding ASCII
$log = & diskpart /s $tmp 2>&1 | Out-String
Write-Host $log
Remove-Item $tmp -Force -EA SilentlyContinue

$vAfter = (Get-Item $Vhdx).Length
$cAfter = (Get-PSDrive C).Free
Write-Host "Buoc 3/3: ket qua" -ForegroundColor Cyan
Write-Host ("vhdx sau   : {0:N1} GB  (giam {1:N1} GB)" -f ($vAfter/1GB), (($vBefore-$vAfter)/1GB))
Write-Host ("o C trong  : {0:N1} GB  (tang {1:N1} GB)" -f ($cAfter/1GB), (($cAfter-$cBefore)/1GB))

if ($vAfter -ge $vBefore) {
    Write-Host ""
    Write-Host "CANH BAO: vhdx KHONG giam. Nguyen nhan thuong gap:" -ForegroundColor Yellow
    Write-Host "  - Chua chay 'sudo fstrim -v /' trong WSL truoc do."
    Write-Host "  - Hoac diskpart khong chay duoc (khong co quyen Admin)."
    Write-Host "  => Chay fstrim trong WSL, roi chay lai script nay."
} else {
    Write-Host ""
    Write-Host "Xong. Mo lai WSL bang: wsl" -ForegroundColor Green
}

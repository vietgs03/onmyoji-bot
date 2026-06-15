# prof_capture.ps1 - DO BOC TACH tung phase cua PrintWindow capture (chi de do, khong production).
# Tra ket qua: PrintWindow / Clone-crop / PNG-save / BMP-save tung phase (ms).
# Chay: powershell -File prof_capture.ps1 [N=30]
param([int]$N = 30)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Cap {
  [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string n);
  [DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int m);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
Add-Type -AssemblyName System.Drawing

# Tim cua so game GIONG HET server.ps1 (process 'Client' = NeoX engine)
$proc = Get-Process -Name Client -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) {
  $proc = Get-Process | Where-Object {
            $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -match '陰陽師|阴阳师'
          } | Select-Object -First 1
}
if (-not $proc) {
  Write-Output "ERR: khong tim thay cua so game (process Client)"
  exit 1
}
$target = $proc.MainWindowHandle
$titleFound = $proc.MainWindowTitle
Write-Output "WIN: '$titleFound' hwnd=$target"

$r = New-Object Cap+RECT
[Cap]::GetWindowRect($target, [ref]$r) | Out-Null
$w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
Write-Output "SIZE: ${w}x${h}"

$cr = New-Object Cap+RECT
[Cap]::GetClientRect($target, [ref]$cr) | Out-Null
$cw = $cr.Right; $ch = $cr.Bottom

$tmp = $env:TEMP
$sw = [System.Diagnostics.Stopwatch]::new()

# Mang luu thoi gian tung phase
$tPW = @(); $tClone = @(); $tPng = @(); $tBmp = @(); $tTotal = @()

for ($i = 0; $i -lt $N; $i++) {
  $totalSw = [System.Diagnostics.Stopwatch]::StartNew()

  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  $sw.Restart()
  $ok = [Cap]::PrintWindow($target, $hdc, 2)
  $sw.Stop(); $tPW += $sw.Elapsed.TotalMilliseconds
  $g.ReleaseHdc($hdc); $g.Dispose()

  # Clone-crop ve client
  $sw.Restart()
  $rect = New-Object System.Drawing.Rectangle 8, 31, ([Math]::Min($cw, $w-8)), ([Math]::Min($ch, $h-31))
  $clip = $bmp.Clone($rect, $bmp.PixelFormat)
  $sw.Stop(); $tClone += $sw.Elapsed.TotalMilliseconds

  # PNG save
  $sw.Restart()
  $clip.Save("$tmp\prof_c.png", [System.Drawing.Imaging.ImageFormat]::Png)
  $sw.Stop(); $tPng += $sw.Elapsed.TotalMilliseconds

  # BMP save (so sanh: bo encode)
  $sw.Restart()
  $clip.Save("$tmp\prof_c.bmp", [System.Drawing.Imaging.ImageFormat]::Bmp)
  $sw.Stop(); $tBmp += $sw.Elapsed.TotalMilliseconds

  $clip.Dispose(); $bmp.Dispose()
  $totalSw.Stop(); $tTotal += $totalSw.Elapsed.TotalMilliseconds
}

function Stat($arr, $label) {
  $sorted = $arr | Sort-Object
  $min = $sorted[0]; $med = $sorted[[int]($sorted.Count/2)]; $max = $sorted[-1]
  Write-Output ("  {0,-16} min={1,6:N1} med={2,6:N1} max={3,6:N1} ms" -f $label, $min, $med, $max)
}
Write-Output "PHASE (N=$N, bo qua warmup dau):"
# bo 3 lan dau (warmup)
Stat ($tPW | Select-Object -Skip 3) "PrintWindow"
Stat ($tClone | Select-Object -Skip 3) "Clone-crop"
Stat ($tPng | Select-Object -Skip 3) "PNG-save"
Stat ($tBmp | Select-Object -Skip 3) "BMP-save"
Stat ($tTotal | Select-Object -Skip 3) "TOTAL"

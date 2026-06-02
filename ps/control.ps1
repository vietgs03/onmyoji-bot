# Onmyoji control core - all coordinates are RELATIVE to the game window top-left.
# Usage:
#   powershell -File control.ps1 -Action shot   -Out C:\path\out.png
#   powershell -File control.ps1 -Action click  -X 250 -Y 480
#   powershell -File control.ps1 -Action dclick -X 250 -Y 480
#   powershell -File control.ps1 -Action drag   -X 100 -Y 100 -X2 400 -Y2 400 -Dur 600
#   powershell -File control.ps1 -Action move   -X 250 -Y 480
#   powershell -File control.ps1 -Action key    -Key ESC
#   powershell -File control.ps1 -Action info
#   powershell -File control.ps1 -Action focus
# Window is found by ProcessName 'Client' with title matching the game, or by -ProcId.

param(
  [string]$Action = "info",
  [int]$X = 0, [int]$Y = 0,
  [int]$X2 = 0, [int]$Y2 = 0,
  [int]$Dur = 500,
  [int]$ProcId = 0,
  [string]$Key = "",
  [string]$Out = "C:\Users\Public\onmyoji.png",
  [string]$Title = "Onmyoji"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Native {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, IntPtr dwExtraInfo);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int n);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
}
"@

$LEFTDOWN = 0x0002; $LEFTUP = 0x0004

function Get-GameProc {
  if ($ProcId -gt 0) { return Get-Process -Id $ProcId }
  $c = Get-Process | Where-Object { $_.MainWindowTitle -match $Title -or $_.MainWindowTitle -match '陰陽師|阴阳师' }
  if (-not $c) { throw "Game window not found (title match '$Title')" }
  return $c | Select-Object -First 1
}

function Ensure-Front($h) {
  if ([Native]::IsIconic($h)) { [Native]::ShowWindow($h, 9) | Out-Null }
  [Native]::SetForegroundWindow($h) | Out-Null
  Start-Sleep -Milliseconds 150
}

function Get-Rect($h) {
  $r = New-Object Native+RECT
  [Native]::GetWindowRect($h, [ref]$r) | Out-Null
  return $r
}

function Do-ClickAt($sx, $sy, $double=$false) {
  [Native]::SetCursorPos($sx, $sy) | Out-Null
  Start-Sleep -Milliseconds 70
  [Native]::mouse_event($LEFTDOWN,0,0,0,[IntPtr]::Zero)
  Start-Sleep -Milliseconds 50
  [Native]::mouse_event($LEFTUP,0,0,0,[IntPtr]::Zero)
  if ($double) {
    Start-Sleep -Milliseconds 60
    [Native]::mouse_event($LEFTDOWN,0,0,0,[IntPtr]::Zero)
    Start-Sleep -Milliseconds 50
    [Native]::mouse_event($LEFTUP,0,0,0,[IntPtr]::Zero)
  }
}

function Do-Drag($sx,$sy,$ex,$ey,$dur) {
  [Native]::SetCursorPos($sx,$sy) | Out-Null
  Start-Sleep -Milliseconds 80
  [Native]::mouse_event($LEFTDOWN,0,0,0,[IntPtr]::Zero)
  $steps = [Math]::Max(10, [int]($dur/15))
  for ($i=1; $i -le $steps; $i++) {
    $t = $i/$steps
    $cx = [int]($sx + ($ex-$sx)*$t)
    $cy = [int]($sy + ($ey-$sy)*$t)
    [Native]::SetCursorPos($cx,$cy) | Out-Null
    Start-Sleep -Milliseconds ([int]($dur/$steps))
  }
  Start-Sleep -Milliseconds 50
  [Native]::mouse_event($LEFTUP,0,0,0,[IntPtr]::Zero)
}

function Do-Shot($r, $path) {
  Add-Type -AssemblyName System.Drawing
  $w = $r.Right - $r.Left
  $h = $r.Bottom - $r.Top
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
  $bmp.Save($path)
  $g.Dispose(); $bmp.Dispose()
}

$p = Get-GameProc
$h = $p.MainWindowHandle

switch ($Action.ToLower()) {
  "info" {
    $r = Get-Rect $h
    Write-Output ("PID={0} Name={1} Title={2}" -f $p.Id, $p.ProcessName, $p.MainWindowTitle)
    Write-Output ("Left={0} Top={1} Width={2} Height={3}" -f $r.Left, $r.Top, ($r.Right-$r.Left), ($r.Bottom-$r.Top))
  }
  "focus" { Ensure-Front $h; Write-Output "focused" }
  "shot" {
    Ensure-Front $h
    $r = Get-Rect $h
    Do-Shot $r $Out
    Write-Output ("saved {0} ({1}x{2})" -f $Out, ($r.Right-$r.Left), ($r.Bottom-$r.Top))
  }
  "click" {
    Ensure-Front $h; $r = Get-Rect $h
    Do-ClickAt ($r.Left+$X) ($r.Top+$Y) $false
    Write-Output ("click ({0},{1})" -f $X,$Y)
  }
  "dclick" {
    Ensure-Front $h; $r = Get-Rect $h
    Do-ClickAt ($r.Left+$X) ($r.Top+$Y) $true
    Write-Output ("dclick ({0},{1})" -f $X,$Y)
  }
  "move" {
    Ensure-Front $h; $r = Get-Rect $h
    [Native]::SetCursorPos(($r.Left+$X),($r.Top+$Y)) | Out-Null
    Write-Output ("move ({0},{1})" -f $X,$Y)
  }
  "drag" {
    Ensure-Front $h; $r = Get-Rect $h
    Do-Drag ($r.Left+$X) ($r.Top+$Y) ($r.Left+$X2) ($r.Top+$Y2) $Dur
    Write-Output ("drag ({0},{1})->({2},{3})" -f $X,$Y,$X2,$Y2)
  }
  "key" {
    Ensure-Front $h
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.SendKeys]::SendWait("{$Key}")
    Write-Output ("key {0}" -f $Key)
  }
  default { Write-Output "unknown action: $Action" }
}

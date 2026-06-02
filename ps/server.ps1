# Onmyoji control SERVER - persistent PowerShell, doc lenh tu STDIN tung dong.
# Giu san Win32 handle + Add-Type -> moi lenh chi ton thoi gian thuc thi (khong spawn lai).
# Giao thuc (moi dong 1 lenh):
#   bgshot <winpath>           -> ghi anh, in "OK <w>x<h>"
#   bgclick <x> <y>            -> in "OK click x y"
#   info                       -> in "OK PID ... rect ..."
#   ping                       -> in "OK pong"
#   quit                       -> thoat
# Output luon 1 dong bat dau "OK " hoac "ERR ...".
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Native {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int n);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
Add-Type -AssemblyName System.Drawing

$Title = "Onmyoji"
function Get-Handle {
  $c = Get-Process | Where-Object { $_.MainWindowTitle -match $Title -or $_.MainWindowTitle -match '陰陽師|阴阳师' } | Select-Object -First 1
  if (-not $c) { return [IntPtr]::Zero }
  return $c.MainWindowHandle
}

function Do-BgShot($hwnd, $path) {
  $r = New-Object Native+RECT
  [Native]::GetWindowRect($hwnd, [ref]$r) | Out-Null
  $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
  if ($w -le 0 -or $h -le 0) { return @(0,0,$false) }
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  $ok = [Native]::PrintWindow($hwnd, $hdc, 2)
  $g.ReleaseHdc($hdc)
  if (-not $ok) { $hdc2 = $g.GetHdc(); [Native]::PrintWindow($hwnd, $hdc2, 0) | Out-Null; $g.ReleaseHdc($hdc2) }
  $bmp.Save($path)
  $g.Dispose(); $bmp.Dispose()
  return @($w,$h,$ok)
}

function Do-BgClick($hwnd, $x, $y) {
  $WM_MOUSEMOVE=0x0200; $WM_LBUTTONDOWN=0x0201; $WM_LBUTTONUP=0x0202
  $MK_LBUTTON=[IntPtr]0x0001
  $lparam = [IntPtr](($y -shl 16) -bor ($x -band 0xFFFF))
  [Native]::PostMessage($hwnd, $WM_MOUSEMOVE, [IntPtr]::Zero, $lparam) | Out-Null
  [Native]::PostMessage($hwnd, $WM_LBUTTONDOWN, $MK_LBUTTON, $lparam) | Out-Null
  Start-Sleep -Milliseconds (Get-Random -Minimum 60 -Maximum 120)
  [Native]::PostMessage($hwnd, $WM_LBUTTONUP, [IntPtr]::Zero, $lparam) | Out-Null
}

$hwnd = Get-Handle
Write-Output "OK ready"
[Console]::Out.Flush()

while ($true) {
  $line = [Console]::In.ReadLine()
  if ($null -eq $line) { break }
  $line = $line.Trim()
  if ($line -eq "") { continue }
  $parts = $line.Split(" ")
  $cmd = $parts[0].ToLower()
  try {
    if ($hwnd -eq [IntPtr]::Zero) { $hwnd = Get-Handle }
    switch ($cmd) {
      "ping"   { Write-Output "OK pong" }
      "info"   {
        $r = New-Object Native+RECT; [Native]::GetWindowRect($hwnd, [ref]$r) | Out-Null
        Write-Output ("OK rect {0} {1} {2} {3}" -f $r.Left,$r.Top,($r.Right-$r.Left),($r.Bottom-$r.Top))
      }
      "bgshot" {
        $res = Do-BgShot $hwnd $parts[1]
        Write-Output ("OK {0}x{1} pw={2}" -f $res[0],$res[1],$res[2])
      }
      "bgclick" {
        Do-BgClick $hwnd ([int]$parts[1]) ([int]$parts[2])
        Write-Output ("OK click {0} {1}" -f $parts[1],$parts[2])
      }
      "quit"   { Write-Output "OK bye"; break }
      default  { Write-Output ("ERR unknown {0}" -f $cmd) }
    }
  } catch {
    Write-Output ("ERR {0}" -f $_.Exception.Message)
    $hwnd = [IntPtr]::Zero  # reset handle de lan sau tim lai
  }
  [Console]::Out.Flush()
}

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
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, IntPtr dwExtraInfo);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
Add-Type -AssemblyName System.Drawing

$Title = "Onmyoji"
function Get-Handle {
  # Game NeoX engine luon co ProcessName 'Client' + title 陰陽師/Onmyoji.
  # Uu tien match process name de tranh nham browser tab "onmyoji-bot".
  $c = Get-Process -Name Client -ErrorAction SilentlyContinue |
       Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if (-not $c) {
    # fallback: title CJK (chi game co), KHONG match latin 'Onmyoji' (de tranh browser)
    $c = Get-Process | Where-Object {
           $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -match '陰陽師|阴阳师'
         } | Select-Object -First 1
  }
  if (-not $c) { return [IntPtr]::Zero }
  return $c.MainWindowHandle
}

function Restore-Win($hwnd) {
  # SW_RESTORE = 9: bo minimize/maximize, dua cua so ve trang thai binh thuong.
  [Native]::ShowWindow($hwnd, 9) | Out-Null
  Start-Sleep -Milliseconds 120
  [Native]::SetForegroundWindow($hwnd) | Out-Null
  Start-Sleep -Milliseconds 120
}

function Do-BgShot($hwnd, $path) {
  $r = New-Object Native+RECT
  [Native]::GetWindowRect($hwnd, [ref]$r) | Out-Null
  $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
  # Cua so bi minimize (rect 0/qua nho) -> restore roi do lai rect.
  if ($w -le 200 -or $h -le 100) {
    Restore-Win $hwnd
    [Native]::GetWindowRect($hwnd, [ref]$r) | Out-Null
    $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
  }
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

function Do-FgClick($hwnd, $x, $y) {
  # Click thuc (foreground): focus cua so + di chuot toi toa do man hinh + bam.
  # Tin cay tren MOI popup/modal (PostMessage bi mot so modal bo qua).
  $r = New-Object Native+RECT
  [Native]::GetWindowRect($hwnd, [ref]$r) | Out-Null
  $sx = $r.Left + $x; $sy = $r.Top + $y
  [Native]::SetForegroundWindow($hwnd) | Out-Null
  Start-Sleep -Milliseconds 40
  [Native]::SetCursorPos($sx, $sy) | Out-Null
  Start-Sleep -Milliseconds 30
  $LEFTDOWN=0x0002; $LEFTUP=0x0004
  [Native]::mouse_event($LEFTDOWN,0,0,0,[IntPtr]::Zero)
  Start-Sleep -Milliseconds (Get-Random -Minimum 50 -Maximum 100)
  [Native]::mouse_event($LEFTUP,0,0,0,[IntPtr]::Zero)
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
        Do-FgClick $hwnd ([int]$parts[1]) ([int]$parts[2])
        Write-Output ("OK click {0} {1}" -f $parts[1],$parts[2])
      }
      "fgclick" {
        Do-FgClick $hwnd ([int]$parts[1]) ([int]$parts[2])
        Write-Output ("OK fgclick {0} {1}" -f $parts[1],$parts[2])
      }
      "pmclick" {
        Do-BgClick $hwnd ([int]$parts[1]) ([int]$parts[2])
        Write-Output ("OK pmclick {0} {1}" -f $parts[1],$parts[2])
      }
      "restore" {
        Restore-Win $hwnd
        $r = New-Object Native+RECT; [Native]::GetWindowRect($hwnd, [ref]$r) | Out-Null
        Write-Output ("OK restore {0} {1}" -f ($r.Right-$r.Left),($r.Bottom-$r.Top))
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

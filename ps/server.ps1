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
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int n);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT lpPoint);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT lpPoint);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, IntPtr dwExtraInfo);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
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

function Set-ClientSize($hwnd, $cw, $ch) {
  # Dat CLIENT AREA (vung ve game) ve dung $cw x $ch px. Perception cua bot duoc
  # hieu chinh theo 1152x679 (xem knowledge/oas_pagegraph) nen game PHAI dung size
  # nay, neu khong toa do detect/click se lech (bot production KHONG resize anh).
  # Window size = client size + vien (title bar + border). Tinh chenh roi cong bu.
  Restore-Win $hwnd
  $wr = New-Object Native+RECT; [Native]::GetWindowRect($hwnd, [ref]$wr) | Out-Null
  $cr = New-Object Native+RECT; [Native]::GetClientRect($hwnd, [ref]$cr) | Out-Null
  $curCW = $cr.Right; $curCH = $cr.Bottom
  $curWW = $wr.Right - $wr.Left; $curWH = $wr.Bottom - $wr.Top
  # vien = window - client (khong doi khi resize, voi cung window style)
  $borderW = $curWW - $curCW
  $borderH = $curWH - $curCH
  $newWW = $cw + $borderW
  $newWH = $ch + $borderH
  # SWP_NOMOVE=0x2, SWP_NOZORDER=0x4, SWP_SHOWWINDOW=0x40 -> chi DOI kich thuoc
  [Native]::SetWindowPos($hwnd, [IntPtr]::Zero, 0, 0, $newWW, $newWH, 0x46) | Out-Null
  Start-Sleep -Milliseconds 150
  # doc lai client that su (co the bi gioi han min-size)
  $cr2 = New-Object Native+RECT; [Native]::GetClientRect($hwnd, [ref]$cr2) | Out-Null
  return @($cr2.Right, $cr2.Bottom)
}

function Capture-ClientBitmap($hwnd) {
  # Chup window qua PrintWindow roi CAT ve CLIENT AREA. Tra @($bmp, $cw, $ch, $ok)
  # hoac @($null,0,0,$false) neu loi. NGUOI GOI phai Dispose $bmp.
  # Dung chung cho Do-BgShot (luu PNG) va Do-BgShotRaw (gui raw stdout) -> 1 nguon
  # logic capture+crop da kiem chung (fix lech 31px phien 2026-06-10).
  $r = New-Object Native+RECT
  [Native]::GetWindowRect($hwnd, [ref]$r) | Out-Null
  $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
  # Cua so bi minimize (rect 0/qua nho) -> restore roi do lai rect.
  if ($w -le 200 -or $h -le 100) {
    Restore-Win $hwnd
    [Native]::GetWindowRect($hwnd, [ref]$r) | Out-Null
    $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
  }
  if ($w -le 0 -or $h -le 0) { return @($null, 0, 0, $false) }
  $bmp = New-Object System.Drawing.Bitmap $w, $h
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  $ok = [Native]::PrintWindow($hwnd, $hdc, 2)
  $g.ReleaseHdc($hdc)
  if (-not $ok) { $hdc2 = $g.GetHdc(); [Native]::PrintWindow($hwnd, $hdc2, 0) | Out-Null; $g.ReleaseHdc($hdc2) }
  $g.Dispose()
  # FIX BUG LECH 31px (phien duplex 2026-06-10 phat hien): PrintWindow chup CA
  # WINDOW (title bar ~31px + border 8px) nhung click dung toa do CLIENT
  # (ClientToScreen/SendMessage lParam) -> toa do doc tu ANH lech +8,+31 so voi
  # client. Fix tai GOC: CAT anh ve dung CLIENT AREA -> toa do anh == client.
  $cr = New-Object Native+RECT
  [Native]::GetClientRect($hwnd, [ref]$cr) | Out-Null
  $cw = $cr.Right; $ch = $cr.Bottom
  $pt = New-Object Native+POINT; $pt.X = 0; $pt.Y = 0
  [Native]::ClientToScreen($hwnd, [ref]$pt) | Out-Null
  $offX = $pt.X - $r.Left; $offY = $pt.Y - $r.Top
  if ($cw -gt 0 -and $ch -gt 0 -and ($offX -gt 0 -or $offY -gt 0) -and
      ($offX + $cw) -le $w -and ($offY + $ch) -le $h) {
    $rect = New-Object System.Drawing.Rectangle $offX, $offY, $cw, $ch
    $clip = $bmp.Clone($rect, $bmp.PixelFormat)
    $bmp.Dispose()
    return @($clip, $cw, $ch, $ok)
  }
  return @($bmp, $w, $h, $ok)
}

function Do-BgShot($hwnd, $path) {
  $res = Capture-ClientBitmap $hwnd
  $bmp = $res[0]; $cw = $res[1]; $ch = $res[2]; $ok = $res[3]
  if ($null -eq $bmp) { return @(0, 0, $false) }
  $bmp.Save($path)
  $bmp.Dispose()
  return @($cw, $ch, $ok)
}

function Do-BgShotRaw($hwnd) {
  # Chup -> gui RAW BGR24 ra STDOUT (binary), bo qua encode PNG + file 9P.
  # Header ASCII 1 dong "RAW <w> <h> <nbytes>\n" roi <nbytes> byte BGR (top-down,
  # row-major, stride = w*3 KHONG padding). CA header VA binary deu ghi qua RAW
  # stream (OpenStandardOutput) de tranh PowerShell text-pipeline doi encoding/
  # CRLF/thu tu buffer. Phia WSL doc header roi nuot dung so byte -> numpy.
  # Tra @($cw,$ch,$ok).
  $stdout = [System.Console]::OpenStandardOutput()
  $res = Capture-ClientBitmap $hwnd
  $bmp = $res[0]; $cw = $res[1]; $ch = $res[2]; $ok = $res[3]
  if ($null -eq $bmp) {
    $hdr = [System.Text.Encoding]::ASCII.GetBytes("RAW 0 0 0`n")
    $stdout.Write($hdr, 0, $hdr.Length); $stdout.Flush()
    return @(0, 0, $false)
  }
  $rect = New-Object System.Drawing.Rectangle 0, 0, $cw, $ch
  $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly,
                        [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
  $stride = $data.Stride
  $rowBytes = $cw * 3
  $total = $rowBytes * $ch
  $hdr = [System.Text.Encoding]::ASCII.GetBytes("RAW $cw $ch $total`n")
  $stdout.Write($hdr, 0, $hdr.Length)
  if ($stride -eq $rowBytes) {
    # Khong padding: copy 1 phat
    $buf = New-Object byte[] $total
    [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $buf, 0, $total)
    $stdout.Write($buf, 0, $total)
  } else {
    # Co padding cuoi hang (stride > w*3): copy tung hang, loai byte padding
    $rowBuf = New-Object byte[] $rowBytes
    for ($y = 0; $y -lt $ch; $y++) {
      $ptr = [IntPtr]::Add($data.Scan0, $y * $stride)
      [System.Runtime.InteropServices.Marshal]::Copy($ptr, $rowBuf, 0, $rowBytes)
      $stdout.Write($rowBuf, 0, $rowBytes)
    }
  }
  $stdout.Flush()
  $bmp.UnlockBits($data)
  $bmp.Dispose()
  return @($cw, $ch, $ok)
}

function Do-BgShotBoth($hwnd, $path) {
  # CHAN DOAN (dev): chup 1 bitmap, vua LUU PNG vua GUI RAW cua CHINH bitmap do
  # -> kiem transport raw KHONG mat byte (so PNG decode == raw, byte-exact).
  # Header "RAW w h n\n" + binary, GIONG bgshot_raw. KHONG dung production.
  $stdout = [System.Console]::OpenStandardOutput()
  $res = Capture-ClientBitmap $hwnd
  $bmp = $res[0]; $cw = $res[1]; $ch = $res[2]
  if ($null -eq $bmp) {
    $hdr = [System.Text.Encoding]::ASCII.GetBytes("RAW 0 0 0`n")
    $stdout.Write($hdr, 0, $hdr.Length); $stdout.Flush(); return
  }
  $bmp.Save($path)  # luu PNG cua dung bitmap nay
  $rect = New-Object System.Drawing.Rectangle 0, 0, $cw, $ch
  $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly,
                        [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
  $stride = $data.Stride; $rowBytes = $cw * 3; $total = $rowBytes * $ch
  $hdr = [System.Text.Encoding]::ASCII.GetBytes("RAW $cw $ch $total`n")
  $stdout.Write($hdr, 0, $hdr.Length)
  if ($stride -eq $rowBytes) {
    $buf = New-Object byte[] $total
    [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $buf, 0, $total)
    $stdout.Write($buf, 0, $total)
  } else {
    $rowBuf = New-Object byte[] $rowBytes
    for ($y = 0; $y -lt $ch; $y++) {
      $ptr = [IntPtr]::Add($data.Scan0, $y * $stride)
      [System.Runtime.InteropServices.Marshal]::Copy($ptr, $rowBuf, 0, $rowBytes)
      $stdout.Write($rowBuf, 0, $rowBytes)
    }
  }
  $stdout.Flush()
  $bmp.UnlockBits($data)
  $bmp.Dispose()
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

function Do-SendDrag($hwnd, $x0, $y0, $x1, $y1, $steps) {
  # Keo (scroll list) KHONG CHIEM CHUOT: SendMessage down tai (x0,y0) -> nhieu
  # buoc move toi (x1,y1) -> up. Dung de scroll danh sach stage Soul.
  $WM_MOUSEMOVE=0x0200; $WM_LBUTTONDOWN=0x0201; $WM_LBUTTONUP=0x0202
  $MK_LBUTTON=[IntPtr]0x0001
  if ($steps -lt 2) { $steps = 12 }
  $lp0 = [IntPtr]((([int]$y0) -shl 16) -bor (([int]$x0) -band 0xFFFF))
  [Native]::SendMessage($hwnd, $WM_MOUSEMOVE, [IntPtr]::Zero, $lp0) | Out-Null
  [Native]::SendMessage($hwnd, $WM_LBUTTONDOWN, $MK_LBUTTON, $lp0) | Out-Null
  Start-Sleep -Milliseconds 40
  for ($i=1; $i -le $steps; $i++) {
    $x = [int]($x0 + ($x1 - $x0) * $i / $steps)
    $y = [int]($y0 + ($y1 - $y0) * $i / $steps)
    $lp = [IntPtr]((($y) -shl 16) -bor (($x) -band 0xFFFF))
    [Native]::SendMessage($hwnd, $WM_MOUSEMOVE, $MK_LBUTTON, $lp) | Out-Null
    Start-Sleep -Milliseconds 18
  }
  Start-Sleep -Milliseconds 40
  $lp1 = [IntPtr]((([int]$y1) -shl 16) -bor (([int]$x1) -band 0xFFFF))
  [Native]::SendMessage($hwnd, $WM_LBUTTONUP, [IntPtr]::Zero, $lp1) | Out-Null
}

function Do-SendClick($hwnd, $x, $y) {
  # Click KHONG CHIEM CHUOT: SendMessage thang vao hwnd game (NeoX/Win32Window).
  # Game bo qua PostMessage (async) nhung NHAN SendMessage (sync, cho game xu ly).
  # Khong SetForeground, khong SetCursorPos -> chuot user KHONG bi dong toi.
  $WM_MOUSEMOVE=0x0200; $WM_LBUTTONDOWN=0x0201; $WM_LBUTTONUP=0x0202
  $MK_LBUTTON=[IntPtr]0x0001
  $lparam = [IntPtr](($y -shl 16) -bor ($x -band 0xFFFF))
  [Native]::SendMessage($hwnd, $WM_MOUSEMOVE, [IntPtr]::Zero, $lparam) | Out-Null
  [Native]::SendMessage($hwnd, $WM_LBUTTONDOWN, $MK_LBUTTON, $lparam) | Out-Null
  Start-Sleep -Milliseconds (Get-Random -Minimum 60 -Maximum 110)
  [Native]::SendMessage($hwnd, $WM_LBUTTONUP, [IntPtr]::Zero, $lparam) | Out-Null
}

function Do-FgClick($hwnd, $x, $y) {
  # Click thuc (foreground): focus cua so + di chuot toi toa do man hinh + bam.
  # Tin cay tren MOI popup/modal (PostMessage/SendMessage bi mot so modal bo qua).
  # FIX: dung ClientToScreen (toa do anh = CLIENT area, PrintWindow chup client)
  # thay vi GetWindowRect.Left (bao gom title bar/border -> lech ~30px len tren).
  $pt = New-Object Native+POINT
  $pt.X = [int]$x; $pt.Y = [int]$y
  [Native]::ClientToScreen($hwnd, [ref]$pt) | Out-Null
  $sx = $pt.X; $sy = $pt.Y
  [Native]::SetForegroundWindow($hwnd) | Out-Null
  Start-Sleep -Milliseconds 40
  [Native]::SetCursorPos($sx, $sy) | Out-Null
  Start-Sleep -Milliseconds 30
  $LEFTDOWN=0x0002; $LEFTUP=0x0004
  [Native]::mouse_event($LEFTDOWN,0,0,0,[IntPtr]::Zero)
  Start-Sleep -Milliseconds (Get-Random -Minimum 50 -Maximum 100)
  [Native]::mouse_event($LEFTUP,0,0,0,[IntPtr]::Zero)
}

function Do-PoliteClick($hwnd, $x, $y) {
  # Click 'lich su': LUU vi tri chuot cua user -> di chuot toi game -> bam ->
  # TRA chuot ve cho cu NGAY. User chi thay chuot 'nhap nhay' 1 cai rat nhanh,
  # khong mat vi tri/cong viec dang lam. Van can SetForegroundWindow (game
  # DirectX bo qua PostMessage) nhung tra focus/chuot ngay sau.
  $orig = New-Object Native+POINT
  [Native]::GetCursorPos([ref]$orig) | Out-Null      # nho cho chuot user
  # FIX: ClientToScreen (toa do anh = client area) thay GetWindowRect (gom title bar)
  $pt = New-Object Native+POINT
  $pt.X = [int]$x; $pt.Y = [int]$y
  [Native]::ClientToScreen($hwnd, [ref]$pt) | Out-Null
  $sx = $pt.X; $sy = $pt.Y
  [Native]::SetForegroundWindow($hwnd) | Out-Null
  Start-Sleep -Milliseconds 30
  [Native]::SetCursorPos($sx, $sy) | Out-Null
  Start-Sleep -Milliseconds 25
  $LEFTDOWN=0x0002; $LEFTUP=0x0004
  [Native]::mouse_event($LEFTDOWN,0,0,0,[IntPtr]::Zero)
  Start-Sleep -Milliseconds 50
  [Native]::mouse_event($LEFTUP,0,0,0,[IntPtr]::Zero)
  Start-Sleep -Milliseconds 15
  [Native]::SetCursorPos($orig.X, $orig.Y) | Out-Null   # TRA chuot ve cho user
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
      "bgshot_raw" {
        # KHONG Write-Output them: Do-BgShotRaw da tu ghi "RAW w h n\n" + binary.
        [void](Do-BgShotRaw $hwnd)
      }
      "bgshot_both" {
        # CHAN DOAN: luu PNG ($parts[1]) + gui raw cua cung bitmap. KHONG OK them.
        Do-BgShotBoth $hwnd $parts[1]
      }
      "bgclick" {
        Do-SendClick $hwnd ([int]$parts[1]) ([int]$parts[2])
        Write-Output ("OK click {0} {1}" -f $parts[1],$parts[2])
      }
      "sendclick" {
        Do-SendClick $hwnd ([int]$parts[1]) ([int]$parts[2])
        Write-Output ("OK sendclick {0} {1}" -f $parts[1],$parts[2])
      }
      "politeclick" {
        Do-PoliteClick $hwnd ([int]$parts[1]) ([int]$parts[2])
        Write-Output ("OK politeclick {0} {1}" -f $parts[1],$parts[2])
      }
      "senddrag" {
        $st = if ($parts.Count -ge 6) { [int]$parts[5] } else { 12 }
        Do-SendDrag $hwnd ([int]$parts[1]) ([int]$parts[2]) ([int]$parts[3]) ([int]$parts[4]) $st
        Write-Output ("OK senddrag {0} {1} -> {2} {3}" -f $parts[1],$parts[2],$parts[3],$parts[4])
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
      "sizewin" {
        # Dat client area = 1152x679 (mac dinh) hoac WxH neu truyen tham so.
        # Game PHAI dung size nay de toa do detect/click khop perception.
        $cw = if ($parts.Count -gt 1) { [int]$parts[1] } else { 1152 }
        $ch = if ($parts.Count -gt 2) { [int]$parts[2] } else { 679 }
        $res = Set-ClientSize $hwnd $cw $ch
        Write-Output ("OK sizewin {0}x{1}" -f $res[0], $res[1])
      }
      "movewin" {
        # Dua cua so ve toa do tren man chinh (mac dinh 0,0). Giu nguyen kich thuoc.
        # Fix GOC: cua so off-screen (vd 4047,-72) lam politeclick footer that bai.
        # SWP_NOSIZE=0x1, SWP_NOZORDER=0x4, SWP_SHOWWINDOW=0x40 -> chi DOI vi tri.
        $px = if ($parts.Count -gt 1) { [int]$parts[1] } else { 0 }
        $py = if ($parts.Count -gt 2) { [int]$parts[2] } else { 0 }
        Restore-Win $hwnd
        [Native]::SetWindowPos($hwnd, [IntPtr]::Zero, $px, $py, 0, 0, 0x45) | Out-Null
        Start-Sleep -Milliseconds 120
        $r = New-Object Native+RECT; [Native]::GetWindowRect($hwnd, [ref]$r) | Out-Null
        Write-Output ("OK movewin {0} {1}" -f $r.Left, $r.Top)
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

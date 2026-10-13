#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_read.ps1 - Doc sau vung nho da tim duoc, lan theo con tro tim BANG TI LE.

.BOI CANH
  mem_scan.ps1 da tim thay 7 ten bang nam lien nhau tai vung 0x7FF6975Exxxx:
    auto_yuhun_rand_attr_rate, auto_yuhun_single_attr_rate, auto_yuhun_suit_attr_rate,
    auto_yuhun_const, equip_upgrade, rune_random_attr, equip_attr
  Va mot cho khac co chuoi day du: com.data.cdata.equip_attr

.VIEC SCRIPT NAY LAM
  1. Hexdump rong vung quanh cac dia chi do (tim cau truc bang).
  2. Voi moi o nho 8-byte trong vung, COI no la CON TRO -> thu doc xem tro toi dau.
  3. In ra cac con tro doc duoc (de lan theo toi object du lieu).

.CACH DUNG
  powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\docs\mem_read.ps1
#>

$ErrorActionPreference = "Stop"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell -Verb RunAs -ArgumentList @(
        "-NoExit","-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`""
    )
    exit
}

$src = @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public class MemRead {
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out int read);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr h);
    const uint PQI = 0x0400, PVR = 0x0010;

    public static string Dump(int pid, long addr, int len) {
        IntPtr h = OpenProcess(PQI|PVR, false, pid);
        if (h == IntPtr.Zero) return "ERR OpenProcess " + Marshal.GetLastWin32Error();
        try {
            byte[] buf = new byte[len];
            int read;
            if (!ReadProcessMemory(h, (IntPtr)addr, buf, len, out read)) return "ERR read";
            var sb = new StringBuilder();
            for (int i = 0; i < read; i += 16) {
                sb.AppendFormat("0x{0:X12}  ", addr + i);
                for (int j = 0; j < 16; j++) sb.Append(i+j < read ? string.Format("{0:X2} ", buf[i+j]) : "   ");
                sb.Append(" | ");
                for (int j = 0; j < 16 && i+j < read; j++) {
                    byte c = buf[i+j];
                    sb.Append(c >= 32 && c < 127 ? (char)c : '.');
                }
                sb.AppendLine();
            }
            return sb.ToString();
        } finally { CloseHandle(h); }
    }

    // Voi tung 8-byte trong [addr, addr+len), coi la con tro -> thu doc 64 byte
    public static string FollowPtr(int pid, long addr, int len) {
        IntPtr h = OpenProcess(PQI|PVR, false, pid);
        if (h == IntPtr.Zero) return "ERR OpenProcess";
        var sb = new StringBuilder();
        try {
            byte[] buf = new byte[len];
            int read;
            if (!ReadProcessMemory(h, (IntPtr)addr, buf, len, out read)) return "ERR read";
            for (int i = 0; i + 8 <= read; i += 8) {
                long v = BitConverter.ToInt64(buf, i);
                if (v <= 0x10000 || v > 0x7FFFFFFFFFFF) continue;
                byte[] t = new byte[48];
                int r2;
                if (ReadProcessMemory(h, (IntPtr)v, t, 48, out r2) && r2 >= 16) {
                    var vis = new StringBuilder();
                    for (int k = 0; k < Math.Min(r2,32); k++)
                        vis.Append(t[k] >= 32 && t[k] < 127 ? (char)t[k] : '.');
                    sb.AppendFormat("  [0x{0:X}] ptr -> 0x{1:X} : {2}", addr+i, v, vis.ToString());
                    sb.AppendLine();
                }
            }
            return sb.ToString();
        } finally { CloseHandle(h); }
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
$pid_ = $p.Id
Write-Host ("=== DOC BO NHO - PID {0} ===" -f $pid_) -ForegroundColor Cyan

# Vung dang gia nhat: 7 ten bang nam lien nhau (0x7FF6975EDE00..F00)
$base = 0x7FF6975EDE00
Write-Host "`n=== [1] HEXDUMP vung BANG DANG KY (7 ten bang lien nhau) ===" -ForegroundColor Yellow
Write-Host ([MemRead]::Dump($pid_, $base, 400))

Write-Host "`n=== [2] LAN THEO CON TRO trong vung do ===" -ForegroundColor Yellow
Write-Host ([MemRead]::FollowPtr($pid_, $base, 400))

# Vung chuoi ten module day du
$m = 0x1D38B2BC4F0
Write-Host "`n=== [3] HEXDUMP vung 'com.data.cdata.equip_attr' ===" -ForegroundColor Yellow
Write-Host ([MemRead]::Dump($pid_, $m, 400))

Write-Host "`n=== [4] LAN THEO CON TRO vung module name ===" -ForegroundColor Yellow
Write-Host ([MemRead]::FollowPtr($pid_, $m, 400))

Write-Host @"

=== GHI CHU ===
- Muc [2]/[4] in ra cac con tro doc duoc -> do la duong toi object du lieu.
- Neu thay 'ptr -> 0x...' tro toi vung co nhieu so float -> do la bang ti le.
- Gui ket qua cho agent de phan tich tiep.
"@ -ForegroundColor Cyan

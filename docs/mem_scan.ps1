#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_scan.ps1 - Do tim BANG TI LE NGU HON trong bo nho game Onmyoji.

.TAI SAO CACH NAY (khong dung bat goi / API key)
  - Luu luong game la TLS + CO CERT PINNING (thay trong NtUniSdkBase.dll:
    "public key hash: sha256//%s") -> MITM se that bai, bat goi chi thay IP.
  - Nhung bang ti le DA DUOC NAP VAO RAM sau khi game tai xong.
  - => Doc thang tu bo nho: khong dinh TLS, khong can API key.

.CACH LAM
  1. Mo game, dang nhap, MO MAN CUONG HOA NGU HON (de game nap bang).
  2. Chay script nay (tu nang quyen UAC).
  3. Script quet heap cua Client.exe, tim chuoi ten bang:
       auto_yuhun_rand_attr_rate, auto_yuhun_single_attr_rate, ...
  4. In ra DIA CHI + vung nho quanh do (hex) de phan tich tiep.

.KET QUA
  - Tim thay dia chi -> buoc sau: doc cau truc BINDICT (dict Python 2) tai do.
  - Khong tim thay -> bang chua nap; can thao tac trong game (mo man ngự hồn) roi chay lai.

.LUU Y
  - Chi DOC bo nho, KHONG ghi, KHONG sua -> khong lam hong game.
  - Van la can thiep tien trinh: co rui ro voi anti-cheat (xem docs).
#>

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Can quyen Administrator -> hien UAC, bam Yes..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList @(
        "-NoExit","-ExecutionPolicy","Bypass","-File","`"$PSCommandPath`""
    )
    exit
}

$src = @'
using System;
using System.Runtime.InteropServices;
using System.Collections.Generic;
using System.Text;

public class MemScan {
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out int read);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool VirtualQueryEx(IntPtr h, IntPtr addr, out MEMORY_BASIC_INFORMATION mbi, int len);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr h);

    [StructLayout(LayoutKind.Sequential)]
    public struct MEMORY_BASIC_INFORMATION {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public IntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
    }

    const uint PROCESS_QUERY_INFORMATION = 0x0400;
    const uint PROCESS_VM_READ = 0x0010;
    const uint MEM_COMMIT = 0x1000;
    const uint PAGE_GUARD = 0x100;
    const uint PAGE_READWRITE = 0x04;
    const uint PAGE_READONLY = 0x02;
    const uint PAGE_EXECUTE_READ = 0x20;
    const uint PAGE_EXECUTE_READWRITE = 0x40;

    // Quet heap tim chuoi - tra danh sach dia chi
    public static List<string> Scan(int pid, string[] needles, int maxHits) {
        var res = new List<string>();
        IntPtr h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, false, pid);
        if (h == IntPtr.Zero) { res.Add("ERR:OpenProcess that bai, err=" + Marshal.GetLastWin32Error()); return res; }

        IntPtr addr = IntPtr.Zero;
        long scanned = 0, regions = 0;
        MEMORY_BASIC_INFORMATION mbi;
        int mbiSize = Marshal.SizeOf(typeof(MEMORY_BASIC_INFORMATION));
        var needleBytes = new List<byte[]>();
        foreach (var n in needles) {
            var b = Encoding.UTF8.GetBytes(n);
            needleBytes.Add(b);
        }

        try {
            while (VirtualQueryEx(h, addr, out mbi, mbiSize) != false) {
                long rsize = (long)mbi.RegionSize;
                bool readable = mbi.State == MEM_COMMIT && (mbi.Protect & PAGE_GUARD) == 0 &&
                    (mbi.Protect == PAGE_READWRITE || mbi.Protect == PAGE_READONLY ||
                     mbi.Protect == PAGE_EXECUTE_READ || mbi.Protect == PAGE_EXECUTE_READWRITE);
                if (readable && rsize > 0 && rsize < 200L*1024*1024) {
                    regions++;
                    byte[] buf = new byte[rsize];
                    int read;
                    if (ReadProcessMemory(h, mbi.BaseAddress, buf, (int)rsize, out read) && read > 0) {
                        scanned += read;
                        for (int k = 0; k < needleBytes.Count; k++) {
                            var nd = needleBytes[k];
                            for (int i = 0; i + nd.Length <= read; i++) {
                                bool ok = true;
                                for (int j = 0; j < nd.Length; j++) if (buf[i+j] != nd[j]) { ok = false; break; }
                                if (ok) {
                                    long abs = (long)mbi.BaseAddress + i;
                                    res.Add(string.Format("HIT {0} @ 0x{1:X} (region 0x{2:X})",
                                        needles[k], abs, (long)mbi.BaseAddress));
                                    if (res.Count >= maxHits) return res;
                                    break;
                                }
                            }
                        }
                    }
                }
                long next = (long)mbi.BaseAddress + rsize;
                if (next <= (long)addr) break;
                addr = (IntPtr)next;
            }
        } finally { CloseHandle(h); }
        res.Insert(0, string.Format("da quet {0:N0} MB trong {1} vung", scanned/1048576.0, regions));
        return res;
    }

    // Doc hex quanh 1 dia chi
    public static string HexDump(int pid, long addr, int len) {
        IntPtr h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, false, pid);
        if (h == IntPtr.Zero) return "ERR OpenProcess";
        try {
            byte[] buf = new byte[len];
            int read;
            if (!ReadProcessMemory(h, (IntPtr)addr, buf, len, out read)) return "ERR read";
            var sb = new StringBuilder();
            for (int i = 0; i < read; i += 16) {
                sb.AppendFormat("0x{0:X12}  ", addr + i);
                for (int j = 0; j < 16 && i+j < read; j++) sb.AppendFormat("{0:X2} ", buf[i+j]);
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
}
'@

Add-Type -TypeDefinition $src -Language CSharp

$proc = Get-Process -Name Client,onmyoji -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $proc) { Write-Error "Khong thay game. Mo game truoc."; exit 1 }
$pid_ = $proc.Id
Write-Host ("=== QUET BO NHO - {0} PID={1} ({2:N0} MB) ===" -f $proc.ProcessName, $pid_, ($proc.WorkingSet64/1MB)) -ForegroundColor Cyan

# Cac ten bang can tim
$needles = @(
    "auto_yuhun_rand_attr_rate",
    "auto_yuhun_single_attr_rate",
    "auto_yuhun_suit_attr_rate",
    "auto_yuhun_const",
    "equip_upgrade",
    "rune_random_attr",
    "equip_attr"
)
Write-Host "Tim cac chuoi:"; $needles | ForEach-Object { Write-Host "  $_" }
Write-Host "`nDang quet (co the mat 1-3 phut)..." -ForegroundColor Yellow

$t0 = Get-Date
$hits = [MemScan]::Scan($pid_, $needles, 40)
$dt = ((Get-Date) - $t0).TotalSeconds

Write-Host ("`nXong sau {0:N1}s" -f $dt) -ForegroundColor Green
$hits | ForEach-Object { Write-Host $_ }

# Hexdump quanh 3 hit dau
$addrHits = $hits | Where-Object { $_ -like "HIT*" } | Select-Object -First 3
foreach ($h in $addrHits) {
    if ($h -match '0x([0-9A-F]+)') {
        $a = [Convert]::ToInt64($Matches[1], 16)
        Write-Host ("`n=== HEX quanh $h ===") -ForegroundColor Cyan
        Write-Host ([MemScan]::HexDump($pid_, $a - 32, 160))
    }
}

Write-Host @"

=== BUOC TIEP ===
- Neu THAY dia chi: bang da nam trong RAM. Buoc sau: doc cau truc BINDICT
  (dict Python 2) tai dia chi do de lay GIA TRI ti le.
- Neu KHONG thay: mo man cuong hoa ngự hồn trong game (cho game nap bang) roi chay lai.
"@ -ForegroundColor Cyan

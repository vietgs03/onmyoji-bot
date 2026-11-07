#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_entry.ps1 - Dump HEX bang bam cua dict da tim duoc, de tim OFFSET DUNG.

.VAN DE
  mem_find_dict.ps1 tim dung dict that:
    DICT @0x1D38387ED48 used=2763 mask=8191 table=0x1D383942880
    DICT @0x1D3839B8388 used=30   mask=127  table=0x1D3F2811AD0
  Nhung chuoi key bi CAT CUT khong deu (thieu 1, 2, 4 ky tu):
    'dule__' thay 'module__' | 'oad_all' thay 'load_all' | 'ICATE_NAME' thay 'DUPLICATE_NAME'
  => Lech khong co dinh -> khong phai PyStringObject (offset co dinh).
  => Phai XEM HEX cua entry moi biet cau truc that.

.SCRIPT NAY LAM
  1. Dump hex 6 entry dau cua bang bam (moi entry 32 byte) -> thay cau truc.
  2. Voi tung entry, in ra moi CON TRO 8-byte trong do + chuoi no tro toi.
  3. Tu do suy ra offset cua key va value.

.CACH DUNG
  powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\docs\mem_entry.ps1
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
using System.Collections.Generic;

public class PyEnt {
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern IntPtr OpenProcess(uint a, bool i, int pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr h);
    static IntPtr H;
    public static bool Open(int pid){ H=OpenProcess(0x0410,false,pid); return H!=IntPtr.Zero; }
    public static void Close(){ CloseHandle(H); }
    public static byte[] RD(long a,int l){ byte[] b=new byte[l]; int r;
        return ReadProcessMemory(H,(IntPtr)a,b,l,out r)? b:null; }

    public static string DumpHex(long addr,int len){
        var b=RD(addr,len); if(b==null) return "ERR read";
        var sb=new StringBuilder();
        for(int i=0;i<len;i+=16){
            sb.AppendFormat("0x{0:X12}  ", addr+i);
            for(int j=0;j<16;j++) sb.Append(i+j<b.Length? string.Format("{0:X2} ",b[i+j]) : "   ");
            sb.Append(" | ");
            for(int j=0;j<16&&i+j<b.Length;j++){ byte c=b[i+j];
                sb.Append(c>=32&&c<127?(char)c:'.'); }
            sb.AppendLine();
        }
        return sb.ToString();
    }

    // Tai moi offset 8-byte trong [addr,+len), coi la con tro, thu doc chuoi
    public static string Probes(long addr,int len){
        var b=RD(addr,len); if(b==null) return "ERR";
        var sb=new StringBuilder();
        for(int i=0;i+8<=b.Length;i+=8){
            long v=BitConverter.ToInt64(b,i);
            if(v<0x10000 || v>0x7FFFFFFFFFFF) continue;
            var t=RD(v,64);
            if(t==null) continue;
            var s=new StringBuilder(); int k=0;
            while(k<t.Length && t[k]!=0 && t[k]>=32 && t[k]<127 && s.Length<48){ s.Append((char)t[k]); k++; }
            sb.AppendFormat("  +{0,-3} [0x{1:X}] ptr=0x{2:X} -> \"{3}\"", i, addr+i, v,
                            s.Length>0? s.ToString() : "<khong-phai-chuoi>");
            sb.AppendLine();
        }
        return sb.ToString();
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
[PyEnt]::Open($p.Id) | Out-Null
Write-Host ("=== DUMP ENTRY BANG BAM - PID {0} ===" -f $p.Id) -ForegroundColor Cyan

# 2 dict tim duoc o lan truoc
$dicts = @(
  @{ obj = 0x1D38387ED48; used = 2763; mask = 8191; table = 0x1D383942880; ten = "dict lon (used=2763)" },
  @{ obj = 0x1D3839B8388; used = 30;   mask = 127;  table = 0x1D3F2811AD0; ten = "dict nho (used=30)" }
)

foreach ($d in $dicts) {
    Write-Host ("`n############ {0}" -f $d.ten) -ForegroundColor Yellow
    Write-Host ("dict=0x{0:X}  table=0x{1:X}  mask={2}" -f $d.obj, $d.table, $d.mask)
    Write-Host "`n--- HEX 128 byte dau cua bang bam ---" -ForegroundColor Green
    Write-Host ([PyEnt]::DumpHex($d.table, 128))
    Write-Host "--- CON TRO tai tung offset 8-byte + chuoi no tro toi ---" -ForegroundColor Green
    Write-Host ([PyEnt]::Probes($d.table, 128))
    Write-Host "--- HEX 64 byte dau cua CHINH dict object ---" -ForegroundColor Green
    Write-Host ([PyEnt]::DumpHex($d.obj, 64))
}
[PyEnt]::Close()

Write-Host @"

=== CACH DOC KET QUA ===
- Muc 'CON TRO' in ra: offset trong entry -> con tro -> chuoi.
- Offset nao cho ra chuoi DOC DUOC, lien tuc (vd 'module__', 'load_all')
  -> do la offset cua me_key.
- Neu moi offset deu ra chuoi cut -> entry KHONG chua char* truc tiep;
  luc do key co the la PyObject* tro toi struct khac (phai lan tiep).
- Gui ket qua (ca HEX + MUC CON TRO) cho agent.
"@ -ForegroundColor Cyan

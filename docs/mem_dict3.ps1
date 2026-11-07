#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_dict3.ps1 - Doc BINDICT kieu C (entry 16 byte), khong phai PyDictEntry.

.PHAT HIEN QUAN TRONG
  Bang chung cho thay entry KHONG phai 24 byte:
  - dict nho (ma_mask=127, toi da 128 entry) nhung in ra chi so [123] roi [99]
    -> neu entry 24 byte thi chi so khong the vuot 4 (128*24 byte)... 
    thuc te: chi so tinh theo entry size sai -> doc lech.
  - Ti le "khong phai chuoi" rat cao: 3808/3832 (dict lon), 122/128 (dict nho)
    -> doc vao giua cac entry.
  - Tu HEX dump: 0x2880 co [4 byte hash + 4 byte 0][8 byte con tro] = 16 byte.
    Roi 0x2890 la [8 byte con tro][4 byte hash + 4 byte 0] = 16 byte nua.
  => BINDICT cua NeoX dung bang bam C++, ENTRY = 16 BYTE, khong theo CPython.

.SCRIPT NAY LAM
  Thu nhieu kieu entry, in ra kieu nao cho key/value doc duoc:
    A) 16 byte: hash(8) + ptr(8)              -> ptr = key, value o entry ke
    B) 24 byte: hash(8) + key(8) + val(8)     -> kieu CPython (da thu, sai)
    C) 32 byte: hash(8) + key(8) + val(8) + 8 -> co padding
  Voi moi kieu: doc 40 entry dau KHONG trong, in key/value.

.CACH DUNG
  powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\docs\mem_dict3.ps1
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

public class PyD3 {
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
    public static long Q(long a){ var b=RD(a,8); return b==null?0:BitConverter.ToInt64(b,0); }
    static long Q(byte[] b,int o){ return (o+8<=b.Length)? BitConverter.ToInt64(b,o):0; }
    static int I(byte[] b,int o){ return (o+4<=b.Length)? BitConverter.ToInt32(b,o):0; }

    // Doc chuoi: thu PyStringObject (+36) truoc, roi char*
    public static string KStr(long p){
        if(p==0) return null;
        long sz=Q(p+16);
        if(sz>0 && sz<600){
            var b=RD(p+36,(int)sz);
            if(b!=null){ var sb=new StringBuilder(); bool ok=true;
                foreach(var c in b){ if(c<32||c>126){ok=false;break;} sb.Append((char)c); }
                if(ok && sb.Length==(int)sz) return sb.ToString(); }
        }
        // char*
        var t=RD(p,80);
        if(t!=null){ var sb=new StringBuilder();
            for(int i=0;i<t.Length&&t[i]!=0;i++){ if(t[i]<32||t[i]>126) break; sb.Append((char)t[i]); }
            if(sb.Length>=2) return sb.ToString(); }
        return null;
    }

    // Doc bang bam voi entry size cho truoc
    public static string Scan(long table, long mask, int esize, int keyOff, int valOff, int maxOut){
        var sb=new StringBuilder();
        long n=mask+1;
        long need=n*esize;
        if(need<=0 || need>200L*1024*1024){ sb.AppendLine("  (bang qua lon)"); return sb.ToString(); }
        var tb=RD(table,(int)need);
        if(tb==null){ sb.AppendLine("  (khong doc duoc bang)"); return sb.ToString(); }
        int shown=0, miss=0;
        for(long i=0;i<n && shown<maxOut;i++){
            int o=(int)(i*esize);
            if(o+esize>tb.Length) break;
            long kp = keyOff>=0 ? Q(tb,o+keyOff) : 0;
            long vp = valOff>=0 ? Q(tb,o+valOff) : 0;
            string k = KStr(kp);
            if(k==null){ miss++; continue; }
            string v = vp!=0 ? KStr(vp) : null;
            sb.AppendLine(string.Format("    [{0}] \"{1}\"  val={2}", i, k,
                v!=null? "\""+v+"\"" : "0x"+vp.ToString("X")));
            shown++;
        }
        sb.AppendLine(string.Format("    => {0} key doc duoc, {1} entry bo qua", shown, miss));
        return sb.ToString();
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
[PyD3]::Open($p.Id) | Out-Null
Write-Host ("=== THU CAC KIEU ENTRY - PID {0} ===" -f $p.Id) -ForegroundColor Cyan

$cases = @(
  @{ obj=0x1D38387ED48; nama="dict lon" },
  @{ obj=0x1D3839B8388; nama="dict nho" }
)

foreach ($c in $cases) {
    $table=[PyD3]::Q($c.obj+40)
    $mask =[PyD3]::Q($c.obj+32)
    Write-Host ("`n############ {0}  dict=0x{1:X} table=0x{2:X} mask={3}" -f $c.nama,$c.obj,$table,$mask) -ForegroundColor Yellow

    Write-Host "  --- A) entry 16 byte: hash(8)+ptr(8), key@8 ---" -ForegroundColor Green
    Write-Host ([PyD3]::Scan($table,$mask,16,8,-1,25))

    Write-Host "  --- B) entry 16 byte: hash(8)+ptr(8), key@0 (bo 8 hash) ---" -ForegroundColor Green
    Write-Host ([PyD3]::Scan($table,$mask,16,0,-1,25))

    Write-Host "  --- C) entry 32 byte: key@8, val@16 ---" -ForegroundColor Green
    Write-Host ([PyD3]::Scan($table,$mask,32,8,16,25))

    Write-Host "  --- D) entry 24 byte: key@8, val@16 ---" -ForegroundColor Green
    Write-Host ([PyD3]::Scan($table,$mask,24,8,16,25))
}
[PyD3]::Close()

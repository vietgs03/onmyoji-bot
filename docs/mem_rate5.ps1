#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_rate5.ps1 - Doc vung nho quanh cac chuoi Yuhun quan trong.

.PHAT HIEN
  Tim thay trong bo nho cac chuoi:
    0x1D38A2AD6A8 "YuhunMatchConstant"      <- hang so khop ngự hồn
    0x1D38A2915F0 "YuhunAlgo"                <- thuat toan
    0x1D38A2C1C20 "YuhunAlgoGen"
    0x1D38A2ADD70 "yuhun ease calc count:"
    0x1D38A2ADDA8 "yuhun attr ease:"
    0x1D38A2ADDE0 "yuhun attr limit ease:"
    0x1D38A2B23D0 "yuhun attr limit origin:"
  => Cum nay nam canh nhau (0x1D38A2Axxxx..0x1D38A2Cxxxx) -> cung 1 module.
     Nhieu manh giong KEY cua bang tra cuu -> rat co the bang ti le nam day.

.SCRIPT NAY LAM
  1. Dump hex vung 0x1D38A2AD000..0x1D38A2AE000 (quanh cac chuoi 'ease').
  2. Dump hex vung 0x1D38A291000..0x1D38A292000 (quanh 'YuhunAlgo').
  3. Dump hex vung 0x1D38A2C1000..0x1D38A2C2000 (quanh 'YuhunAlgoGen').
  4. Tim cac mang double lien tiep giong bang ti le trong cac vung nay.

.CACH DUNG
  powershell -NoProfile -ExecutionPolicy Bypass -File <duong dan>
#>

$ErrorActionPreference = "Stop"

$src = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;

public class PyR5 {
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern IntPtr OpenProcess(uint a, bool i, int pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr h);
    static IntPtr H;
    public static bool Open(int pid){ H=OpenProcess(0x0410,false,pid); return H!=IntPtr.Zero; }
    public static void Close(){ if(H!=IntPtr.Zero) CloseHandle(H); }
    public static byte[] RD(long a,int l){ byte[] b=new byte[l]; int r;
        return ReadProcessMemory(H,(IntPtr)a,b,l,out r)? b:null; }

    // Dump hex + chuoi (ASCII hien duoc) theo dong 16 byte
    public static List<string> Hex(long baseAddr, int len){
        var res=new List<string>();
        var b=RD(baseAddr,len); if(b==null){ res.Add("  ERR doc"); return res; }
        for(int off=0; off<len; off+=16){
            var hs=new StringBuilder(); var asc=new StringBuilder();
            for(int j=0;j<16 && off+j<len;j++){
                byte c=b[off+j];
                hs.Append(c.ToString("X2")); hs.Append(' ');
                asc.Append(c>=32&&c<=126 ? (char)c : '.');
            }
            res.Add(string.Format("  {0:X12}  {1,-48} {2}", baseAddr+off, hs.ToString(), asc.ToString()));
        }
        return res;
    }

    // Tim mang double lien tiep (>=4) ma gia tri trong [0,1] hoac [1,100]
    public static List<string> FindDoubleRuns(long lo, long hi, int minRun){
        var res=new List<string>();
        var b=RD(lo,(int)(hi-lo)); if(b==null){ res.Add("  ERR doc"); return res; }
        int i=0;
        while(i+8<=b.Length){
            double v=BitConverter.ToDouble(b,i);
            bool okv = (v>=0 && v<=1.0) || (v>=1.0 && v<=100.0);
            if(!okv){ i+=8; continue; }
            int start=i, n=0;
            while(i+8<=b.Length){
                double w=BitConverter.ToDouble(b,i);
                if((w>=0 && w<=1.0) || (w>=1.0 && w<=100.0)){ n++; i+=8; }
                else break;
                if(n>=200) break;
            }
            if(n>=minRun){
                var vals=new List<string>();
                for(int k=0;k<n && k<24;k++){
                    double w=BitConverter.ToDouble(b,start+k*8);
                    vals.Add(w.ToString("G6"));
                }
                res.Add(string.Format("  @0x{0:X}  {1} double: {2}{3}",
                    lo+start, n, string.Join(", ", vals), n>24?", ...":""));
            }
        }
        return res;
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
[PyR5]::Open($p.Id) | Out-Null

$regions = @(
  @{n="quanh 'yuhun attr ease' (0x1D38A2AD000)"; lo=0x1D38A2AD000; hi=0x1D38A2AE000},
  @{n="quanh 'YuhunAlgo' (0x1D38A291000)";       lo=0x1D38A291000; hi=0x1D38A292000},
  @{n="quanh 'YuhunAlgoGen' (0x1D38A2C1000)";    lo=0x1D38A2C1000; hi=0x1D38A2C2000}
)

foreach($r in $regions){
    Write-Host ("=== " + $r.n + " ===") -ForegroundColor Cyan
    ([PyR5]::Hex($r.lo, ($r.hi - $r.lo))) | ForEach-Object { Write-Host $_ }
    Write-Host "  --- mang double ---" -ForegroundColor Yellow
    ([PyR5]::FindDoubleRuns($r.lo, ($r.hi - $r.lo), 4)) | ForEach-Object { Write-Host $_ }
    Write-Host ""
}
[PyR5]::Close()

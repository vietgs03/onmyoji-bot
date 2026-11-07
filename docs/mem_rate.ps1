#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_rate.ps1 - Doc BANG TI LE THAT: da tim thay dict co value la double ti le.

.PHAT HIEN QUAN TRONG (lan chay mem_strict.ps1)
  Tim duoc dict @0x1D385C66B18, used=15, mask=15, TABLE @0x1D386DF1C90.
  16/16 key doc duoc (100%) va VALUE LA DOUBLE TI LE:
     0x3F9EB851EB851EB8 = 0.03
     0x3FB47AE147AE147B = 0.08
     0x3FC999999999999A = 0.2
     0x3FE0000000000000 = 0.5
     0x3FF0000000000000 = 1.0
  => DAY LA BANG TI LE. Nhung key hien ra chi 1 ky tu ("l") -> offset key sai chut.

.SCRIPT NAY LAM
  1. Hexdump bang bam cua dict do (256 byte) -> thay cau truc entry that.
  2. Thu doc key bang NHIEU offset (0,8,16,24,36,40) va in ra.
  3. Doc value double tai nhieu offset -> tim cap (key, value) dung.

.CACH DUNG
  powershell -NoProfile -ExecutionPolicy Bypass -File <duong dan>
#>

$ErrorActionPreference = "Stop"

$src = @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public class PyRate {
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
    public static long Q(long a){ var b=RD(a,8); return b==null?0:BitConverter.ToInt64(b,0); }
    static long Q(byte[] b,int o){ return (o+8<=b.Length)? BitConverter.ToInt64(b,o):0; }
    static double D(byte[] b,int o){ return (o+8<=b.Length)? BitConverter.ToDouble(b,o):0; }

    public static string Hex(long a,int l){
        var b=RD(a,l); if(b==null) return "ERR";
        var sb=new StringBuilder();
        for(int i=0;i<l;i+=16){
            sb.AppendFormat("0x{0:X12}  ", a+i);
            for(int j=0;j<16;j++) sb.Append(i+j<b.Length? string.Format("{0:X2} ",b[i+j]):"   ");
            sb.Append(" | ");
            for(int j=0;j<16&&i+j<b.Length;j++){ byte c=b[i+j]; sb.Append(c>=32&&c<127?(char)c:'.'); }
            sb.AppendLine();
        }
        return sb.ToString();
    }

    static string CStr(long a,int max){
        var b=RD(a,max); if(b==null) return null;
        var sb=new StringBuilder();
        for(int i=0;i<b.Length;i++){ byte c=b[i];
            if(c==0) return sb.Length>0?sb.ToString():null;
            if(c<32||c>126) return null;
            sb.Append((char)c); }
        return null;
    }

    // Thu doc key bang nhieu offset trong 1 entry (entrySize byte)
    public static string Probe(long table, long mask, int esize, int maxEntries){
        long n=mask+1;
        var tb=RD(table,(int)(n*esize)); if(tb==null) return "ERR bang";
        var sb=new StringBuilder();
        int shown=0;
        for(long i=0;i<n && shown<maxEntries;i++){
            int o=(int)(i*esize);
            if(o+esize>tb.Length) break;
            // thu: 8 byte dau co the la hash; key o cac offset
            string line=null;
            for(int ko=0; ko+8<=esize; ko+=8){
                long kp=Q(tb,o+ko); if(kp==0) continue;
                string ks=CStr(kp,80);
                if(ks!=null && ks.Length>=2){ line=string.Format("entry[{0}] keyOff={1} \"{2}\"", i, ko, ks); break; }
            }
            if(line!=null){
                // in them cac double trong entry
                for(int vo=0; vo+8<=esize; vo+=8){
                    double d=D(tb,o+vo);
                    if(d>0 && d<1000) line+=string.Format("  [off{0}]={1:G6}", vo, d);
                }
                sb.AppendLine(line); shown++;
            }
        }
        return sb.ToString();
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
[PyRate]::Open($p.Id) | Out-Null

$dict = 0x1D385C66B18
Write-Host "=== BANG TI LE THAT - dict 0x1D385C66B18 ===" -ForegroundColor Cyan
$table=[PyRate]::Q($dict+40)
$mask =[PyRate]::Q($dict+32)
$used =[PyRate]::Q($dict+24)
Write-Host ("table=0x{0:X}  mask={1}  used={2}" -f $table,$mask,$used)
Write-Host ("`n--- HEX dict (64 byte) ---") 
Write-Host ([PyRate]::Hex($dict,64))
Write-Host ("--- HEX bang bam (256 byte) ---") 
Write-Host ([PyRate]::Hex($table,256))

foreach ($es in 24,32,16) {
    Write-Host ("`n===== THU entry size {0} =====" -f $es) -ForegroundColor Yellow
    Write-Host ([PyRate]::Probe($table,$mask,$es,12))
}
[PyRate]::Close()

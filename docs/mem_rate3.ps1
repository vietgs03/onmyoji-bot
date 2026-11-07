#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_rate3.ps1 - Doc dung: moi entry 24 byte = [8 so][8 ptr TEN BANG][8 double].
                Tat ca entry dung CHUNG 1 con tro ten -> day la MANG gia tri.

.PHAT HIEN
  Bang bam tai table=0x1D386DF1C90, entry 24 byte:
     01 00 00 00 00 00 00 00 | F0 B5 B5 98 F6 7F 00 00 | B8 1E 85 EB 51 B8 9E 3F
     =1                      | ptr TEN = 0x7FF698B5B5F0    | double 0.03
  Entry thu 2 CUNG dung ptr 0x7FF698B5B5F0.
  => Moi entry co cung "key" -> do la TEN BANG (ten bang ti le), khong phai key rieng.

.SCRIPT NAY LAM
  1. Doc chuoi tai con tro ten (0x7FF698B5B5F0) -> biet TEN BANG la gi.
  2. In day du bang gia tri (khong bi gioi han 16 key).
  3. Quet toan bo: tim MOI mang 24-byte-entry co ten bang chua 'yuhun'.

.CACH DUNG
  powershell -NoProfile -ExecutionPolicy Bypass -File <duong dan>
#>

$ErrorActionPreference = "Stop"

$src = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;

public class PyR3 {
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern IntPtr OpenProcess(uint a, bool i, int pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool VirtualQueryEx(IntPtr h, IntPtr a, out MBI m, int l);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr h);
    [StructLayout(LayoutKind.Sequential)]
    public struct MBI { public IntPtr BaseAddress, AllocationBase; public uint AllocationProtect;
                        public IntPtr RegionSize; public uint State, Protect, Type; }
    static IntPtr H;
    public static bool Open(int pid){ H=OpenProcess(0x0410,false,pid); return H!=IntPtr.Zero; }
    public static void Close(){ if(H!=IntPtr.Zero) CloseHandle(H); }
    public static byte[] RD(long a,int l){ byte[] b=new byte[l]; int r;
        return ReadProcessMemory(H,(IntPtr)a,b,l,out r)? b:null; }
    public static long Q(long a){ var b=RD(a,8); return b==null?0:BitConverter.ToInt64(b,0); }
    static long Q(byte[] b,int o){ return (o+8<=b.Length)? BitConverter.ToInt64(b,o):0; }
    static double D(byte[] b,int o){ return (o+8<=b.Length)? BitConverter.ToDouble(b,o):0; }

    public static string CStr(long a,int max){
        if(a==0) return null;
        var b=RD(a,max); if(b==null) return null;
        var sb=new StringBuilder();
        for(int i=0;i<b.Length;i++){ byte c=b[i];
            if(c==0) return sb.Length>0?sb.ToString():null;
            if(c<32||c>126) return null;
            sb.Append((char)c); if(sb.Length>max-1) return null; }
        return null;
    }

    // In bang: doc ten bang + liet ke gia tri
    public static List<string> Read(long dict, int maxVal){
        var res=new List<string>();
        long cnt=Q(dict), table=Q(dict+0x20);
        res.Add(string.Format("  dict=0x{0:X}  count={1}  table=0x{2:X}", dict, cnt, table));
        if(table==0){ res.Add("  (table null)"); return res; }
        var tb=RD(table,(int)Math.Min(cnt,4096)*24);
        if(tb==null){ res.Add("  ERR doc table"); return res; }
        string bk=null;
        int shown=0;
        for(long i=0;i<cnt && i<4096 && shown<maxVal;i++){
            int o=(int)(i*24);
            long kp=Q(tb,o+8); double v=D(tb,o+16);
            if(bk==null){ bk=CStr(kp,120); if(bk!=null) res.Add("  TEN BANG: \""+bk+"\""); }
            res.Add(string.Format("    [{0}] {1:G10}", i, v));
            shown++;
        }
        return res;
    }

    // Quet tim moi mang 24-byte-entry co ten bang chua tu khoa
    public static List<string> ScanNamed(string filter, int maxHits){
        var outl=new List<string>();
        long addr=0;
        MBI mbi; int sz=Marshal.SizeOf(typeof(MBI));
        while(VirtualQueryEx(H,(IntPtr)addr,out mbi,sz)){
            long rs=(long)mbi.RegionSize;
            bool ok = mbi.State==0x1000 && (mbi.Protect&0x100)==0 &&
                      (mbi.Protect==0x04||mbi.Protect==0x02||mbi.Protect==0x20||
                       mbi.Protect==0x40||mbi.Protect==0x80);
            if(ok && rs>=64 && rs<200L*1024*1024){
                var buf=RD((long)mbi.BaseAddress,(int)rs);
                if(buf!=null){
                    for(long off=0; off+24<=buf.Length; off+=8){
                        long cand=(long)mbi.BaseAddress+off;
                        long cnt=Q(buf,(int)off), table=Q(buf,(int)off+8);
                        if(cnt<1 || cnt>5000) continue;
                        if(table<0x10000 || table>0x7FFFFFFFFFFF) continue;
                        // doc entry dau -> lay ten bang
                        var e0=RD(table,24); if(e0==null) continue;
                        long kp=Q(e0,8);
                        string nm=CStr(kp,120);
                        if(nm==null || nm.Length<3) continue;
                        // loc: ten phai la dinh danh (chu/so/gach duoi/.)
                        bool clean=true;
                        foreach(char ch in nm) if(!(char.IsLetterOrDigit(ch)||ch=='_'||ch=='.')){ clean=false; break; }
                        if(!clean) continue;
                        double v0=D(e0,16);
                        if(!(v0>-1e6 && v0<1e6)) continue;
                        if(filter!="" && nm.IndexOf(filter,StringComparison.OrdinalIgnoreCase)<0) continue;
                        outl.Add("=== BANG: \""+nm+"\"  tai 0x"+cand.ToString("X")+
                                 "  count="+cnt+"  table=0x"+table.ToString("X"));
                        foreach(var l in Read(cand, 20)) outl.Add(l);
                        outl.Add("");
                        if(outl.Count/25 >= maxHits) return outl;
                    }
                }
            }
            long nx=(long)mbi.BaseAddress+rs;
            if(nx<=(long)addr) break;
            addr=nx;
        }
        return outl;
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
[PyR3]::Open($p.Id) | Out-Null

Write-Host "=== [1] DICT DA BIET 0x1D385C66B18 ===" -ForegroundColor Cyan
([PyR3]::Read(0x1D385C66B18, 20)) | ForEach-Object { Write-Host $_ }

Write-Host "`n=== [2] QUET BANG CO TEN CHUA 'yuhun' ===" -ForegroundColor Cyan
$t0=Get-Date
$r=[PyR3]::ScanNamed("yuhun", 10)
Write-Host ("Xong {0:N1}s - {1} dong" -f ((Get-Date)-$t0).TotalSeconds, $r.Count) -ForegroundColor Green
$r | ForEach-Object { Write-Host $_ }
[PyR3]::Close()

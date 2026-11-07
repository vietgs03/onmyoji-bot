#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_rate2.ps1 - Doc BANG TI LE voi CAU TRUC DUNG da tim ra.

.CAU TRUC THAT (tu hexdump)
  Bang bam gom cac entry 24 byte, KHONG phai PyDictEntry:
       [0..7]   so nguyen nho (thuong = 1) hoac co the la hash/count
       [8..15]  con tro toi KEY (chuoi C)
       [16..23] GIA TRI DOUBLE nam TRUC TIEP trong entry
  Vi du tu hexdump @0x1D386DF1C90:
     01 00 00 00 00 00 00 00 | F0 B5 B5 98 F6 7F 00 00 | B8 1E 85 EB 51 B8 9E 3F
     =1                      | con tro key              | double 0.03
  => Gia tri la DOUBLE, doc truc tiep, khong phai con tro.

.DICT THAT
  dict=0x1D385C66B18  (ma_used=15, ma_mask=15, table=0x1D386DF1C90)
  Key dau tien: "COLOR_MODE_MUL" (thay trong hexdump cua chinh dict object)

.SCRIPT NAY LAM
  1. Doc bang bam theo entry 24 byte: [8 byte][con tro key][double value].
  2. In cap (key, value) day du.
  3. Quet them dict khac cung cau truc de tim bang ti le ngự hồn.

.CACH DUNG
  powershell -NoProfile -ExecutionPolicy Bypass -File <duong dan>
#>

$ErrorActionPreference = "Stop"

$src = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;

public class PyR2 {
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

    static string CStr(long a,int max){
        if(a==0) return null;
        var b=RD(a,max); if(b==null) return null;
        var sb=new StringBuilder();
        for(int i=0;i<b.Length;i++){ byte c=b[i];
            if(c==0) return sb.Length>0?sb.ToString():null;
            if(c<32||c>126) return null;
            sb.Append((char)c);
            if(sb.Length>max-1) return null; }
        return null;
    }

    // Doc dict theo entry 24 byte: [num][key ptr][double value]
    public static List<string> Rate(long dict, int max){
        var res=new List<string>();
        long used=Q(dict+24), mask=Q(dict+32), table=Q(dict+40);
        if(table==0) table=dict+56;
        long n=mask+1;
        long need=n*24;
        if(need<=0 || need>50L*1024*1024) { res.Add("  (bang qua lon: "+need+" byte)"); return res; }
        var tb=RD(table,(int)need); if(tb==null){ res.Add("  ERR doc bang"); return res; }
        int shown=0, skip=0;
        for(long i=0;i<n && shown<max;i++){
            int o=(int)(i*24);
            long keyPtr=Q(tb,o+8);
            double val=D(tb,o+16);
            string k=CStr(keyPtr,80);
            if(k==null){ skip++; continue; }
            res.Add(string.Format("    \"{0}\" = {1:G8}", k, val));
            shown++;
        }
        res.Insert(0, string.Format("  dict=0x{0:X} used={1} mask={2} table=0x{3:X} | {4} key, {5} bo qua",
            dict,used,mask,table,shown,skip));
        return res;
    }

    // Quet tim moi dict entry-24 co key la chuoi va value la double ti le
    public static List<string> ScanRate(int maxDicts, string filter){
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
                    for(long off=0; off+64<=buf.Length; off+=8){
                        long cand=(long)mbi.BaseAddress+off;
                        long used=Q(buf,(int)off+24), mask=Q(buf,(int)off+32), table=Q(buf,(int)off+40);
                        if(used<3||used>5000) continue;
                        if((mask&(mask+1))!=0) continue;
                        if(mask<3||mask>8192) continue;
                        if(table==0) table=cand+56;
                        // lay mau 24 entry
                        var tb=RD(table,24*24); if(tb==null) continue;
                        int good=0, nonEmpty=0;
                        var hits=new List<string>();
                        for(long i=0;i<24;i++){
                            int o=(int)(i*24);
                            long kp=Q(tb,o+8); double v=D(tb,o+16);
                            if(kp==0) continue;
                            nonEmpty++;
                            string k=CStr(kp,80);
                            if(k==null) continue;
                            if(v>0 && v<=1.0 && k.Length>=3) good++;
                            if(filter!="" && k.IndexOf(filter, StringComparison.OrdinalIgnoreCase)>=0)
                                hits.Add(string.Format("    \"{0}\" = {1:G8}", k, v));
                        }
                        if(nonEmpty>=3 && good*10 >= nonEmpty*6){
                            outl.Add(string.Format("=== dict=0x{0:X} used={1} mask={2} sample OK={3}/{4}",
                                cand,used,mask,good,nonEmpty));
                            foreach(var h in hits) outl.Add(h);
                            foreach(var k in Rate(cand,12)) outl.Add(k);
                            outl.Add("");
                            if(outl.Count/20 >= maxDicts) return outl;
                        }
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
[PyR2]::Open($p.Id) | Out-Null

Write-Host "=== [1] DICT DA BIET (0x1D385C66B18) - cau truc entry 24 byte ===" -ForegroundColor Cyan
([PyR2]::Rate(0x1D385C66B18, 20)) | ForEach-Object { Write-Host $_ }

Write-Host "`n=== [2] QUET TIM BANG TI LE co key chua 'yuhun' ===" -ForegroundColor Cyan
Write-Host "Dang quet..." -ForegroundColor Yellow
$t0=Get-Date
$r=[PyR2]::ScanRate(6,"yuhun")
Write-Host ("Xong sau {0:N1}s" -f ((Get-Date)-$t0).TotalSeconds) -ForegroundColor Green
$r | ForEach-Object { Write-Host $_ }
[PyR2]::Close()

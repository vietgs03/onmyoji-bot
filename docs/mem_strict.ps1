#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_strict.ps1 - Tim BINDICT THAT voi DIEU KIEN CHAT (khong bat nham).

.SUA LOI LAN TRUOC
  Lan truoc kiem tra cau truc qua LONG (chi ma_mask=2^n-1, used<=fill) nen bat
  nham rat nhieu vung nho rac -> chuoi doc ra la manh vun ('(', 'zq', 'aG').
  Ti le doc duoc chi 0.5% o MOI kieu entry => sai tu tang goc, khong phai offset.

.DIEU KIEN CHAT LAN NAY
  1. ma_used >= 5 (dict that co it nhat vai key).
  2. Lay mau toi da 64 entry; doc key theo PyStringObject.
  3. YEU CAU: >= 60% entry khong-trong ma doc duoc key la chuoi ASCII in duoc,
     va so key doc duoc >= 60% cua ma_used.
  4. In ra dict nao DAT -> do la BINDICT that.

.CACH DUNG (goi tu WSL hoac Windows deu duoc, KHONG can Admin)
  powershell -NoProfile -ExecutionPolicy Bypass -File <duong dan>
#>

$ErrorActionPreference = "Stop"

$src = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;

public class PyStrict {
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern IntPtr OpenProcess(uint a, bool i, int pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, int s, out int r);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool VirtualQueryEx(IntPtr h, IntPtr a, out MBI m, int l);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr h);

    [StructLayout(LayoutKind.Sequential)]
    public struct MBI {
        public IntPtr BaseAddress, AllocationBase;
        public uint AllocationProtect;
        public IntPtr RegionSize;
        public uint State, Protect, Type;
    }
    static IntPtr H;
    public static bool Open(int pid){ H=OpenProcess(0x0410,false,pid); return H!=IntPtr.Zero; }
    public static void Close(){ if(H!=IntPtr.Zero) CloseHandle(H); }
    public static byte[] RD(long a,int l){ byte[] b=new byte[l]; int r;
        return ReadProcessMemory(H,(IntPtr)a,b,l,out r)? b:null; }
    public static long Q(long a){ var b=RD(a,8); return b==null?0:BitConverter.ToInt64(b,0); }
    static long Q(byte[] b,int o){ return (o+8<=b.Length)? BitConverter.ToInt64(b,o):0; }

    // Key la chuoi ASCII in duoc, do dai 1..80, ket thuc 0
    static bool IsKey(long p, out string s){
        s=null; if(p==0) return false;
        var b=RD(p,80); if(b==null) return false;
        var sb=new StringBuilder();
        for(int i=0;i<b.Length;i++){
            byte c=b[i];
            if(c==0) { s=sb.Length>0?sb.ToString():null; return sb.Length>0; }
            if(c<32||c>126) return false;
            sb.Append((char)c);
            if(sb.Length>80) return false;
        }
        return false;
    }

    // Kiem tra 1 dia chi co phai dict THAT khong (dieu kien chat)
    public static string Check(long dict, out int goodKeys, out int usedT){
        goodKeys=0; usedT=0;
        var h=RD(dict,64); if(h==null) return null;
        long fill=Q(h,16), used=Q(h,24), mask=Q(h,32), table=Q(h,40);
        if(used<5 || used>100000) return null;
        if(fill<used) return null;
        if((mask & (mask+1))!=0) return null;
        if(mask<7 || mask>1000000) return null;
        if(table==0) table=dict+56;
        long n=mask+1;
        // chi doc toi da 256 entry dau de lay mau
        long sample = n<256? n : 256;
        var tb=RD(table,(int)(sample*24)); if(tb==null) return null;
        int nonEmpty=0;
        for(long i=0;i<sample;i++){
            int o=(int)(i*24);
            if(o+24>tb.Length) break;
            long key=Q(tb,o+8);
            if(key==0) continue;
            nonEmpty++;
            string ks;
            if(IsKey(key,out ks)) goodKeys++;
        }
        if(nonEmpty==0) return null;
        // YEU CAU CHAT: >=60% key doc duoc (tren so entry khong-trong)
        double ratio = (double)goodKeys / nonEmpty;
        if(ratio < 0.6) return null;
        usedT=(int)used;
        return string.Format("dict=0x{0:X} used={1} mask={2} table=0x{3:X} | mau {4} entry: {5} key OK ({6:P0})",
            dict, used, mask, table, nonEmpty, goodKeys, ratio);
    }

    // In key cua dict da xac nhan
    public static List<string> Keys(long dict, int max){
        var res=new List<string>();
        var h=RD(dict,64); if(h==null) return res;
        long mask=Q(h,32), table=Q(h,40), used=Q(h,24);
        if(table==0) table=dict+56;
        long n=mask+1;
        long need=n*24; if(need>200L*1024*1024) return res;
        var tb=RD(table,(int)need); if(tb==null) return res;
        for(long i=0;i<n && res.Count<max;i++){
            int o=(int)(i*24);
            if(o+24>tb.Length) break;
            long key=Q(tb,o+8), val=Q(tb,o+16);
            if(key==0) continue;
            string ks; if(IsKey(key,out ks))
                res.Add(string.Format("    \"{0}\"  val=0x{1:X}", ks, val));
        }
        return res;
    }

    public static List<string> ScanAll(int maxDicts){
        var found=new List<string>();
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
                        int gk,ut;
                        var d=Check(cand,out gk,out ut);
                        if(d!=null){
                            found.Add("=== "+d);
                            foreach(var k in Keys(cand,15)) found.Add(k);
                            found.Add("");
                            if(found.Count/17 >= maxDicts) return found;
                        }
                    }
                }
            }
            long nx=(long)mbi.BaseAddress+rs;
            if(nx<=(long)addr) break;
            addr=nx;
        }
        return found;
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
if (-not [PyStrict]::Open($p.Id)) { Write-Error "OpenProcess that bai"; exit 1 }

Write-Host ("=== TIM BINDICT CHAT - PID {0} ===" -f $p.Id) -ForegroundColor Cyan
Write-Host "Dieu kien: >=60% key doc duoc, used>=5. Dang quet..." -ForegroundColor Yellow
$t0=Get-Date
$res=[PyStrict]::ScanAll(10)
$dt=((Get-Date)-$t0).TotalSeconds
Write-Host ("`nXong sau {0:N1}s - tim thay {1} dong" -f $dt,$res.Count) -ForegroundColor Green
$res | ForEach-Object { Write-Host $_ }
[PyStrict]::Close()

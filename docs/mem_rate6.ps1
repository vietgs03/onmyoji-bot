#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_rate6.ps1 - Tim MANG SO NGUYEN NHO lien tiep (ti le roll dong phu ngự hồn).

.LY DO
  Cac script truoc CHI tim mang double -> BO SOT.
  Ti le roll dong phu ngự hồn la so nguyen nho:
     ATK/DEF/HP/CRITDMG/ACC/RES/ATK%/DEF%/HP% : 3,4,5
     SPD/CRIT                                : 2,3,4
  => Phai tim MANG INT lien tiep chua 2,3,4 hoac 3,4,5.

.DANG BO NHI
  a) int32 lien tiep : 03 00 00 00 04 00 00 00 05 00 00 00
  b) int64 lien tiep : 03 00 00 00 00 00 00 00 04 00 ...
  c) double          : 00 00 00 00 00 00 08 40 (=3.0)

.SCRIPT NAY LAM
  1. Quet toan bo bo nho, tim MOI vi tri co chuoi [2,3,4] hoac [3,4,5]
     lien tiep (int32 hoac int64 hoac double).
  2. Voi moi vi tri, xem lan can co chuoi dai hon giong bang ti le khong.
  3. In ket qua (dia chi + chuoi gia tri) de phan tich.

.CACH DUNG
  powershell -NoProfile -ExecutionPolicy Bypass -File <duong dan>
#>

$ErrorActionPreference = "Stop"

$src = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;

public class PyR6 {
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

    static int I32(byte[] b,int o){ return (o+4<=b.Length)? BitConverter.ToInt32(b,o):int.MinValue; }
    static long I64(byte[] b,int o){ return (o+8<=b.Length)? BitConverter.ToInt64(b,o):long.MinValue; }
    static double D(byte[] b,int o){ return (o+8<=b.Length)? BitConverter.ToDouble(b,o):double.NaN; }

    // Ten dong phu -> chuoi ti le mong doi
    // 3,4,5 : ATK DEF HP CRITDMG ACC RES ATK% DEF% HP%
    // 2,3,4 : SPD CRIT
    // Ta tim MOI chuoi >=3 so nguyen nho (1..100) lien tiep, roi loc.
    public static List<string> Scan(string tag){
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
                if(buf==null){ addr+=(long)rs; continue; }

                // ---- int32: [3][4][5] hoac [2][3][4] ----
                for(int i=0;i+16<=buf.Length;i+=4){
                    int a=I32(buf,i), b=I32(buf,i+4), c=I32(buf,i+8);
                    bool p1 = (a==3&&b==4&&c==5);
                    bool p2 = (a==2&&b==3&&c==4);
                    if(!(p1||p2)) continue;
                    // mo rong chuoi
                    int n=3, j=i+12; var vals=new List<int>{a,b,c};
                    while(j+4<=buf.Length){ int x=I32(buf,j);
                        if(x>=1&&x<=100){ vals.Add(x); n++; j+=4; } else break;
                        if(n>=60) break; }
                    // tim nguoc
                    int k=i-4; var pre=new List<int>();
                    while(k>=0){ int x=I32(buf,k);
                        if(x>=1&&x<=100){ pre.Insert(0,x); k-=4; } else break;
                        if(pre.Count>=60) break; }
                    long sa=(long)mbi.BaseAddress+i;
                    outl.Add(string.Format("  [int32] 0x{0:X}  len={1} : {2}",
                        sa, pre.Count+n, string.Join(",", pre)+ " | " + string.Join(",", vals)));
                }

                // ---- int64: [3][4][5] ----
                for(int i=0;i+24<=buf.Length;i+=8){
                    long a=I64(buf,i), b=I64(buf,i+8), c=I64(buf,i+16);
                    bool p1 = (a==3&&b==4&&c==5);
                    bool p2 = (a==2&&b==3&&c==4);
                    if(!(p1||p2)) continue;
                    int n=3, j=i+24; var vals=new List<long>{a,b,c};
                    while(j+8<=buf.Length){ long x=I64(buf,j);
                        if(x>=1&&x<=100){ vals.Add(x); n++; j+=8; } else break;
                        if(n>=60) break; }
                    long sa=(long)mbi.BaseAddress+i;
                    outl.Add(string.Format("  [int64] 0x{0:X}  len={1} : {2}",
                        sa, n, string.Join(",", vals)));
                }

                // ---- double: 3.0 4.0 5.0 ----
                for(int i=0;i+24<=buf.Length;i+=8){
                    double a=D(buf,i), b=D(buf,i+8), c=D(buf,i+16);
                    bool p1 = (Math.Abs(a-3)<1e-9 && Math.Abs(b-4)<1e-9 && Math.Abs(c-5)<1e-9);
                    bool p2 = (Math.Abs(a-2)<1e-9 && Math.Abs(b-3)<1e-9 && Math.Abs(c-4)<1e-9);
                    if(!(p1||p2)) continue;
                    int n=3, j=i+24; var vals=new List<double>{a,b,c};
                    while(j+8<=buf.Length){ double x=D(buf,j);
                        if(x>=1&&x<=100 && Math.Abs(x-Math.Round(x))<1e-9){ vals.Add(x); n++; j+=8; } else break;
                        if(n>=60) break; }
                    long sa=(long)mbi.BaseAddress+i;
                    outl.Add(string.Format("  [dbl  ] 0x{0:X}  len={1} : {2}",
                        sa, n, string.Join(",", vals)));
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
[PyR6]::Open($p.Id) | Out-Null

Write-Host "=== TIM MANG SO NGUYEN [2,3,4] / [3,4,5] TRONG BO NHO ===" -ForegroundColor Cyan
$t0=Get-Date
$r=[PyR6]::Scan("")
Write-Host ("Xong {0:N1}s - {1} vi tri" -f ((Get-Date)-$t0).TotalSeconds, $r.Count) -ForegroundColor Green
# loc: chi in chuoi dai >=4 (co y nghia)
$r | Where-Object { $_ -match "len=(\d+)" -and [int]$Matches[1] -ge 4 } | Select-Object -First 60 | ForEach-Object { Write-Host $_ }
Write-Host ("`nTong: {0} vi tri, in {1} vi tri dai nhat" -f $r.Count, [Math]::Min(60,$r.Count))
[PyR6]::Close()

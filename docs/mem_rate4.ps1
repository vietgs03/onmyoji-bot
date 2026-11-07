#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_rate4.ps1 - Neo theo du lieu DA BIET de tim bang ti le ngự hồn.

.CHIEN LUOC MOI (khong quet mu)
  Da biet tu du lieu game da tai (data/game_assets):
    - Ten cac dong phu ngự hồn (vi du: "ATK", "CRIT", ... ti le co dinh)
    - Bien the ngự hồn.
  => Thay vi quet toan bo 6GB, ta tim theo CHUOI DAC TRUNG:
     1. Tim moi chuoi trong bo nho chua 'yuhun' hoac ten bang ti le.
     2. Voi moi chuoi tim duoc, xem vung nho lan can co mang double
        giong bang ti le (cac gia tri trong khoang 0..1 hoac 1..100) khong.
     3. In ra vung do.

.CAU TRUC ENTRY (da xac nhan)
  Mang 24-byte-entry: [8 so][8 ptr key][8 double value]
  - Neu moi entry CUNG ptr key => do la MANG gia tri 1 bang.
  - Neu moi entry KHAC ptr key => do la DICT that.

.CACH DUNG
  powershell -NoProfile -ExecutionPolicy Bypass -File <duong dan> <tu khoa>
  Vi du: ... -File mem_rate4.ps1 yuhun
#>

param([string]$Kw = "yuhun")

$ErrorActionPreference = "Stop"

$src = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;

public class PyR4 {
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

    // Tim moi chuoi doc duoc co chua $kw, tra ve (dia chi chuoi, noi dung)
    public static List<string> FindStrings(string kw, int max){
        var res=new List<string>();
        long addr=0;
        MBI mbi; int sz=Marshal.SizeOf(typeof(MBI));
        byte[] nk=Encoding.ASCII.GetBytes(kw.ToLowerInvariant());
        while(VirtualQueryEx(H,(IntPtr)addr,out mbi,sz)){
            long rs=(long)mbi.RegionSize;
            bool ok = mbi.State==0x1000 && (mbi.Protect&0x100)==0 &&
                      (mbi.Protect==0x04||mbi.Protect==0x02||mbi.Protect==0x20||
                       mbi.Protect==0x40||mbi.Protect==0x80);
            if(ok && rs>=64 && rs<200L*1024*1024){
                var buf=RD((long)mbi.BaseAddress,(int)rs);
                if(buf!=null){
                    for(int i=0;i<buf.Length-8;i++){
                        // bat dau chuoi: byte truoc la 0 hoac khong in duoc
                        if(i>0 && buf[i-1]!=0 && buf[i-1]>=32 && buf[i-1]<=126) continue;
                        // so sanh kw (khong phan biet hoa thuong)
                        bool m=true;
                        for(int j=0;j<nk.Length;j++){
                            byte c=buf[i+j];
                            byte lc=(c>='A'&&c<='Z')?(byte)(c+32):c;
                            if(lc!=nk[j]){ m=false; break; }
                        }
                        if(!m) continue;
                        // doc het chuoi
                        var sb=new StringBuilder(); int p=i; bool okc=true;
                        while(p<buf.Length && buf[p]!=0){
                            if(buf[p]<32||buf[p]>126){ okc=false; break; }
                            sb.Append((char)buf[p]); p++;
                            if(sb.Length>120){ okc=false; break; }
                        }
                        if(okc && sb.Length>=3){
                            long sa=(long)mbi.BaseAddress+i;
                            res.Add("0x"+sa.ToString("X")+" | \""+sb.ToString()+"\"");
                            if(res.Count>=max) return res;
                        }
                        i=p;
                    }
                }
            }
            long nx=(long)mbi.BaseAddress+rs;
            if(nx<=(long)addr) break;
            addr=nx;
        }
        return res;
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
[PyR4]::Open($p.Id) | Out-Null

Write-Host "=== TIM CHUOI CHUA '$Kw' TRONG BO NHO ===" -ForegroundColor Cyan
$t0=Get-Date
$r=[PyR4]::FindStrings($Kw, 60)
Write-Host ("Xong {0:N1}s - {1} chuoi" -f ((Get-Date)-$t0).TotalSeconds, $r.Count) -ForegroundColor Green
$r | ForEach-Object { Write-Host $_ }
[PyR4]::Close()

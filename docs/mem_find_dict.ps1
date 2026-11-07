#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_find_dict.ps1 - Tim DICT cua Python trong bo nho game (khong dua vao dia chi cu).

.TAI SAO VIET LAI
  Cach cu that bai: dia chi chuoi ten bang (0x1D3F3476E10) nam trong BYTECODE,
  khong phai PyStringObject -> ob_size doc ra vo nghia -> khong truy nguoc duoc.
  Cach moi: QUET THEO CAU TRUC DICT, khong theo chuoi.
    - Duyet moi vung nho, tai moi dia chi coi la PyDictObject.
    - Kiem tra hop le: ma_mask = 2^n - 1, ma_used <= ma_fill <= mask+1,
      ma_table tro toi vung doc duoc, cac entry co me_key hop le.
    - Dict nao co key la chuoi chua 'yuhun'/'auto_yuhun' -> in ra.

.CACH DUNG
  powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\docs\mem_find_dict.ps1
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
using System.Collections.Generic;
using System.Text;

public class PyFind {
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
    const uint PQI=0x0400, PVR=0x0010, MEM_COMMIT=0x1000, PAGE_GUARD=0x100;

    static IntPtr H;
    public static bool Open(int pid){ H=OpenProcess(PQI|PVR,false,pid); return H!=IntPtr.Zero; }
    public static void Close(){ if(H!=IntPtr.Zero) CloseHandle(H); }

    public static byte[] RD(long addr,int len){
        byte[] b=new byte[len]; int r;
        if(H==IntPtr.Zero) return null;
        return ReadProcessMemory(H,(IntPtr)addr,b,len,out r) ? b : null;
    }
    static long Q(byte[] b,int o){ return (o+8<=b.Length)? BitConverter.ToInt64(b,o) : 0; }

    // doc chuoi tai dia chi (co the la PyStringObject -> ob_sval)
    static string RdStr(long addr,int max){
        var b=RD(addr,max); if(b==null) return null;
        var sb=new StringBuilder();
        for(int i=0;i<b.Length&&b[i]!=0;i++){
            byte c=b[i];
            if(c<32||c>126) return null;      // khong phai chuoi ASCII -> bo
            sb.Append((char)c);
        }
        return sb.Length>0? sb.ToString() : null;
    }

    // Kiem tra 1 dia chi co phai PyDictObject hop le khong
    // Tra ve (true, used, table, mask) neu hop le
    public static bool CheckDict(long addr, out long used, out long table, out long mask){
        used=0; table=0; mask=0;
        var h=RD(addr,64); if(h==null) return false;
        long fill=Q(h,16), usd=Q(h,24), msk=Q(h,32), tbl=Q(h,40);
        if (fill<0 || usd<0 || msk<0) return false;
        if (fill>100000 || usd>100000 || msk>100000) return false;
        if (usd>fill) return false;
        if (fill>msk+1) return false;
        // ma_mask phai la 2^n - 1
        if ((msk & (msk+1))!=0) return false;
        if (msk<7) return false;               // smalltable = 8
        if (tbl==0) tbl=addr+56;               // dung smalltable
        used=usd; table=tbl; mask=msk;
        return true;
    }

    // Doc cac key cua dict, tra ve danh sach (keyStr, keyAddr, valAddr)
    public static List<string[]> Keys(long dict, long used, long table, long mask, int max){
        var res=new List<string[]>();
        long n = (mask>0 && mask<100000) ? mask+1 : 8;
        var tb=RD(table, (int)(n*24));
        if(tb==null) return res;
        for(long i=0;i<n && res.Count<max;i++){
            int o=(int)(i*24);
            if(o+24>tb.Length) break;
            long key=Q(tb,o+8), val=Q(tb,o+16);
            if(key==0) continue;
            // key co the la PyStringObject: ob_sval@36
            string s = RdStr(key+36, 48);
            if(s==null) s = RdStr(key, 48);        // hoac char* truc tiep
            res.Add(new string[]{ i.ToString(), "0x"+key.ToString("X"), "0x"+val.ToString("X"), s??"<non-str>" });
        }
        return res;
    }

    // Quet tim moi dict co key chua tu khoa
    public static List<string> ScanForKeys(string[] needles, int maxDict){
        var outLines=new List<string>();
        long addr=0;
        MBI mbi; int sz=Marshal.SizeOf(typeof(MBI));
        while(VirtualQueryEx(H,(IntPtr)addr,out mbi,sz)){
            long rs=(long)mbi.RegionSize;
            bool ok = mbi.State==MEM_COMMIT && (mbi.Protect&PAGE_GUARD)==0 &&
                      (mbi.Protect==0x04||mbi.Protect==0x02||mbi.Protect==0x20||
                       mbi.Protect==0x40||mbi.Protect==0x80);
            if(ok && rs>=64 && rs<200L*1024*1024){
                var buf=RD((long)mbi.BaseAddress,(int)rs);
                if(buf!=null){
                    for(long off=0; off+64<=buf.Length; off+=8){
                        long cand=(long)mbi.BaseAddress+off;
                        long used,table,mask;
                        if(!CheckDict(cand,out used,out table,out mask)) continue;
                        if(used<1||used>20000) continue;
                        var ks=Keys(cand,used,table,mask,4000);
                        bool hit=false; string found=null;
                        foreach(var k in ks){
                            string s=k[3];
                            if(s==null) continue;
                            foreach(var nd in needles)
                                if(s.Contains(nd)){ hit=true; found=s; break; }
                            if(hit) break;
                        }
                        if(hit){
                            outLines.Add(string.Format("DICT @0x{0:X} used={1} mask={2} table=0x{3:X}",
                                cand,used,mask,table));
                            outLines.Add("  key match: "+found);
                            int shown=0;
                            foreach(var k in ks){
                                if(shown>=25) break;
                                outLines.Add(string.Format("    [{0}] {1} val={2}", k[0], k[3], k[2]));
                                shown++;
                            }
                            outLines.Add("");
                            if(outLines.Count/3 >= maxDict) return outLines;
                        }
                    }
                }
            }
            long nx=(long)mbi.BaseAddress+rs;
            if(nx<=(long)addr) break;
            addr=nx;
        }
        return outLines;
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
[PyFind]::Open($p.Id) | Out-Null
Write-Host ("=== QUET DICT THEO CAU TRUC - PID {0} ===" -f $p.Id) -ForegroundColor Cyan
Write-Host "Tim dict co key chua: yuhun / equip_upgrade / equip_attr / rune_random_attr" -ForegroundColor Yellow
Write-Host "Dang quet (2-5 phut)..." -ForegroundColor Yellow

$t0=Get-Date
$needles=@("yuhun","equip_upgrade","equip_attr","rune_random_attr","auto_yuhun")
$res=[PyFind]::ScanForKeys($needles, 12)
$dt=((Get-Date)-$t0).TotalSeconds

Write-Host ("`nXong sau {0:N1}s - {1} dong ket qua" -f $dt, $res.Count) -ForegroundColor Green
$res | ForEach-Object { Write-Host $_ }
[PyFind]::Close()

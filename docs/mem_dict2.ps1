#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_dict2.ps1 - Doc dict Python bang cach DOC CON TRO TU CHINH DICT (khong nhap tay).

.SUA LOI
  Ban truoc: minh NHAP TAY ma_table = 0x1D383942880 -> SAI (thieu 1 chu so hex).
  Con tro that, doc tu hexdump cua dict:
     0x01D38387ED70: 80 28 94 83 D3 01 00 00  -> 0x01D383842880
                                                        ^ (co '28 94 83 D3')
  => Phai DOC con tro tu bo nho, KHONG duoc chep tay.

.SCRIPT NAY LAM
  1. Tu dia chi dict, doc ma_fill/ma_used/ma_mask/ma_table TRUC TIEP.
  2. In lai cac gia tri do de kiem chung.
  3. Duyet bang bam THAT, in key/value.
  4. Key: thu ca PyStringObject (+36/+40) va char* truc tiep.

.CACH DUNG
  powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\docs\mem_dict2.ps1
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

public class PyD2 {
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
    public static long Q(byte[] b,int o){ return (o+8<=b.Length)? BitConverter.ToInt64(b,o) : 0; }

    // Doc chuoi C tai dia chi
    static string CStr(long a,int max){
        var b=RD(a,max); if(b==null) return null;
        var sb=new StringBuilder();
        for(int i=0;i<b.Length && b[i]!=0;i++){
            if(b[i]<32||b[i]>126) return null;
            sb.Append((char)b[i]);
        }
        return sb.Length>0? sb.ToString():null;
    }

    // Doc PyStringObject: ob_size@16, ob_sval@36 (thu them 40)
    static string PyStr(long obj){
        if(obj==0) return null;
        long sz=Q(obj+16);
        if(sz>0 && sz<600) {
            var b=RD(obj+36,(int)sz);
            if(b!=null){
                var sb=new StringBuilder(); bool ok=true;
                foreach(var c in b) { if(c<32||c>126){ok=false;break;} sb.Append((char)c); }
                if(ok && sb.Length==sz) return sb.ToString();
            }
        }
        return null;
    }

    // In dict: doc het truong, in bang bam
    public static string Dump(long dict,int maxKeys){
        var sb=new StringBuilder();
        var h=RD(dict,64);
        if(h==null) return "ERR doc dict";
        long fill=Q(h,16), used=Q(h,24), mask=Q(h,32), table=Q(h,40);
        sb.AppendLine(string.Format("dict=0x{0:X}", dict));
        sb.AppendLine(string.Format("  ma_fill={0}  ma_used={1}  ma_mask={2}", fill,used,mask));
        sb.AppendLine(string.Format("  ma_table=0x{0:X}  (doc TU BO NHO, khong nhap tay)", table));
        if(mask<0||mask>100000) return sb.ToString()+"  ma_mask bat thuong";
        if(table==0) { table=dict+56; sb.AppendLine("  (dung smalltable)"); }
        long n=mask+1;
        // entry 24 byte (hash8,key8,val8) - thu truoc
        long need=n*24;
        if(need>0 && need<100L*1024*1024){
            var tb=RD(table, (int)need);
            if(tb!=null){
                int shown=0, notstr=0;
                sb.AppendLine("  --- entry size 24 (hash,key,val) ---");
                for(long i=0;i<n && shown<maxKeys;i++){
                    int o=(int)(i*24);
                    long key=Q(tb,o+8), val=Q(tb,o+16);
                    if(key==0) continue;
                    string k = PyStr(key);
                    if(k==null) k = CStr(key,64);
                    if(k==null){ notstr++; continue; }
                    sb.AppendLine(string.Format("    [{0}] \"{1}\"  val=0x{2:X}", i, k, val));
                    shown++;
                }
                if(shown==0) sb.AppendLine("    (khong doc duoc key nao - entry size co the khac)");
                if(notstr>0) sb.AppendLine("    (bo qua "+notstr+" entry khong phai chuoi)");
            }
        }
        return sb.ToString();
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
[PyD2]::Open($p.Id) | Out-Null
Write-Host ("=== DOC DICT (doc con tro tu bo nho) - PID {0} ===" -f $p.Id) -ForegroundColor Cyan

# 2 dict tim duoc
$dicts = @(0x1D38387ED48, 0x1D3839B8388)
foreach ($d in $dicts) {
    Write-Host "`n############ dict 0x$('{0:X}' -f $d) ############" -ForegroundColor Yellow
    Write-Host ([PyD2]::Dump($d, 30))
}
[PyD2]::Close()
Write-Host @"

=== NEU VAN CHUOI CAT ===
Neu entry size 24 khong ra key, thu entry size 16 hoac 32 -> bao agent.
Ket qua quan trong: ma_table doc tu bo nho phai la 0x1D383842880 (khong phai
0x1D383942880 nhu lan truoc - da nhap sai 1 chu so hex).
"@ -ForegroundColor Cyan

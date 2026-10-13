#!/usr/bin/env powershell
<#
.SYNOPSIS
  mem_dict.ps1 - Tim doi tuong STR cua ten bang, roi truy nguoc tim DICT chua no.
                Doc gia tri ti le tu dict (CPython 2.7 64-bit).

.BOI CANH
  - python27.dll -> CPython 2.7, 64-bit.
  - Layout struct (byte):
      PyObject_HEAD = 16 (refcnt 0..7, type 8..15)
      PyDictObject: ma_fill@16, ma_used@24, ma_mask@32, ma_table@40, smalltable@56
      PyDictEntry : me_hash@0, me_key@8, me_value@16 (size 24)
      PyStringObj : ob_size@16, ob_shash@24, ob_sstate@32, ob_sval@36
      PyIntObject : ob_ival@16 | PyFloatObject: ob_fval@16
  - Chuoi ten bang da tim thay (UTF-8) tai cac dia chi trong lan quet truoc.

.CACH LAM
  1. Voi dia chi chuoi da biet, lui ve dau doi tuong: ob_sval@36 -> obj = addr-36.
  2. Quet heap tim o nho 8 byte == addr cua doi tuong str do (do la me_key trong dict).
  3. Tai cho tim thay, doc nguoc 8 byte (me_value) va 16 byte (me_hash).
  4. In ra key + value -> neu value la dict/int/float thi in tiep.

.CACH DUNG
  powershell -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\docs\mem_dict.ps1
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

public class PyMem {
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
    const uint PQI=0x0400, PVR=0x0010, MEM_COMMIT=0x1000, PAGE_GUARD=0x100;

    static IntPtr H; static int PID;
    public static bool Open(int pid) {
        PID=pid; H=OpenProcess(PQI|PVR,false,pid); return H!=IntPtr.Zero;
    }
    public static void Close(){ if(H!=IntPtr.Zero) CloseHandle(H); }

    public static byte[] RD(long addr, int len) {
        byte[] b=new byte[len]; int r;
        if (H==IntPtr.Zero) return null;
        return ReadProcessMemory(H,(IntPtr)addr,b,len,out r) ? b : null;
    }
    public static long Q(long addr){ var b=RD(addr,8); return b==null?0:BitConverter.ToInt64(b,0); }
    public static uint D(long addr){ var b=RD(addr,4); return b==null?0:BitConverter.ToUInt32(b,0); }
    public static double F(long addr){ var b=RD(addr,8); return b==null?0:BitConverter.ToDouble(b,0); }
    public static string Str(long addr,int max) {
        var b=RD(addr,max); if(b==null) return "<null>";
        var sb=new StringBuilder();
        for(int i=0;i<b.Length && b[i]!=0;i++) sb.Append((char)b[i]);
        return sb.ToString();
    }

    // Doc PyStringObject tai dia chi obj -> chuoi
    public static string PyStr(long obj) {
        if (obj==0) return "<null>";
        long sz=Q(obj+16);                 // ob_size
        if (sz<=0 || sz>512) return "<bad size "+sz+">";
        var b=RD(obj+36, (int)sz);
        return b==null ? "<unreadable>" : Encoding.UTF8.GetString(b);
    }

    // Doc PyObject -> mo ta ngan (kieu + gia tri neu la int/float/str)
    public static string PyRepr(long obj) {
        if (obj==0) return "None";
        long typ=Q(obj+8);
        if (typ==0) return "<?>";
        // doc ten type: PyTypeObject.tp_name @ +24 (PyObject_VAR_HEAD + ...)
        // PyTypeObject: ob_refcnt,ob_type,ob_size @16, tp_name @24
        long namePtr=Q(typ+24);
        string tn = namePtr!=0 ? Str(namePtr,32) : "?";
        if (tn.Contains("str"))  return "'" + PyStr(obj) + "'";
        if (tn.Contains("int"))  return Q(obj+16).ToString();
        if (tn.Contains("float")) return F(obj+16).ToString("G6");
        if (tn.Contains("dict")) return "<dict>";
        if (tn.Contains("list")) return "<list>";
        return "<"+tn+">";
    }

    // Quet heap tim o 8-byte == target (tim me_key tro toi obj)
    public static List<long> FindPtr(long target, int maxHits) {
        var res=new List<long>();
        long addr=0; long scanned=0;
        MBI mbi; int sz=Marshal.SizeOf(typeof(MBI));
        while (VirtualQueryEx(H,(IntPtr)addr,out mbi,sz)) {
            long rs=(long)mbi.RegionSize;
            bool ok = mbi.State==MEM_COMMIT && (mbi.Protect & PAGE_GUARD)==0 &&
                      (mbi.Protect==0x04||mbi.Protect==0x02||mbi.Protect==0x20||
                       mbi.Protect==0x40||mbi.Protect==0x80);
            if (ok && rs>0 && rs<200L*1024*1024) {
                var buf=RD((long)mbi.BaseAddress,(int)rs);
                if (buf!=null) {
                    scanned+=buf.Length;
                    for(int i=0;i+8<=buf.Length;i+=8) {
                        if (BitConverter.ToInt64(buf,i)==target) {
                            res.Add((long)mbi.BaseAddress+i);
                            if (res.Count>=maxHits) return res;
                        }
                    }
                }
            }
            long nx=(long)mbi.BaseAddress+rs;
            if (nx<=(long)addr) break;
            addr=nx;
        }
        return res;
    }

    // Doc dict: in toi da N entry
    public static string DumpDict(long dict, int maxEntries) {
        if (dict==0) return "  <dict null>";
        long fill=Q(dict+16), used=Q(dict+24), mask=Q(dict+32);
        long table=Q(dict+40);
        var sb=new StringBuilder();
        sb.AppendLine(string.Format("  dict@0x{0:X} fill={1} used={2} mask={3} table=0x{4:X}",
            dict, fill, used, mask, table));
        if (table==0) table=dict+56;      // smalltable
        long n = (mask>0 && mask<10000) ? mask+1 : 8;
        int shown=0;
        for (long i=0;i<n && shown<maxEntries;i++) {
            long e = table + i*24;
            long key=Q(e+8), val=Q(e+16);
            if (key==0) continue;
            sb.AppendLine(string.Format("    [{0}] {1} = {2}", i, PyRepr(key), PyRepr(val)));
            shown++;
        }
        if (shown==0) sb.AppendLine("    <khong co entry / chua doc dung>");
        return sb.ToString();
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Error "Game chua chay"; exit 1 }
$pid_ = $p.Id
[PyMem]::Open($pid_) | Out-Null
Write-Host ("=== TIM DICT CHUA BANG TI LE - PID {0} ===" -f $pid_) -ForegroundColor Cyan

# Dia chi chuoi ten bang (tim duoc o lan quet truoc). Neu game restart thi phai chay lai mem_scan.ps1
$strAddrs = @{
  "auto_yuhun_rand_attr_rate"   = 0x1D3F3476E10
  "auto_yuhun_single_attr_rate" = 0x1D3F3476E90
  "auto_yuhun_suit_attr_rate"   = 0x1D3F3476E50
  "auto_yuhun_const"            = 0x1D3F3477E18
}

foreach ($k in $strAddrs.Keys) {
    $sval = $strAddrs[$k]
    Write-Host "`n### $k" -ForegroundColor Yellow
    $txt = [PyMem]::Str($sval, 64)
    Write-Host ("  ob_sval @ 0x{0:X} : '{1}'" -f $sval, $txt)

    # Doi tuong str bat dau truoc ob_sval 36 byte
    $obj = $sval - 36
    $sz  = [PyMem]::Q($obj+16)
    Write-Host ("  => obj str @ 0x{0:X}  ob_size={1}" -f $obj, $sz)
    if ($sz -ne $k.Length) {
        Write-Host "     (ob_size KHONG khop -> thu offset 40)" -ForegroundColor DarkYellow
        foreach ($off in 40,44,48) {
            $o2 = $sval - $off
            $s2 = [PyMem]::Q($o2+16)
            if ($s2 -eq $k.Length) { Write-Host ("     => DUNG offset {0}: obj @ 0x{1:X}" -f $off,$o2); $obj=$o2; break }
        }
    }

    # Tim con tro toi obj nay (me_key trong dict entry)
    Write-Host "  Tim con tro toi obj trong heap..." -ForegroundColor DarkGray
    $refs = [PyMem]::FindPtr($obj, 6)
    Write-Host ("  -> {0} noi tim thay" -f $refs.Count)
    foreach ($r in $refs) {
        # me_key @ r => entry bat dau tai r-8, dict entry: hash@-8,key@0,value@+8
        $val = [PyMem]::Q($r+8)
        $hash = [PyMem]::Q($r-8)
        Write-Host ("     ref@0x{0:X}  hash={1}  value=0x{2:X} {3}" -f $r, $hash, $val, [PyMem]::PyRepr($val))
    }
}
[PyMem]::Close()
Write-Host @"

=== NEU KET QUA RONG ===
Game co the da restart -> dia chi doi. Chay lai mem_scan.ps1 de lay dia chi moi,
roi sua bien strAddrs trong file nay.
"@ -ForegroundColor Cyan

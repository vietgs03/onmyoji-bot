<#
.SYNOPSIS
  dump_all_code.ps1 - Dump TOAN BO PyCodeObject tu RAM game Onmyoji.

.DINH DANG XUAT (giong full_yuhun_equip_dump.txt)
  ### 'name'  @0xADDR  argc=N nloc=M stack=S
  V|varname1|varname2|...
  N|name1|name2|...
  C|const1|const2|...
  B|84 01 00 ...

.LAYOUT PyCodeObject g37
  +0 refcnt | +8 type=base+0x36B7540 | +16 argc | +20 nloc | +24 stack
  +28 flags | +32 co_code | +40 co_consts | +48 co_names | +56 co_varnames
  +64 freevars | +72 cellvars | +80 co_filename | +88 co_name
.LAYOUT PyString g37
  +0 refcnt | +8 type=base+0x36B57B0 | +16 size | +24 hash | +32 sval
#>

param([string]$OutFile = "\\wsl.localhost\Ubuntu\tmp\py27\work\all_code_dump.txt")
$ErrorActionPreference="Stop"

$src = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
using System.IO;

public class CodeDump {
    [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint a,bool i,int pid);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool VirtualQueryEx(IntPtr h,IntPtr a,out MBI m,int l);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [StructLayout(LayoutKind.Sequential)] public struct MBI {
        public IntPtr BaseAddress, AllocationBase; public uint AllocationProtect;
        public IntPtr RegionSize; public uint State, Protect, Type; }
    static IntPtr H;
    // RVA co dinh trong client.exe (xac minh 2026-10-14: base 0x7FF74D350000)
    public const long CODE_RVA = 0x36B7540L;
    public const long STR_RVA  = 0x36B57B0L;
    static long CODE_TYPE, STR_TYPE, MOD_BASE;
    public static void Init(long modBase){ MOD_BASE=modBase; CODE_TYPE=modBase+CODE_RVA; STR_TYPE=modBase+STR_RVA; }

    public static bool Open(int pid){ H=OpenProcess(0x0410,false,pid); return H!=IntPtr.Zero; }
    public static void Close(){ if(H!=IntPtr.Zero) CloseHandle(H); }
    static byte[] RD(long a,int l){ byte[] b=new byte[l]; int r;
        return ReadProcessMemory(H,(IntPtr)a,b,l,out r)? b:null; }
    static long Q(long a){ var b=RD(a,8); return b==null?-1:BitConverter.ToInt64(b,0); }

    static string PyStr(long a){
        if(a<=0) return null;
        var h=RD(a,24); if(h==null) return null;
        long sz=BitConverter.ToInt64(h,16);
        if(sz<0||sz>20000) return null;
        var d=RD(a+32,(int)sz); if(d==null) return null;
        var sb=new StringBuilder();
        foreach(byte c in d){ if(c<32||c>126) return null; sb.Append((char)c); }
        return sb.ToString();
    }
    static string PyStrRaw(long a, out bool ok){
        ok=false; if(a<=0) return null;
        var h=RD(a,24); if(h==null) return null;
        long sz=BitConverter.ToInt64(h,16);
        if(sz<0||sz>200) return null;
        var d=RD(a+32,(int)sz); if(d==null) return null;
        var sb=new StringBuilder();
        foreach(byte c in d){ if(c<9||(c>13&&c<32)||c>126) return null; sb.Append((char)c); }
        ok=true; return sb.ToString();
    }
    static List<long> PySeq(long a){
        var res=new List<long>(); if(a<=0) return res;
        var h=RD(a,24); if(h==null) return res;
        long sz=BitConverter.ToInt64(h,16);
        if(sz<0||sz>2000) return res;
        var d=RD(a+24,(int)sz*8); if(d==null) return res;
        for(int i=0;i<sz;i++) res.Add(BitConverter.ToInt64(d,i*8));
        return res;
    }
    static string CRepr(long a){
        bool ok; string s=PyStrRaw(a,out ok);
        if(ok){
            if(s==null) return "";
            return s.Replace("|","\\p").Replace("\n","\\n").Replace("\r","\\r").Replace("\t","\\t");
        }
        long t=Q(a+8);
        if(t>MOD_BASE+0x3660000L && t<MOD_BASE+0x3B60000L){
            var iv=RD(a+16,8);
            if(iv!=null){ long v=BitConverter.ToInt64(iv,0); if(v>=-100000000 && v<=100000000) return v.ToString(); }
            return "None";
        }
        return "None";
    }

    public static long Dump(TextWriter w){
        long count=0; long addr=0; MBI mbi; int sz=Marshal.SizeOf(typeof(MBI));
        var seen=new HashSet<long>();
        while(VirtualQueryEx(H,(IntPtr)addr,out mbi,sz)){
            long rs=(long)mbi.RegionSize;
            bool ok=mbi.State==0x1000 && (mbi.Protect&0x100)==0 &&
                    (mbi.Protect==0x04||mbi.Protect==0x02||mbi.Protect==0x20||mbi.Protect==0x40||mbi.Protect==0x80);
            if(ok && rs>=64 && rs<200L*1024*1024){
                long p=(long)mbi.BaseAddress; long end=p+rs;
                while(p<end){
                    int n=(int)Math.Min(262144,end-p);
                    var c=RD(p,n); if(c==null){ p+=n; continue; }
                    for(int i=0;i+96<=c.Length;i+=8){
                        long typ=BitConverter.ToInt64(c,i+8);
                        if(typ!=CODE_TYPE) continue;
                        int argc=BitConverter.ToInt32(c,i+16);
                        int nloc=BitConverter.ToInt32(c,i+20);
                        int stack=BitConverter.ToInt32(c,i+24);
                        if(argc<0||argc>30||nloc<0||nloc>120||stack<0||stack>500) continue;
                        long co=p+i;
                        if(seen.Contains(co)) continue;
                        seen.Add(co);
                        long pcode=BitConverter.ToInt64(c,i+32);
                        long pconsts=BitConverter.ToInt64(c,i+40);
                        long pnames=BitConverter.ToInt64(c,i+48);
                        long pvarnames=BitConverter.ToInt64(c,i+56);
                        long pfile=BitConverter.ToInt64(c,i+80);
                        long pname=BitConverter.ToInt64(c,i+88);
                        string nm=PyStr(pname), fn=PyStr(pfile);
                        w.WriteLine("### '{0}'  @0x{1:X}  argc={2} nloc={3} stack={4}",
                            nm==null?"?":nm, co, argc, nloc, stack);
                        var vn=PySeq(pvarnames).ConvertAll(x=>PyStr(x)??"?");
                        w.WriteLine("V|"+string.Join("|",vn.ToArray()));
                        var nn=PySeq(pnames).ConvertAll(x=>PyStr(x)??"?");
                        w.WriteLine("N|"+string.Join("|",nn.ToArray()));
                        var cc=PySeq(pconsts).ConvertAll(x=>CRepr(x));
                        w.WriteLine("C|"+string.Join("|",cc.ToArray()));
                        if(pcode>0){
                            long csz=Q(pcode+16);
                            if(csz>0 && csz<100000){
                                var b=RD(pcode+32,(int)csz);
                                if(b!=null) w.WriteLine("B|"+BitConverter.ToString(b).Replace("-"," "));
                            }
                        }
                        w.WriteLine();
                        count++;
                    }
                    p+=n;
                }
            }
            long nx=(long)mbi.BaseAddress+rs; if(nx<=(long)addr) break; addr=nx;
        }
        return count;
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp

$p = Get-Process -Name Client,onmyoji -EA SilentlyContinue | Select-Object -First 1
if(-not $p){ Write-Host "GAME CHUA CHAY - khong the dump"; exit 1 }
[CodeDump]::Open($p.Id) | Out-Null
$base = $p.MainModule.BaseAddress.ToInt64()
[CodeDump]::Init($base)
Write-Host ("client.exe base=0x{0:X} code_type=0x{1:X}" -f $base, ($base+[CodeDump]::CODE_RVA))
Write-Host ("Dang dump tu PID {0} ..." -f $p.Id)
$t0=Get-Date
$w = New-Object System.IO.StreamWriter($OutFile,$false,[System.Text.Encoding]::UTF8)
$n = [CodeDump]::Dump($w)
$w.Close()
Write-Host ("Da dump {0} code object sau {1:N1}s -> {2}" -f $n,((Get-Date)-$t0).TotalSeconds,$OutFile)
[CodeDump]::Close()

<#
pyobj_dump.ps1 - Doc object Python 2.7 tu RAM game Onmyoji ra JSON.

CACH DUNG
  -Mode findname -Name DATA_EQUIP_RANDOM_ATTR
      Tim PyString co noi dung Name, roi tim cac dict entry co key = string do,
      in ra value (type name + dia chi).
  -Mode dump -Addr 0x... -Depth 8 -Out file.json
      Serialize object tai Addr ra JSON (dict/list/tuple/int/long/float/str/unicode/bool/None,
      module -> __dict__, object khac -> {"__type__":name,"__addr__":...,"__dict__":...}).
  -Mode modattr -Name <ten bien import> -Attr data -Out file.json
      findname + lay value (module/object) + lay thuoc tinh Attr trong __dict__ + dump.

LAYOUT (CPython 2.7 x64)
  PyObject: +0 refcnt +8 ob_type
  PyTypeObject: +24 tp_name (char*)  +32 tp_basicsize  +256 tp_base +264 tp_dict +288 tp_dictoffset
  PyStringObject: +16 size +24 hash +32 state +36 sval
     (ban game: sval bat dau +32? -> dumper cu dung +32 va OK)
  PyDictObject: +16 fill +24 used +32 mask +40 table(ptr) ; entry = hash,key,value (24B)
  PyListObject: +16 size +24 items(ptr) ; PyTupleObject: +16 size +24 items[]
  PyIntObject: +16 long ; PyFloatObject: +16 double ; PyModuleObject: +16 md_dict
#>
param(
  [string]$Mode = "findname",
  [string]$Name = "DATA_EQUIP_RANDOM_ATTR",
  [string]$Attr = "data",
  [string]$Addr = "",
  [int]$Depth = 12,
  [int]$MaxItems = 200000,
  [string]$Out = ""
)
$ErrorActionPreference = "Stop"
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
using System.IO;
using System.Globalization;

public class PO {
    [StructLayout(LayoutKind.Sequential)] public struct MBI {
        public IntPtr BaseAddress, AllocationBase; public uint AllocationProtect;
        public IntPtr RegionSize; public uint State, Protect, Type; }
    [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint a,bool i,int pid);
    [DllImport("kernel32.dll")] static extern bool ReadProcessMemory(IntPtr h,IntPtr a,byte[] b,int s,out int r);
    [DllImport("kernel32.dll")] static extern bool VirtualQueryEx(IntPtr h,IntPtr a,out MBI m,int l);
    static IntPtr H;
    public static long STR_TYPE;
    public static int StrOff = 32;
    public static void Open(int pid,long strType){ H=OpenProcess(0x0410,false,pid); STR_TYPE=strType; }
    public static byte[] RD(long a,int l){ if(a<=0x10000||l<=0) return null; byte[] b=new byte[l]; int r; return ReadProcessMemory(H,(IntPtr)a,b,l,out r)? b:null; }
    public static long Q(long a){ var b=RD(a,8); return b==null?0:BitConverter.ToInt64(b,0); }
    // Windows LLP64: C long = 32 bit -> PyIntObject.ob_ival la int32
    public static int I32(long a){ var b=RD(a,4); return b==null?0:BitConverter.ToInt32(b,0); }

    static Dictionary<long,string> tnCache=new Dictionary<long,string>();
    public static string TypeName(long t){
        if(t==0) return null;
        string s; if(tnCache.TryGetValue(t,out s)) return s;
        long p=Q(t+24); s=null;
        var b=RD(p,64);
        if(b!=null){ int n=Array.IndexOf(b,(byte)0); if(n>0){ s=Encoding.ASCII.GetString(b,0,n); foreach(char c in s) if(c<32||c>126){ s=null; break; } } }
        tnCache[t]=s; return s;
    }
    public static string Str(long a){
        var h=RD(a,24); if(h==null) return null;
        long sz=BitConverter.ToInt64(h,16); if(sz<0||sz>5000000) return null;
        if(sz==0) return "";
        var d=RD(a+StrOff,(int)sz); if(d==null) return null;
        try { return new UTF8Encoding(false,true).GetString(d); }
        catch { return Encoding.GetEncoding(28591).GetString(d); }
    }
    public static string Uni(long a){
        long sz=Q(a+16); if(sz<0||sz>5000000) return null;
        long p=Q(a+24); if(sz==0) return "";
        // thu UCS2 truoc (Windows build)
        var d=RD(p,(int)sz*2); if(d==null) return null;
        return Encoding.Unicode.GetString(d);
    }

    // ---------- tim string object co noi dung name ----------
    public static List<long> FindStrings(string name){
        var res=new List<long>(); byte[] pat=Encoding.ASCII.GetBytes(name);
        Scan((p,c,n)=>{
            for(int i=0;i+32+pat.Length<=n;i+=8){
                if(BitConverter.ToInt64(c,i+8)!=STR_TYPE) continue;
                if(BitConverter.ToInt64(c,i+16)!=pat.Length) continue;
                bool ok=true; for(int k=0;k<pat.Length;k++) if(c[i+StrOff+k]!=pat[k]){ ok=false; break; }
                if(ok) res.Add(p+i);
            }
        });
        return res;
    }
    // ---------- tim dict entry (hash,key,value) voi key thuoc set ----------
    public static List<long[]> FindEntries(HashSet<long> keys){
        var res=new List<long[]>();
        Scan((p,c,n)=>{
            for(int i=8;i+16<=n;i+=8){
                long k=BitConverter.ToInt64(c,i);
                if(!keys.Contains(k)) continue;
                long v=BitConverter.ToInt64(c,i+8);
                if(v<=0x10000) continue;
                res.Add(new long[]{p+i-8,k,v});
            }
        });
        return res;
    }
    // tim dict object (type==dictType) co table chua dia chi entry
    public static List<long> FindOwnerDicts(long dictType,long entry){
        var res=new List<long>();
        Scan((p,c,n)=>{
            for(int i=0;i+48<=n;i+=8){
                if(BitConverter.ToInt64(c,i+8)!=dictType) continue;
                long mask=BitConverter.ToInt64(c,i+32), table=BitConverter.ToInt64(c,i+40);
                if(mask<=0||mask>(1<<22)) continue;
                if(entry>=table && entry<table+(mask+1)*24) res.Add(p+i);
            }
        });
        return res;
    }
    delegate void ChunkFn(long p,byte[] c,int n);
    static void Scan(ChunkFn fn){
        long addr=0; MBI m; int sz=Marshal.SizeOf(typeof(MBI));
        while(VirtualQueryEx(H,(IntPtr)addr,out m,sz)){
            long rs=(long)m.RegionSize;
            if(m.State==0x1000 && (m.Protect==0x02||m.Protect==0x04) && rs<512L*1024*1024){
                long p=(long)m.BaseAddress,end=p+rs;
                while(p<end){
                    int n=(int)Math.Min(1<<20,end-p); var c=RD(p,n);
                    if(c!=null) fn(p,c,n);
                    p+=n;
                }
            }
            long nx=(long)m.BaseAddress+rs; if(nx<=addr) break; addr=nx;
        }
    }

    // ---------- dict helpers ----------
    public static List<long[]> DictItems(long d){
        var res=new List<long[]>();
        long mask=Q(d+32), table=Q(d+40);
        if(mask<0||mask>(1<<24)||table==0) return res;
        var b=RD(table,(int)(mask+1)*24);
        if(b==null){
            b=new byte[(mask+1)*24];
            for(long off=0;off<b.Length;off+=4096){
                int n=(int)Math.Min(4096,b.Length-off); var c=RD(table+off,n);
                if(c!=null) Buffer.BlockCopy(c,0,b,(int)off,n);
            }
        }
        for(long i=0;i<=mask;i++){
            long k=BitConverter.ToInt64(b,(int)i*24+8), v=BitConverter.ToInt64(b,(int)i*24+16);
            if(k!=0 && v!=0 && TypeName(Q(k+8))!=null && TypeName(Q(v+8))!=null) res.Add(new long[]{k,v});
        }
        return res;
    }
    public static long DictGetStr(long d,string key){
        foreach(var kv in DictItems(d)) if(TypeName(Q(kv[0]+8))=="str" && Str(kv[0])==key) return kv[1];
        return 0;
    }
    public static long InstDict(long o){
        long t=Q(o+8); string tn=TypeName(t);
        if(tn=="module") return Q(o+16);
        long off=Q(t+288);
        if(off>0 && off<4096){ long d=Q(o+off); if(d!=0 && TypeName(Q(d+8))=="dict") return d; }
        if(tn=="instance") return Q(o+24); // old-style: in_class +16, in_dict +24
        return 0;
    }

    // ---------- full code object dump (JSONL) ----------
    public static long CODE_TYPE;
    static string B64(byte[] b){ return b==null?"":Convert.ToBase64String(b); }
    static void TupleStrs(StringBuilder w,long t){
        w.Append('[');
        long n=Q(t+16); if(n<0||n>100000) n=0;
        var b=RD(t+24,(int)n*8);
        for(long i=0;b!=null&&i<n;i++){ if(i>0) w.Append(','); long s=BitConverter.ToInt64(b,(int)i*8);
            var old=sb; sb=new StringBuilder(); JStr(Str(s)??"?"); w.Append(sb.ToString()); sb=old; }
        w.Append(']');
    }
    static byte[] StrBytes(long s){ long n=Q(s+16); if(n<0||n>50000000) return null; if(n==0) return new byte[0]; return RD(s+StrOff,(int)n); }
    static void Const(StringBuilder w,long o,int depth){
        string tn=TypeName(Q(o+8));
        switch(tn){
            case "NoneType": w.Append("[\"N\"]"); return;
            case "bool": w.Append(I32(o+16)!=0?"[\"T\"]":"[\"F\"]"); return;
            case "int": w.Append("[\"i\","+I32(o+16)+"]"); return;
            case "float": { double v=BitConverter.Int64BitsToDouble(Q(o+16)); w.Append("[\"f\",\""+v.ToString("R",CultureInfo.InvariantCulture)+"\"]"); return; }
            case "complex": { double r=BitConverter.Int64BitsToDouble(Q(o+16)), im=BitConverter.Int64BitsToDouble(Q(o+24));
                w.Append("[\"j\",\""+r.ToString("R",CultureInfo.InvariantCulture)+"\",\""+im.ToString("R",CultureInfo.InvariantCulture)+"\"]"); return; }
            case "long": {
                long n=Q(o+16); int an=(int)Math.Min(Math.Abs(n),4096); var b=RD(o+24,an*4);
                System.Numerics.BigInteger acc=0;
                for(int i=an-1;b!=null&&i>=0;i--) acc=(acc<<30)+(BitConverter.ToUInt32(b,i*4)&0x3FFFFFFF);
                if(n<0) acc=-acc; w.Append("[\"l\",\""+acc.ToString()+"\"]"); return; }
            case "str": w.Append("[\"s\",\""+B64(StrBytes(o))+"\"]"); return;
            case "unicode": { long n=Q(o+16); long p=Q(o+24); var b=(n>0&&n<10000000)?RD(p,(int)n*2):new byte[0];
                w.Append("[\"u\",\""+B64(b)+"\"]"); return; }
            case "code": w.Append("[\"c\",\"0x"+o.ToString("X")+"\"]"); return;
            case "ellipsis": w.Append("[\"E\"]"); return;
            case "tuple": case "frozenset": {
                if(depth>20){ w.Append("[\"?\",\"deep\"]"); return; }
                w.Append(tn=="tuple"?"[\"t\",[":"[\"z\",[");
                if(tn=="tuple"){
                    long n=Q(o+16); var b=(n>0&&n<1000000)?RD(o+24,(int)n*8):null;
                    for(long i=0;b!=null&&i<n;i++){ if(i>0) w.Append(','); Const(w,BitConverter.ToInt64(b,(int)i*8),depth+1); }
                } else {
                    long mask=Q(o+32), table=Q(o+40); var b=(mask>0&&mask<(1<<20))?RD(table,(int)(mask+1)*16):null; bool f=true;
                    for(long i=0;b!=null&&i<=mask;i++){ long k=BitConverter.ToInt64(b,(int)i*16); if(k==0||TypeName(Q(k+8))==null) continue;
                        if(!f) w.Append(','); f=false; Const(w,k,depth+1); }
                }
                w.Append("]]"); return; }
        }
        w.Append("[\"?\",\""+(tn??"null")+"\"]");
    }
    public static long DumpCodes(TextWriter tw){
        long count=0; var seen=new HashSet<long>();
        Scan((p,c,n)=>{
            for(int i=0;i+128<=n;i+=8){
                if(BitConverter.ToInt64(c,i+8)!=CODE_TYPE) continue;
                int argc=BitConverter.ToInt32(c,i+16), nloc=BitConverter.ToInt32(c,i+20), stack=BitConverter.ToInt32(c,i+24), flags=BitConverter.ToInt32(c,i+28);
                if(argc<0||argc>255||nloc<0||nloc>65535||stack<0||stack>100000) continue;
                long co=p+i; if(!seen.Add(co)) continue;
                long pcode=BitConverter.ToInt64(c,i+32), pconsts=BitConverter.ToInt64(c,i+40), pnames=BitConverter.ToInt64(c,i+48),
                     pvar=BitConverter.ToInt64(c,i+56), pfree=BitConverter.ToInt64(c,i+64), pcell=BitConverter.ToInt64(c,i+72),
                     pfile=BitConverter.ToInt64(c,i+80), pname=BitConverter.ToInt64(c,i+88), plnotab=BitConverter.ToInt64(c,i+104);
                int fl=BitConverter.ToInt32(c,i+96);
                if(TypeName(Q(pcode+8))!="str") continue;
                var w=new StringBuilder();
                var old=sb; sb=new StringBuilder();
                sb.Append("{\"a\":\"0x"+co.ToString("X")+"\",\"name\":"); JStr(Str(pname)??"?");
                sb.Append(",\"file\":"); JStr(Str(pfile)??"?");
                w.Append(sb.ToString()); sb=old;
                w.Append(",\"fl\":"+fl+",\"argc\":"+argc+",\"nloc\":"+nloc+",\"stack\":"+stack+",\"flags\":"+flags);
                w.Append(",\"code\":\""+B64(StrBytes(pcode))+"\",\"lnotab\":\""+B64(StrBytes(plnotab))+"\"");
                w.Append(",\"names\":"); TupleStrs(w,pnames);
                w.Append(",\"varnames\":"); TupleStrs(w,pvar);
                w.Append(",\"freevars\":"); TupleStrs(w,pfree);
                w.Append(",\"cellvars\":"); TupleStrs(w,pcell);
                w.Append(",\"consts\":"); 
                if(TypeName(Q(pconsts+8))=="tuple"){ var t=new StringBuilder(); Const(t,pconsts,0); var s=t.ToString(); w.Append(s.Substring(5,s.Length-6)); } else w.Append("[]");
                w.Append('}');
                tw.WriteLine(w.ToString()); count++;
            }
        });
        return count;
    }

    // ---------- serialize ----------
    static StringBuilder sb; static int items; static HashSet<long> stack;
    public static int MaxItems=200000;
    public static string JsonStr(string s){ var old=sb; sb=new StringBuilder(); JStr(s); var r=sb.ToString(); sb=old; return r; }
    static bool CleanKey(string s){ if(s==null) return false; foreach(char c in s) if(c<32 && c!='\n' && c!='\t' && c!='\r') return false; return true; }
    static void JStr(string s){
        sb.Append('"');
        foreach(char c in s){
            if(c=='"') sb.Append("\\\""); else if(c=='\\') sb.Append("\\\\");
            else if(c<32||c>126) sb.AppendFormat("\\u{0:x4}",(int)c);
            else sb.Append(c);
        }
        sb.Append('"');
    }
    static string KeyStr(long k){
        string tn=TypeName(Q(k+8));
        if(tn=="str") return Str(k);
        if(tn=="unicode") return Uni(k);
        if(tn=="int"||tn=="bool") return I32(k+16).ToString();
        if(tn=="float") return BitConverter.Int64BitsToDouble(Q(k+16)).ToString("R",CultureInfo.InvariantCulture);
        if(tn=="tuple"){
            long n=Q(k+16); var parts=new List<string>();
            for(long i=0;i<n&&i<32;i++) parts.Add(KeyStr(Q(k+24+i*8)));
            return "("+string.Join(",",parts.ToArray())+")";
        }
        return "<"+tn+"@0x"+k.ToString("X")+">";
    }
    public static string Dump(long o,int depth){
        sb=new StringBuilder(); items=0; stack=new HashSet<long>();
        Ser(o,depth); return sb.ToString();
    }
    static void Ser(long o,int depth){
        items++;
        if(o==0){ sb.Append("null"); return; }
        long t=Q(o+8); string tn=TypeName(t);
        if(tn==null){ sb.Append("\"<bad@0x"+o.ToString("X")+">\""); return; }
        switch(tn){
            case "NoneType": sb.Append("null"); return;
            case "bool": sb.Append(I32(o+16)!=0?"true":"false"); return;
            case "int": sb.Append(I32(o+16)); return;
            case "float": {
                double v=BitConverter.Int64BitsToDouble(Q(o+16));
                if(double.IsNaN(v)||double.IsInfinity(v)) sb.Append("null"); else sb.Append(v.ToString("R",CultureInfo.InvariantCulture)); return; }
            case "long": {
                long n=Q(o+16); var b=RD(o+24,(int)Math.Min(Math.Abs(n),8)*4);
                if(b==null||n==0){ sb.Append(0); return; }
                System.Numerics.BigInteger acc=0;
                for(int i=(int)Math.Abs(n)-1;i>=0;i--){ acc=(acc<<30)+(BitConverter.ToUInt32(b,i*4)&0x3FFFFFFF); }
                if(n<0) acc=-acc; sb.Append(acc.ToString()); return; }
            case "str": { var s=Str(o); if(s==null) sb.Append("null"); else JStr(s); return; }
            case "unicode": { var s=Uni(o); if(s==null) sb.Append("null"); else JStr(s); return; }
        }
        if(depth<=0||items>MaxItems||stack.Contains(o)){ sb.Append("\"<"+tn+"@0x"+o.ToString("X")+">\""); return; }
        stack.Add(o);
        try{
        if(tn=="dict"){
            sb.Append('{'); bool first=true;
            foreach(var kv in DictItems(o)){
                string ks=KeyStr(kv[0]); if(!CleanKey(ks)) continue;
                if(!first) sb.Append(','); first=false;
                JStr(ks); sb.Append(':'); Ser(kv[1],depth-1);
            }
            sb.Append('}'); return;
        }
        if(tn=="list"||tn=="tuple"||tn=="set"||tn=="frozenset"){
            long n=Q(o+16); if(n<0||n>2000000){ sb.Append("[]"); return; }
            sb.Append('[');
            if(tn=="list"){
                long items_=Q(o+24); var b=RD(items_,(int)n*8);
                for(long i=0;b!=null&&i<n;i++){ if(i>0) sb.Append(','); Ser(BitConverter.ToInt64(b,(int)i*8),depth-1); }
            } else if(tn=="tuple"){
                var b=RD(o+24,(int)n*8);
                for(long i=0;b!=null&&i<n;i++){ if(i>0) sb.Append(','); Ser(BitConverter.ToInt64(b,(int)i*8),depth-1); }
            } else {
                // set: +16 fill +24 used +32 mask +40 table ; entry = key,hash (16B)
                long mask=Q(o+32), table=Q(o+40); var b=RD(table,(int)(mask+1)*16); bool first=true;
                for(long i=0;b!=null&&i<=mask;i++){ long k=BitConverter.ToInt64(b,(int)i*16); if(k==0) continue;
                    if(TypeName(Q(k+8))==null) continue; if(!first) sb.Append(','); first=false; Ser(k,depth-1); }
            }
            sb.Append(']'); return;
        }
        if(tn=="taggeddict.taggeddict"){
            // layout: +16 PyObject** items (key,val xen ke, con tro gan tag 3 bit thap) +24 n_items
            long arr=Q(o+16), n=Q(o+24);
            sb.Append('{');
            if(n>0 && n<200000){
                var b=RD(arr,(int)n*8);
                for(long i=0;b!=null&&i+1<n;i+=2){
                    long k=BitConverter.ToInt64(b,(int)i*8)&~7L, v=BitConverter.ToInt64(b,(int)(i+1)*8)&~7L;
                    if(i>0) sb.Append(',');
                    JStr(KeyStr(k)??"?"); sb.Append(':'); Ser(v,depth-1);
                }
            }
            sb.Append('}'); return;
        }
        long d=InstDict(o);
        sb.Append("{\"__type__\":"); JStr(tn); sb.Append(",\"__addr__\":\"0x"+o.ToString("X")+"\"");
        if(d!=0 && tn!="module"){ sb.Append(",\"__dict__\":"); Ser(d,depth-1); }
        else if(tn=="module"){ sb.Append(",\"__keys__\":["); bool f=true; foreach(var kv in DictItems(d)){ if(!f) sb.Append(','); f=false; JStr(KeyStr(kv[0])??"?"); } sb.Append(']'); }
        sb.Append('}');
        } finally { stack.Remove(o); }
    }
}
'@ -ReferencedAssemblies System.Numerics

$p = Get-Process -Name Client -EA SilentlyContinue | Select-Object -First 1
if(-not $p){ Write-Host "GAME CHUA CHAY"; exit 1 }
$base = $p.MainModule.BaseAddress.ToInt64()
[PO]::Open($p.Id, $base + 0x36B57B0)
[PO]::MaxItems = $MaxItems

function Write-Json($json){
  if($Out){ [IO.File]::WriteAllText($Out,$json,(New-Object Text.UTF8Encoding $false)); Write-Host ("Wrote {0} chars -> {1}" -f $json.Length,$Out) }
  else { Write-Host $json }
}

function Find-Values([string]$nm){
  $strs = [PO]::FindStrings($nm)
  Write-Host ("str objects '{0}': {1}" -f $nm, (($strs | % { "0x{0:X}" -f $_ }) -join ","))
  $set = New-Object 'System.Collections.Generic.HashSet[long]'
  foreach($s in $strs){ [void]$set.Add($s) }
  $ents = [PO]::FindEntries($set)
  $out = @()
  foreach($e in $ents){
    $v=$e[2]; $tn=[PO]::TypeName([PO]::Q($v+8))
    if($tn){ $out += ,@($e[0],$v,$tn) }
  }
  return ,$out
}

switch($Mode){
  "codes" {
    [PO]::CODE_TYPE = $base + 0x36B7540
    $w = New-Object System.IO.StreamWriter($Out,$false,(New-Object Text.UTF8Encoding $false))
    $t0=Get-Date; $n=[PO]::DumpCodes($w); $w.Close()
    Write-Host ("code objects={0} in {1:N0}s -> {2}" -f $n,((Get-Date)-$t0).TotalSeconds,$Out)
  }
  "bindicts" {
    # -Addr = dia chi sys.modules ; -Out = thu muc. Ghi <module>.<attr>.bin cho moi str bindict
    # (attr ten *content* hoac str > 64 byte bat dau bang header bindict) + <module>.py.json (phan con lai)
    $sm=[Convert]::ToInt64($Addr.Replace("0x",""),16)
    [IO.Directory]::CreateDirectory($Out) | Out-Null
    $nb=0; $nm=0
    foreach($kv in [PO]::DictItems($sm)){
      $mn=[PO]::Str($kv[0]); if(-not $mn -or $mn -notmatch '^com\.data\.'){ continue }
      if([PO]::TypeName([PO]::Q($kv[1]+8)) -ne "module"){ continue }
      $md=[PO]::InstDict($kv[1]); $nm++
      $rest=New-Object System.Text.StringBuilder; [void]$rest.Append("{"); $first=$true
      foreach($a in [PO]::DictItems($md)){
        $an=[PO]::Str($a[0]); $tn=[PO]::TypeName([PO]::Q($a[1]+8))
        if(-not $an -or $an -match '[\x00-\x1f]'){ continue }
        if($an -like "__*" -or $tn -eq "module" -or $tn -eq "type" -or $tn -eq "function" -or $tn -eq "builtin_function_or_method" -or $tn -eq "classobj"){ continue }
        if($tn -eq "str"){
          $n=[PO]::Q($a[1]+16)
          if($n -ge 16 -and ($an -match 'content|bin|buf' -or $n -ge 4096)){
            $b=[PO]::RD($a[1]+32,[int]$n)
            $isBd=$false
            if($b){
              $sc=[BitConverter]::ToUInt32($b,0); $pad=[BitConverter]::ToUInt32($b,4)
              if($pad -eq 0 -and $sc -lt 1000000 -and (8+4*$sc) -le $n){
                $isBd=$true; $prev=0
                for($q=0;$q -lt [Math]::Min($sc,64);$q++){ $L=[BitConverter]::ToUInt32($b,8+4*$q); if($L -lt $prev -or $L -gt $n){ $isBd=$false; break }; $prev=$L }
              }
            }
            if($isBd){ [IO.File]::WriteAllBytes((Join-Path $Out ("{0}.{1}.bin" -f $mn,$an)),$b); $nb++; continue }
          }
        }
        if($tn -eq "BindictProxy"){ continue }
        if($tn -like "bindict*"){
          # bindict.bindict native: +24 = PyDict cache cac entry da giai ma
          $cache=[PO]::Q($a[1]+24)
          if($cache -and [PO]::TypeName([PO]::Q($cache+8)) -eq "dict"){
            $j=[PO]::Dump($cache,10)
            [IO.File]::WriteAllText((Join-Path $Out ("{0}.{1}.cache.json" -f $mn,$an)),$j,(New-Object Text.UTF8Encoding $false))
          }
          continue
        }
        $j=[PO]::Dump($a[1],8)
        if(-not $first){ [void]$rest.Append(",") }; $first=$false
        [void]$rest.Append([PO]::JsonStr($an)+':'+$j)
      }
      [void]$rest.Append("}")
      [IO.File]::WriteAllText((Join-Path $Out ("{0}.py.json" -f $mn)),$rest.ToString(),(New-Object Text.UTF8Encoding $false))
    }
    Write-Host ("modules={0} bindict blobs={1}" -f $nm,$nb)
  }
  "sysmodules" {
    # Tim sys.modules: tim entry key = $Name (ten module day du) -> dict chua entry co >500 module
    $vals = Find-Values $Name
    foreach($x in $vals){
      if($x[2] -ne "module"){ continue }
      $md=[PO]::InstDict($x[1]); $dictType=[PO]::Q($md+8)
      $owners=[PO]::FindOwnerDicts($dictType,$x[0])
      foreach($o in $owners){
        $items=[PO]::DictItems($o)
        Write-Host ("  owner 0x{0:X} items={1} (entry 0x{2:X})" -f $o,$items.Count,$x[0])
        if($items.Count -lt 500){ continue }
        $lines = foreach($kv in $items){ if([PO]::TypeName([PO]::Q($kv[1]+8)) -eq "module"){ "{0}`t0x{1:X}" -f [PO]::Str($kv[0]),$kv[1] } }
        Write-Host ("sys.modules = 0x{0:X} ({1} modules)" -f $o,$lines.Count)
        if($Out){ [IO.File]::WriteAllLines($Out,[string[]]$lines) }
        return
      }
    }
  }
  "hex" {
    # -Addr 0x..[,+off,+off] : theo chuoi con tro roi in 64 byte
    $parts=$Addr.Split(",")
    $a=[Convert]::ToInt64($parts[0].Replace("0x",""),16)
    for($i=1;$i -lt $parts.Length;$i++){ $a=[PO]::Q($a+[int]$parts[$i]) }
    $b=[PO]::RD($a,64)
    Write-Host ("0x{0:X} type={1}" -f $a,[PO]::TypeName([PO]::Q($a+8)))
    if($b){ for($j=0;$j -lt 64;$j+=8){ Write-Host ("  +{0,2}: {1:X16}" -f $j,[BitConverter]::ToInt64($b,$j)) } }
  }
  "findname" {
    $vals = Find-Values $Name
    foreach($x in $vals){ Write-Host ("entry@0x{0:X} -> 0x{1:X} ({2})" -f $x[0],$x[1],$x[2]) }
  }
  "dump" {
    $a=[Convert]::ToInt64($Addr.Replace("0x",""),16)
    Write-Json ([PO]::Dump($a,$Depth))
  }
  "modattr" {
    $vals = Find-Values $Name
    $seen=@{}
    foreach($x in $vals){
      $v=$x[1]; if($seen.ContainsKey($v)){ continue }; $seen[$v]=1
      Write-Host ("candidate 0x{0:X} ({1})" -f $v,$x[2])
      if($x[2] -eq "dict" -or $x[2] -eq "list"){ Write-Json ([PO]::Dump($v,$Depth)); return }
      $d=[PO]::InstDict($v)
      if($d -eq 0){ continue }
      if(-not $Attr){ Write-Json ([PO]::Dump($d,$Depth)); return }
      $a=[PO]::DictGetStr($d,$Attr)
      if($a -ne 0){ Write-Host ("  {0} -> 0x{1:X} ({2})" -f $Attr,$a,[PO]::TypeName([PO]::Q($a+8))); Write-Json ([PO]::Dump($a,$Depth)); return }
      else { Write-Host ("  keys: " + (([PO]::DictItems($d) | % { [PO]::Str($_[0]) }) -join ",")) }
    }
  }
}

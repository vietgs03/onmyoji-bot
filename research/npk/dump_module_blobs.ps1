<#
dump_module_blobs.ps1 - Ghi moi str attr lon (bindict blob) cua 1 module trong sys.modules ra file (chi DOC).
  -Module com.data.cdata_en.currency  -OutDir \\wsl.localhost\...\data\cdata_raw
Ghi them: native bindict.bindict -> doc blob qua cac offset (+16..+48) neu attr khong phai str.
#>
param([string]$Module = "com.data.cdata_en.currency", [string]$OutDir = "")
$ErrorActionPreference = "Stop"
$wM=$Module; $wO=$OutDir
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
$Module=$wM; $OutDir=$wO
function A($d,$k){ [PO]::DictGetStr($d,$k) }
$strs=[PO]::FindStrings("__builtin__")
$set=New-Object 'System.Collections.Generic.HashSet[long]'; foreach($s in $strs){[void]$set.Add($s)}
$sm=0
foreach($e in [PO]::FindEntries($set)){
  if([PO]::TypeName([PO]::Q($e[2]+8)) -ne "module"){ continue }
  $dt=[PO]::Q([PO]::InstDict($e[2])+8)
  foreach($o in [PO]::FindOwnerDicts($dt,$e[0])){ if(([PO]::DictItems($o)).Count -gt 200 -and (A $o "Globals")){ $sm=$o; break } }
  if($sm){ break }
}
if(-not $sm){ throw "sys.modules not found" }
$m=A $sm $Module
if(-not $m){ throw "module $Module chua load" }
$md=[PO]::InstDict($m)
foreach($kv in [PO]::DictItems($md)){
  $an=[PO]::Str($kv[0]); $t=[PO]::TypeName([PO]::Q($kv[1]+8))
  Write-Host ("  {0} : {1}" -f $an,$t)
  if($t -eq "str"){
    $n=[PO]::Q($kv[1]+16)
    if($n -ge 64){ $b=[PO]::RD($kv[1]+32,[int]$n); $f=Join-Path $OutDir ("{0}.{1}.bin" -f $Module,$an); [IO.File]::WriteAllBytes($f,$b); Write-Host ("    -> {0} bytes {1}" -f $n,$f) }
  }
  elseif($t -eq "BindictProxy"){
    $bd=A ([PO]::InstDict($kv[1])) "bindict_data"
    if($bd){
      Write-Host "    native bindict.bindict, hex +0..+64:"
      $h=[PO]::RD($bd,64); for($j=0;$j -lt 64;$j+=8){ $q=[BitConverter]::ToInt64($h,$j); Write-Host ("     +{0,2}: {1:X16} {2}" -f $j,$q,([PO]::TypeName([PO]::Q($q+8)))) }
      foreach($off in 16,24,32,40,48){
        $p=[PO]::Q($bd+$off)
        if([PO]::TypeName([PO]::Q($p+8)) -eq "str"){
          $n=[PO]::Q($p+16); $b=[PO]::RD($p+32,[int]$n)
          $f=Join-Path $OutDir ("{0}.{1}.native{2}.bin" -f $Module,$an,$off); [IO.File]::WriteAllBytes($f,$b); Write-Host ("    -> str@+{0} {1} bytes {2}" -f $off,$n,$f)
        }
      }
    }
  }
}

<#
read_day_limit.ps1 - Doc gioi han ngay ban PC (chi DOC):
  player1.PClimit           (tien do hien tai, server gui qua day_limit_update / bdict['day_limit_pc'])
  DATA_DAY_LIMIT.data[id]   (name, limit_pc)  - cache bindict neu da giai ma
#>
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
function A($d,$k){ [PO]::DictGetStr($d,$k) }
$strs=[PO]::FindStrings("__builtin__"); $set=New-Object 'System.Collections.Generic.HashSet[long]'; foreach($s in $strs){[void]$set.Add($s)}
$sm=0; foreach($e in [PO]::FindEntries($set)){ if([PO]::TypeName([PO]::Q($e[2]+8)) -ne "module"){continue}; $dt=[PO]::Q([PO]::InstDict($e[2])+8); foreach($o in [PO]::FindOwnerDicts($dt,$e[0])){ if(([PO]::DictItems($o)).Count -gt 200 -and (A $o "Globals")){$sm=$o;break} }; if($sm){break} }
if(-not $sm){ throw "sys.modules not found" }
$G=[PO]::InstDict((A $sm "Globals"))
$pd=[PO]::InstDict((A $G "player1"))
$pc=A $pd "PClimit"
Write-Host ("PClimit = " + $(if($pc){[PO]::Dump($pc,3)}else{"(none)"}))
$dcd=[PO]::InstDict((A $sm "DynamicConfigData"))
foreach($n in "DATA_DAY_LIMIT"){
  $w=A $dcd $n; if(-not $w){ Write-Host "$n (none)"; continue }
  $m=A ([PO]::InstDict($w)) "_dataModule"
  if(-not $m){ Write-Host "$n chua load"; continue }
  $md=[PO]::InstDict($m)
  Write-Host ("$n module = " + [PO]::Str((A $md "__name__")))
  $bd=A $md "bin_data"
  if($bd){
    $c=[PO]::Q($bd+24)
    if($c -and [PO]::TypeName([PO]::Q($c+8)) -eq "dict"){ Write-Host ("$n cache = " + [PO]::Dump($c,3)) }
    $inner=[PO]::Q($bd+16)
    if($inner){ $p=[PO]::Q($inner); if([PO]::TypeName([PO]::Q($p+8)) -eq "str"){ $n2=[PO]::Q($p+16); $b=[PO]::RD($p+32,[int]$n2); [IO.File]::WriteAllBytes((Join-Path $PSScriptRoot "data\day_limit_blob.bin"),$b); Write-Host "blob $n2 bytes -> data\day_limit_blob.bin" } }
  }
}

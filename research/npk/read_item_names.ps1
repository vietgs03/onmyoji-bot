<#
read_item_names.ps1 - Doc ten vat pham tu RAM game: DynamicConfigData.DATA_CURRENCY.data[id]['name'] (chi DOC).
  -Ids "300002,300079,900180"
#>
param([string]$Ids = "300002")
$ErrorActionPreference = "Stop"
$wIds = $Ids
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
$Ids = $wIds
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
$dcd=[PO]::InstDict((A $sm "DynamicConfigData"))
$tbl=A $dcd "DATA_CURRENCY"
$tn=[PO]::TypeName([PO]::Q($tbl+8))
Write-Host ("DATA_CURRENCY type={0}" -f $tn)
# DynamicConfigData wrapper -> _dataModule (module com.data.cdata[_en].currency) -> .data
if($tn -eq "DynamicConfigData"){
  $md=A ([PO]::InstDict($tbl)) "_dataModule"
  if(-not $md -or [PO]::TypeName([PO]::Q($md+8)) -ne "module"){ throw "_dataModule chua load (game chua dung DATA_CURRENCY?)" }
  $mdd=[PO]::InstDict($md)
  $tbl=A $mdd "data"; if(-not $tbl){ $tbl=A $mdd "bin_data_content" }
  $tn=[PO]::TypeName([PO]::Q($tbl+8))
  Write-Host ("  _dataModule.data type={0}" -f $tn)
}
# BindictProxy -> bindict_data (native bindict) -> +24 cache dict (chi entry da giai ma)
$data=0
if($tn -eq "dict"){ $data=$tbl }
elseif($tn -eq "BindictProxy"){
  $pd=[PO]::InstDict($tbl)
  if($pd){
    Write-Host ("  BindictProxy keys: " + (([PO]::DictItems($pd) | % { "{0}({1})" -f [PO]::Str($_[0]),[PO]::TypeName([PO]::Q($_[1]+8)) }) -join ","))
    foreach($kv in [PO]::DictItems($pd)){
      $vt=[PO]::TypeName([PO]::Q($kv[1]+8))
      if($vt -like "bindict*"){ $c=[PO]::Q($kv[1]+24); if($c -and [PO]::TypeName([PO]::Q($c+8)) -eq "dict"){ $data=$c; break } }
      if($vt -eq "dict" -and ([PO]::DictItems($kv[1])).Count -gt 50){ $data=$kv[1]; break }
    }
  } else {
    Write-Host "  BindictProxy khong co __dict__, thu offset native"
    foreach($off in 16,24,32,40){ $p=[PO]::Q($tbl+$off); $pt=[PO]::TypeName([PO]::Q($p+8)); Write-Host ("   +{0} -> {1}" -f $off,$pt)
      if($pt -like "bindict*"){ $c=[PO]::Q($p+24); if([PO]::TypeName([PO]::Q($c+8)) -eq "dict"){ $data=$c; break } }
      if($pt -eq "dict"){ $data=$p; break } }
  }
}
elseif($tn -like "bindict*"){ $data=[PO]::Q($tbl+24) }
elseif($tn -eq "module"){ $data=A ([PO]::InstDict($tbl)) "data" }
if(-not $data){ throw "khong lay duoc DATA_CURRENCY.data" }
$want=@{}; foreach($x in $Ids.Split(",")){ $want[[int]$x.Trim()]=1 }
$found=0
foreach($kv in [PO]::DictItems($data)){
  if([PO]::TypeName([PO]::Q($kv[0]+8)) -ne "int"){ continue }
  $id=[PO]::I32($kv[0]+16)
  if(-not $want.ContainsKey($id)){ continue }
  $row=$kv[1]; $rt=[PO]::TypeName([PO]::Q($row+8))
  $nm=$null
  if($rt -eq "dict"){ $n=A $row "name"; if($n){ $nm=([PO]::Dump($n,1)) } }
  else { $nm=[PO]::Dump($row,3) }
  Write-Host ("ID {0}`t{1}" -f $id,$nm); $found++
}
Write-Host ("found {0}/{1} (cache chi chua entry game da dung)" -f $found,$want.Count)

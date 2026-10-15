<#
find_bonus_event.ps1 - Tim su kien khop dong ho banner "8 days"/"46 days" (chi DOC RAM).
Quet active_time_list + recordparam tim end-time gan now+8d (~1792738844) va now+46d (~1796022044).
#>
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
function A($d,$k){ [PO]::DictGetStr($d,$k) }
$strs=[PO]::FindStrings("__builtin__"); $set=New-Object 'System.Collections.Generic.HashSet[long]'; foreach($s in $strs){[void]$set.Add($s)}
$sm=0; foreach($e in [PO]::FindEntries($set)){ if([PO]::TypeName([PO]::Q($e[2]+8)) -ne "module"){continue}; $dt=[PO]::Q([PO]::InstDict($e[2])+8); foreach($o in [PO]::FindOwnerDicts($dt,$e[0])){ if(([PO]::DictItems($o)).Count -gt 200 -and (A $o "Globals")){$sm=$o;break} }; if($sm){break} }
if(-not $sm){ throw "sys.modules not found" }
$G=[PO]::InstDict((A $sm "Globals")); $pd=[PO]::InstDict((A $G "player1"))
$now=[int](([DateTimeOffset](Get-Date)).ToUnixTimeSeconds())
$t8=$now+8*86400; $t46=$now+46*86400; $tol=2*86400
Write-Host ("now=$now  t8~$t8  t46~$t46")

# 1) active_time_list: in entry co end-time khop
Write-Host "=== active_time_list khop dong ho ==="
$atl=A $pd "active_time_list"
foreach($kv in [PO]::DictItems($atl)){
  $v=$kv[1]
  if([PO]::TypeName([PO]::Q($v+8)) -ne "list"){ continue }
  $n=[PO]::Q($v+16); if($n -lt 1){ continue }
  $items=[PO]::Q($v+24)
  for($i=0;$i -lt $n;$i++){
    $pair=[PO]::Q($items+$i*8)
    if([PO]::TypeName([PO]::Q($pair+8)) -ne "list" -or [PO]::Q($pair+16) -lt 2){ continue }
    $arr=[PO]::Q($pair+24); $e=[PO]::Q($arr+8)
    $eend=[PO]::I32($e+16)
    if( ($eend -ge ($t8-$tol) -and $eend -le ($t8+$tol)) -or ($eend -ge ($t46-$tol) -and $eend -le ($t46+$tol)) ){
      $keyhex=("0x{0:X}" -f $kv[0]); $kt=[PO]::TypeName([PO]::Q($kv[0]+8))
      $kstr=if($kt -eq "str"){[PO]::Str($kv[0])}elseif($kt -eq "int"){[PO]::I32($kv[0]+16)}else{$keyhex}
      Write-Host ("  key=$kstr ($kt)  window=" + [PO]::Dump($pair,1) + "  end=$eend")
    }
  }
}

# 2) recordparam: value la dict co 'cd'/'end'/'et' khop, hoac int khop
Write-Host "=== recordparam khop dong ho ==="
$rp=A $pd "recordparam"
foreach($kv in [PO]::DictItems($rp)){
  $k=[PO]::Str($kv[0]); $v=$kv[1]; $tn=[PO]::TypeName([PO]::Q($v+8))
  if($tn -eq "dict"){
    foreach($f in "cd","end","et","endtime","end_time","expire"){
      $fv=A $v $f
      if($fv -and [PO]::TypeName([PO]::Q($fv+8)) -eq "int"){ $iv=[PO]::I32($fv+16)
        if( ($iv -ge ($t8-$tol) -and $iv -le ($t8+$tol)) -or ($iv -ge ($t46-$tol) -and $iv -le ($t46+$tol)) ){
          Write-Host ("  recordparam['$k'].$f=$iv -> " + [PO]::Dump($v,3)) }
      }
    }
  }
}

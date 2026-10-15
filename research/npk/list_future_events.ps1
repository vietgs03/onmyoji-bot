<# list_future_events.ps1 - Liet ke moi window tuong lai trong active_time_list (chi DOC). #>
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
function A($d,$k){ [PO]::DictGetStr($d,$k) }
$strs=[PO]::FindStrings("__builtin__"); $set=New-Object 'System.Collections.Generic.HashSet[long]'; foreach($s in $strs){[void]$set.Add($s)}
$sm=0; foreach($e in [PO]::FindEntries($set)){ if([PO]::TypeName([PO]::Q($e[2]+8)) -ne "module"){continue}; $dt=[PO]::Q([PO]::InstDict($e[2])+8); foreach($o in [PO]::FindOwnerDicts($dt,$e[0])){ if(([PO]::DictItems($o)).Count -gt 200 -and (A $o "Globals")){$sm=$o;break} }; if($sm){break} }
$G=[PO]::InstDict((A $sm "Globals")); $pd=[PO]::InstDict((A $G "player1"))
$now=[int](([DateTimeOffset](Get-Date)).ToUnixTimeSeconds())
$atl=A $pd "active_time_list"
Write-Host ("now=$now ; active_time_list = {0} entries" -f ([PO]::DictItems($atl)).Count)
$rows=@()
foreach($kv in [PO]::DictItems($atl)){
  $kt=[PO]::TypeName([PO]::Q($kv[0]+8))
  $kstr=if($kt -eq "str"){[PO]::Str($kv[0])}elseif($kt -eq "int"){""+[PO]::I32($kv[0]+16)}else{"0x{0:X}" -f $kv[0]}
  $v=$kv[1]; if([PO]::TypeName([PO]::Q($v+8)) -ne "list"){ continue }
  $n=[PO]::Q($v+16); if($n -lt 1){ continue }; $items=[PO]::Q($v+24)
  $maxend=0
  for($i=0;$i -lt $n;$i++){
    $pair=[PO]::Q($items+$i*8)
    if([PO]::TypeName([PO]::Q($pair+8)) -ne "list" -or [PO]::Q($pair+16) -lt 2){ continue }
    $arr=[PO]::Q($pair+24); $eend=[PO]::I32([PO]::Q($arr+8)+16)
    if($eend -gt $maxend){ $maxend=$eend }
  }
  if($maxend -gt $now){ $days=[math]::Round(($maxend-$now)/86400.0,1); $rows += ,@($kstr,$maxend,$days) }
}
$rows = $rows | Sort-Object { $_[1] }
foreach($r in $rows){ Write-Host ("  {0,-28} end={1}  (+{2}d)" -f $r[0],$r[1],$r[2]) }

<#
read_soul_buff2.ps1 - Liet ke active_time_list + tim WEEKEND_EQUIP that su (chi DOC).
#>
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
function A($d,$k){ [PO]::DictGetStr($d,$k) }
$strs=[PO]::FindStrings("__builtin__"); $set=New-Object 'System.Collections.Generic.HashSet[long]'; foreach($s in $strs){[void]$set.Add($s)}
$sm=0; foreach($e in [PO]::FindEntries($set)){ if([PO]::TypeName([PO]::Q($e[2]+8)) -ne "module"){continue}; $dt=[PO]::Q([PO]::InstDict($e[2])+8); foreach($o in [PO]::FindOwnerDicts($dt,$e[0])){ if(([PO]::DictItems($o)).Count -gt 200 -and (A $o "Globals")){$sm=$o;break} }; if($sm){break} }
if(-not $sm){ throw "sys.modules not found" }
$G=[PO]::InstDict((A $sm "Globals"))
$pd=[PO]::InstDict((A $G "player1"))
$now=[int][double]::Parse(((Get-Date)-(Get-Date "1970-01-01")).TotalSeconds)

Write-Host "=== TAT CA active_time_list (ten | start | end | con mo?) ==="
$atl=A $pd "active_time_list"
foreach($kv in [PO]::DictItems($atl)){
  $name=[PO]::Str($kv[0]); $v=$kv[1]
  $s="?"; $e="?"
  if([PO]::TypeName([PO]::Q($v+8)) -eq "list" -and [PO]::Q($v+16) -ge 1){
    $it=[PO]::Q($v+24); $first=[PO]::Q($it)
    if([PO]::TypeName([PO]::Q($first+8)) -eq "list" -and [PO]::Q($first+16) -ge 2){
      $arr=[PO]::Q($first+24); $s=[PO]::Dump([PO]::Q($arr),1); $e=[PO]::Dump([PO]::Q($arr+8),1)
    }
  }
  Write-Host ("  {0}`t{1}`t{2}" -f $name,$s,$e)
}

Write-Host "=== Tim key WEEKEND_EQUIP: xem ParamNameDef ==="
$pdef=A $sm "com.param_def"
if($pdef){ $pdd=[PO]::InstDict((A ([PO]::InstDict($pdef)) "ParamNameDef")); if($pdd){ $w=A $pdd "WEEKEND_EQUIP"; Write-Host ("  WEEKEND_EQUIP const = " + $(if($w){[PO]::Dump($w,1)}else{'?'})) } }

Write-Host "=== Cac dict param tren player (tim equips/cnt/vip_day_cnt) ==="
foreach($kv in [PO]::DictItems($pd)){
  $name=[PO]::Str($kv[0]); $v=$kv[1]
  if([PO]::TypeName([PO]::Q($v+8)) -ne "dict"){ continue }
  $hasEquips = (A $v "equips") -ne 0 -or (A $v "vip_day_cnt") -ne 0 -or (A $v "pre_equips") -ne 0
  if($hasEquips){ Write-Host ("  player.{0} = {1}" -f $name,[PO]::Dump($v,4)) }
}

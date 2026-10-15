<#
read_soul_buff.ps1 - DOC trang thai su kien / buff drop ngu hon tu RAM (chi DOC).
  player1.active_time_list            -> cac su kien dang mo (ten + [start,end])
  player1.entity_params / WEEKEND_EQUIP -> lua chon ngu hon (equips, cnt, vip_day_cnt)
  tim them key param co 'rune/yuhun/soul/weekend/bonus/double'
#>
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
function A($d,$k){ [PO]::DictGetStr($d,$k) }
$strs=[PO]::FindStrings("__builtin__"); $set=New-Object 'System.Collections.Generic.HashSet[long]'; foreach($s in $strs){[void]$set.Add($s)}
$sm=0; foreach($e in [PO]::FindEntries($set)){ if([PO]::TypeName([PO]::Q($e[2]+8)) -ne "module"){continue}; $dt=[PO]::Q([PO]::InstDict($e[2])+8); foreach($o in [PO]::FindOwnerDicts($dt,$e[0])){ if(([PO]::DictItems($o)).Count -gt 200 -and (A $o "Globals")){$sm=$o;break} }; if($sm){break} }
if(-not $sm){ throw "sys.modules not found" }
$G=[PO]::InstDict((A $sm "Globals"))
$pd=[PO]::InstDict((A $G "player1"))

# 1) active_time_list: loc ten lien quan rune/soul
$atl=A $pd "active_time_list"
Write-Host "=== active_time_list (su kien dang mo) ==="
if($atl -and [PO]::TypeName([PO]::Q($atl+8)) -eq "dict"){
  foreach($kv in [PO]::DictItems($atl)){
    $name=[PO]::Str($kv[0])
    if($name -match 'rune|yuhun|soul|weekend|bonus|double|evo|god|zhufu|orochi'){
      Write-Host ("  {0} = {1}" -f $name,[PO]::Dump($kv[1],3))
    }
  }
  Write-Host ("  [tong so su kien dang mo: {0}]" -f ([PO]::DictItems($atl)).Count)
} else { Write-Host "  (khong co active_time_list)" }

# 2) WEEKEND_EQUIP + cac param rune: quet entity param dict
Write-Host "=== entity params lien quan (rune/yuhun/weekend/soul) ==="
foreach($pname in "entity_params","_entity_params","params","entityParams"){
  $pp=A $pd $pname
  if($pp -and [PO]::TypeName([PO]::Q($pp+8)) -eq "dict"){
    Write-Host ("  [tu {0}]" -f $pname)
    foreach($kv in [PO]::DictItems($pp)){
      $name=[PO]::Str($kv[0])
      if($name -match 'weekend|rune|yuhun|soul|bonus|double|drop'){
        Write-Host ("    {0} = {1}" -f $name,[PO]::Dump($kv[1],4))
      }
    }
  }
}
# truc tiep tren player (vai param gan thang vao __dict__)
foreach($k in "WEEKEND_EQUIP","weekend_equip","dungeon_rune_floor","PClimit"){
  $v=A $pd $k
  if($v){ Write-Host ("  player.{0} = {1}" -f $k,[PO]::Dump($v,4)) }
}

<#
read_versions.ps1 - Doc player1.heroes_version / inventory_version / _last_process tu RAM (chi DOC).
Game dung 3 so nay lam loginInfo['versions'] khi reconnect.
#>
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
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
$G=[PO]::InstDict((A $sm "Globals"))
$pd=[PO]::InstDict((A $G "player1"))
$ver=@{}
foreach($k in "heroes_version","inventory_version","_last_process"){
  $v=A $pd $k
  $ver[$k]= if($v){ [PO]::Dump($v,1) } else { "0" }
}
$sid=([PO]::Dump((A $pd "login_session"),2) | ConvertFrom-Json).sid
Write-Host ("VERSIONS={0}#{1}#{2}" -f $ver.heroes_version,$ver.inventory_version,$ver._last_process)
Write-Host ("SID={0}" -f $sid)

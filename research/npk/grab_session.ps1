<#
grab_session.ps1 - Lay thong tin phien hien tai tu RAM game -> research/npk/data/session.json + authmsg.bson

sys.modules['Globals'] -> player1 (ClientAvatar) -> server.stub.rpc_channel.rpc_service (GateClient)
authmsg: GateClient.reconnect_data.bin_authmsg (chi co sau khi game tu reconnect it nhat 1 lan).
#>
$ErrorActionPreference = "Stop"
. '\\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\research\npk\pyobj_dump.ps1' -Mode none
$OUT = '\\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\research\npk\data'
function A($d,$k){ [PO]::DictGetStr($d,$k) }

$strs=[PO]::FindStrings("com.data.cdata_en.equip_attr")
$set=New-Object 'System.Collections.Generic.HashSet[long]'; foreach($s in $strs){[void]$set.Add($s)}
$sm=0
foreach($e in [PO]::FindEntries($set)){
  if([PO]::TypeName([PO]::Q($e[2]+8)) -ne "module"){ continue }
  $dt=[PO]::Q([PO]::InstDict($e[2])+8)
  foreach($o in [PO]::FindOwnerDicts($dt,$e[0])){ if(([PO]::DictItems($o)).Count -gt 500){ $sm=$o; break } }
  if($sm){ break }
}
if(-not $sm){ throw "sys.modules not found" }
Write-Host ("sys.modules=0x{0:X}" -f $sm)
$G=[PO]::InstDict((A $sm "Globals"))
$gate=[PO]::Dump((A $G "currentGateAddr"),2) | ConvertFrom-Json
$pub=[PO]::Str((A $G "loginpubkey"))
$p1=A $G "player1"
if(-not $p1 -or [PO]::TypeName([PO]::Q($p1+8)) -ne "ClientAvatar"){ throw "player1 chua san sang (chua vao sanh)" }
$pd=[PO]::InstDict($p1)
$oidp=[PO]::Q((A $pd "id")+16); $oid=[PO]::RD($oidp+32,12)
$sid=([PO]::Dump((A $pd "login_session"),2) | ConvertFrom-Json).sid
$srv=[PO]::InstDict((A $pd "server")); $stub=[PO]::InstDict((A $srv "stub")); $ch=[PO]::InstDict((A $stub "rpc_channel"))
$gc=[PO]::InstDict((A $ch "rpc_service"))
$fulluid=[PO]::Str((A $gc "fulluid"))
$rd=A $gc "reconnect_data"
$auth=$null
if($rd -and [PO]::TypeName([PO]::Q($rd+8)) -eq "dict"){
  $b=A $rd "bin_authmsg"; if($b){ $n=[PO]::Q($b+16); $auth=[PO]::RD($b+32,[int]$n) }
}
Write-Host ("gate={0}:{1} entity={2} sid={3} fulluid={4} authmsg={5}" -f $gate[0],$gate[1],(($oid|%{$_.ToString('x2')}) -join ''),$sid,$fulluid,$(if($auth){$auth.Length}else{'none'}))
if($auth){ [IO.File]::WriteAllBytes("$OUT\authmsg.bson",$auth) }
$sess=[ordered]@{ gate_ip=$gate[0]; gate_port=[int]$gate[1]; deviceid=$fulluid; entityid=(($oid|%{$_.ToString('x2')}) -join ''); sid=$sid; authmsg_file="authmsg.bson"; pubkey=($pub -split ' ')[0..1] -join ' '; has_fresh_authmsg=[bool]$auth }
[IO.File]::WriteAllText("$OUT\session.json",($sess | ConvertTo-Json),(New-Object Text.UTF8Encoding $false))

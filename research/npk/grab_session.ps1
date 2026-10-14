<#
grab_session.ps1 - Lay thong tin phien hien tai tu RAM game -> research/npk/data/session.json + authmsg.bson

sys.modules['Globals'] -> player1 (ClientAvatar) -> server.stub.rpc_channel.rpc_service (GateClient)
authmsg: GateClient.reconnect_data.bin_authmsg (chi co sau khi game tu reconnect it nhat 1 lan).
#>
param([string]$DataDir = '\\wsl.localhost\Ubuntu\home\viethx\onmyoji-bot\research\npk\data')
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
function A($d,$k){ [PO]::DictGetStr($d,$k) }

# anchor "__builtin__" luon co trong sys.modules (com.data.* load luoi, co the chua co)
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
if($auth){ [IO.File]::WriteAllBytes("$DataDir\authmsg.bson",$auth) }
$sess=[ordered]@{ gate_ip=$gate[0]; gate_port=[int]$gate[1]; deviceid=$fulluid; entityid=(($oid|%{$_.ToString('x2')}) -join ''); sid=$sid; authmsg_file="authmsg.bson"; pubkey=($pub -split ' ')[0..1] -join ' '; has_fresh_authmsg=[bool]$auth }
[IO.File]::WriteAllText("$DataDir\session.json",($sess | ConvertTo-Json),(New-Object Text.UTF8Encoding $false))

# --- player_state.json: trang thai daily (chi doc, cho daily_claim.py dry-run) ---
$ps=[ordered]@{}
$cur=A $pd "currency"
$ps.day_active_score=0
if($cur){
  # CurrencyDict la subclass cua dict -> Dump khong doc duoc, doc thang bang DictItems (key int)
  foreach($kv in [PO]::DictItems($cur)){
    if([PO]::TypeName([PO]::Q($kv[0]+8)) -ne "int"){ continue }
    if([PO]::I32($kv[0]+16) -eq 900005){ $ps.day_active_score=[PO]::I32($kv[1]+16) }
  }
}
$dtr=A $pd "daily_task_reward"; $ps.daily_task_reward=@(); if($dtr){ $ps.daily_task_reward=@([PO]::Dump($dtr,2) | ConvertFrom-Json) }
$dt=A $pd "daily_task"; if($dt){ $ps.daily_task=([PO]::Dump($dt,3) | ConvertFrom-Json) }
$dte=A $pd "daily_task_event"; if($dte){ $ps.daily_task_event=([PO]::Dump($dte,3) | ConvertFrom-Json) }
[IO.File]::WriteAllText("$DataDir\player_state.json",($ps | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding $false))
Write-Host ("player_state: day_active_score={0} claimed={1}" -f $ps.day_active_score,(@($ps.daily_task_reward).Count))

# --- Bang nguong diem moc daily (DATA_DAILY_TASK_REWARD) tu RAM runtime ---
# tim DynamicConfigData -> .DATA_DAILY_TASK_REWARD -> BindictProxy -> bindict cache
$dcd=A $sm "DynamicConfigData"
if($dcd){
  $dcdd=[PO]::InstDict($dcd); $tbl=$null
  if($dcdd){ $tbl=A $dcdd "DATA_DAILY_TASK_REWARD" }
  if($tbl){
    $tn=[PO]::TypeName([PO]::Q($tbl+8))
    $data=$null
    if($tn -eq "BindictProxy"){ $bd=[PO]::DictGetStr([PO]::InstDict($tbl),"bindict_data"); if($bd){ $data=[PO]::Q($bd+24) } }
    elseif($tn -like "bindict*"){ $data=[PO]::Q($tbl+24) }
    if($data -and [PO]::TypeName([PO]::Q($data+8)) -eq "dict"){
      [IO.File]::WriteAllText("$DataDir\daily_task_reward_full.json",[PO]::Dump($data,4),(New-Object Text.UTF8Encoding $false))
      Write-Host "daily_task_reward_full.json written"
    }
  }
}

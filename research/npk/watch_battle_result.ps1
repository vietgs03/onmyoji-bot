<#
watch_battle_result.ps1 - Bat gia tri THAT de rap payload dungeon_rune_attack_result (chi DOC RAM).
Quet lien tuc Globals.localBattleEngine; khi dang co tran:
  - controllers[0].fightHeroUids  -> heroes
  - battle_ext_buff[camp1]        -> buff (getSkinBuffList)
  - player1.dungeon_reward        -> rewardId cua tran hien tai
In + ghi JSONL moi khi doi. KHONG gui gi len server.
  -Seconds  thoi gian theo doi (mac dinh 900)
  -Out      file JSONL
#>
param([int]$Seconds = 900, [string]$Out = "")
$ErrorActionPreference = "Stop"
$wSec=$Seconds; $wOut=$Out
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
$Seconds=$wSec; $Out=$wOut
function A($d,$k){ [PO]::DictGetStr($d,$k) }

# --- neo sys.modules -> Globals ---
$strs=[PO]::FindStrings("__builtin__"); $set=New-Object 'System.Collections.Generic.HashSet[long]'; foreach($s in $strs){[void]$set.Add($s)}
$sm=0; foreach($e in [PO]::FindEntries($set)){ if([PO]::TypeName([PO]::Q($e[2]+8)) -ne "module"){continue}; $dt=[PO]::Q([PO]::InstDict($e[2])+8); foreach($o in [PO]::FindOwnerDicts($dt,$e[0])){ if(([PO]::DictItems($o)).Count -gt 200 -and (A $o "Globals")){$sm=$o;break} }; if($sm){break} }
if(-not $sm){ throw "sys.modules not found" }
$G=[PO]::InstDict((A $sm "Globals"))
$pd=[PO]::InstDict((A $G "player1"))

Write-Host ("watch battle result for {0}s" -f $Seconds)
$prev=$null; $end=(Get-Date).AddSeconds($Seconds)
while((Get-Date) -lt $end){
  $eng=A $G "localBattleEngine"
  $engTn=[PO]::TypeName([PO]::Q($eng+8))
  $snap=$null
  if($eng -and $engTn -ne "NoneType"){
    $ed=[PO]::InstDict($eng)
    # heroes: controllers[0].fightHeroUids
    $heroes="[]"
    $ctrls=A $ed "controllers"
    if($ctrls -and [PO]::TypeName([PO]::Q($ctrls+8)) -eq "list"){
      $n=[PO]::Q($ctrls+16)
      if($n -ge 1){ $c0=[PO]::Q([PO]::Q($ctrls+24)); $cd=[PO]::InstDict($c0); $fh=A $cd "fightHeroUids"; if($fh){ $heroes=[PO]::Dump($fh,2) } }
    }
    # buff: battle_ext_buff (OrderedDict) - dump ca map
    $buff="{}"; $beb=A $ed "battle_ext_buff"; if($beb){ $buff=[PO]::Dump($beb,4) }
    $state=[PO]::Dump((A $ed "battleState"),1)
    $dr=A $pd "dungeon_reward"; $drj=if($dr){[PO]::Dump($dr,2)}else{"{}"}
    $snap=('{"engine":"0x' + ('{0:X}' -f $eng) + '","battleState":' + $state + ',"heroes":' + $heroes + ',"buff":' + $buff + ',"dungeon_reward":' + $drj + '}')
  } else {
    $dr=A $pd "dungeon_reward"; $drj=if($dr){[PO]::Dump($dr,2)}else{"{}"}
    $snap=('{"engine":null,"dungeon_reward":' + $drj + '}')
  }
  if($snap -ne $prev){
    $ts=(Get-Date).ToString("HH:mm:ss")
    Write-Host ("[{0}] {1}" -f $ts,$snap)
    if($Out){ [IO.File]::AppendAllText($Out, ('{"t":"'+$ts+'",' + $snap.Substring(1) + "`n")) }
    $prev=$snap
  }
  Start-Sleep -Milliseconds 700
}
Write-Host "done"

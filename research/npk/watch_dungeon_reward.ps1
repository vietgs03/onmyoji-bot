<#
watch_dungeon_reward.ps1 - Theo doi dict player1.dungeon_reward trong RAM game (chi DOC).
In ra moi khi noi dung thay doi (vd khi server tra dungeon_rune_attack_return -> rewardId).

  -Addr  : dia chi dict (lay tu: pyobj_dump.ps1 -Mode finddump -Name dungeon_reward -All)
  -Seconds: thoi gian theo doi (mac dinh 600)
  -Out   : file JSONL ghi lai moi lan thay doi
#>
param(
  [Parameter(Mandatory=$true)][string]$Addr,
  [int]$Seconds = 600,
  [string]$Out = ""
)
$ErrorActionPreference = "Stop"
# luu tham so TRUOC khi dot-source: param() cua pyobj_dump.ps1 ghi de $Addr/$Out
$wAddr = $Addr; $wSeconds = $Seconds; $wOut = $Out
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
$Addr = $wAddr; $Seconds = $wSeconds; $Out = $wOut
$a = [Convert]::ToInt64($Addr.Replace("0x",""),16)
$tn = [PO]::TypeName([PO]::Q($a+8))
if($tn -ne "dict"){ throw ("0x{0:X} khong phai dict (type={1}). Dia chi da doi, chay lai finddump." -f $a,$tn) }
Write-Host ("watching dungeon_reward @0x{0:X} for {1}s" -f $a,$Seconds)
$prev = $null
$end = (Get-Date).AddSeconds($Seconds)
while((Get-Date) -lt $end){
  $j = [PO]::Dump($a,4)
  if($j -ne $prev){
    $ts = (Get-Date).ToString("HH:mm:ss")
    Write-Host ("[{0}] dungeon_reward = {1}" -f $ts,$j)
    if($Out){ [IO.File]::AppendAllText($Out, ('{"t":"' + $ts + '","dungeon_reward":' + $j + "}`n")) }
    $prev = $j
  }
  Start-Sleep -Milliseconds 1000
}
Write-Host "done"

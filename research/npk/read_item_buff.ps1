<#
read_item_buff.ps1 - Lay ParamNameDef.ALL_ITEM_BUFF/EXPBUFF/MONEYBUFF tu RAM roi doc recordparam (chi DOC).
#>
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'pyobj_dump.ps1') -Mode none
function A($d,$k){ [PO]::DictGetStr($d,$k) }
$strs=[PO]::FindStrings("__builtin__"); $set=New-Object 'System.Collections.Generic.HashSet[long]'; foreach($s in $strs){[void]$set.Add($s)}
$sm=0; foreach($e in [PO]::FindEntries($set)){ if([PO]::TypeName([PO]::Q($e[2]+8)) -ne "module"){continue}; $dt=[PO]::Q([PO]::InstDict($e[2])+8); foreach($o in [PO]::FindOwnerDicts($dt,$e[0])){ if(([PO]::DictItems($o)).Count -gt 200 -and (A $o "Globals")){$sm=$o;break} }; if($sm){break} }
if(-not $sm){ throw "sys.modules not found" }
$G=[PO]::InstDict((A $sm "Globals"))
$pd=[PO]::InstDict((A $G "player1"))
# ParamNameDef class trong module com.param_def
$pmod=A $sm "com.param_def"
$codes=@{}
if($pmod){
  $pmd=[PO]::InstDict($pmod)
  $cls=A $pmd "ParamNameDef"
  if($cls){
    $cd=[PO]::Q($cls+264)  # tp_dict cua class
    if($cd -and [PO]::TypeName([PO]::Q($cd+8)) -eq "dict"){
      foreach($n in "ALL_ITEM_BUFF","EXPBUFF","MONEYBUFF","ALL_ITEM_STOP_BUFF","WEEKEND_EQUIP"){
        $v=A $cd $n
        if($v){ $sv=[PO]::Dump($v,1); $codes[$n]=$sv.Trim('"'); Write-Host ("ParamNameDef.$n = $sv") }
      }
    } else { Write-Host "class dict khong doc duoc" }
  }
}
$rp=A $pd "recordparam"
Write-Host ("recordparam {0} keys" -f ([PO]::DictItems($rp)).Count)
foreach($n in $codes.Keys){
  $key=$codes[$n]
  $v=A $rp $key
  Write-Host ("  recordparam['$key'] ($n) = " + $(if($v){[PO]::Dump($v,5)}else{"(khong co / rong)"}))
}

Add-Type -Path 'K:\KK\BepInEx\core\Mono.Cecil.dll'
$asm = [Mono.Cecil.AssemblyDefinition]::ReadAssembly('K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll')
$refEnum = $asm.MainModule.GetType('ChaReference/RefObjKey')
if ($refEnum) {
    Write-Host "=== ChaReference.RefObjKey ==="
    foreach ($f in $refEnum.Fields) {
        if ($f.IsLiteral) {
            Write-Host ("{0} = {1}" -f $f.Name, [int]$f.Constant)
        }
    }
}

$infoType = $asm.MainModule.GetType('Studio.Info')
foreach ($m in $infoType.Methods) {
    if ($m.Name -like '*Accessory*' -or $m.Name -like '*Init*') {
        Write-Host "Info method: $($m.Name)"
    }
}

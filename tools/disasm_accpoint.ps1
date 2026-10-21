Add-Type -Path 'K:\KK\BepInEx\core\Mono.Cecil.dll'
$asm = [Mono.Cecil.AssemblyDefinition]::ReadAssembly('K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll')
$infoType = $asm.MainModule.GetType('Studio.Info')
$m = $infoType.Methods | Where-Object { $_.Name -eq 'LoadAccessoryPointInfo' }
foreach ($inst in $m.Body.Instructions) {
    Write-Host ("{0:X4}: {1} {2}" -f $inst.Offset, $inst.OpCode, $inst.Operand)
}

Add-Type -Path 'K:\KK\BepInEx\core\Mono.Cecil.dll'
$asm = [Mono.Cecil.AssemblyDefinition]::ReadAssembly('K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll')
$infoType = $asm.MainModule.GetType('Studio.Info')
foreach ($m in $infoType.Methods) {
    if ($m.HasBody) {
        foreach ($inst in $m.Body.Instructions) {
            if ($inst.OpCode.Name -eq 'ldstr' -and $inst.Operand -like '*AccessoryPoint*') {
                Write-Host "$($m.Name): $($inst.Operand)"
            }
        }
    }
}

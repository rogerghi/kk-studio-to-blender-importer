Add-Type -Path 'K:\KK\BepInEx\core\Mono.Cecil.dll'
$asm = [Mono.Cecil.AssemblyDefinition]::ReadAssembly('K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll')
$infoType = $asm.MainModule.GetType('Studio.Info')
foreach ($m in $infoType.Methods) {
    if ($m.HasBody) {
        foreach ($inst in $m.Body.Instructions) {
            if ($inst.Operand -and $inst.Operand.ToString() -like '*LoadAccessoryPointInfo*') {
                Write-Host "Called from: $($m.Name)"
                foreach ($i2 in $m.Body.Instructions) {
                    Write-Host ("{0:X4}: {1} {2}" -f $i2.Offset, $i2.OpCode, $i2.Operand)
                }
            }
        }
    }
}

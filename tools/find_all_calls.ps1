Add-Type -Path 'K:\KK\BepInEx\core\Mono.Cecil.dll'
$asm = [Mono.Cecil.AssemblyDefinition]::ReadAssembly('K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll')
foreach ($t in $asm.MainModule.Types) {
    foreach ($m in $t.Methods) {
        if ($m.HasBody) {
            foreach ($inst in $m.Body.Instructions) {
                if ($inst.Operand -and $inst.Operand.ToString() -like '*LoadAccessoryPointInfo*') {
                    Write-Host "$($t.FullName)::$($m.Name)"
                }
            }
        }
    }
}

Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\BepInEx\plugins\KK_BepisPlugins\ExtensibleSaveFormat.dll")
$type = $assemblyDef.MainModule.GetType("ExtensibleSaveFormat.ExtendedSave/Hooks")
foreach ($m in $type.Methods) {
    Write-Host "$($m.Name):"
    foreach ($instr in $m.Body.Instructions) {
        if ($instr.Operand -ne $null) {
            Write-Host "   $($instr.OpCode) $($instr.Operand)"
        }
    }
}

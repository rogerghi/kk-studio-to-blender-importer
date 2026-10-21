Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\BepInEx\plugins\KK_BepisPlugins\ExtensibleSaveFormat.dll")
$type = $assemblyDef.MainModule.GetType("ExtensibleSaveFormat.ExtendedSave")
foreach ($m in $type.Methods) {
    if ($m.Name -like "*Scene*" -or $m.Name -like "*Load*" -or $m.Name -like "*Save*") {
        Write-Host "Method: $($m.Name)"
        foreach ($instr in $m.Body.Instructions) {
            Write-Host "   $($instr.Offset): $($instr.OpCode) $($instr.Operand)"
        }
    }
}

Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\BepInEx\patchers\KK_ExtensibleSaveFormat_Patcher.dll")
$type = $assemblyDef.MainModule.GetType("ExtensibleSaveFormat.Patcher")
foreach ($instr in ($type.Methods | Where-Object { $_.Name -eq "Patch" }).Body.Instructions) {
    if ($instr.Operand -ne $null) {
        Write-Host "$($instr.OpCode) $($instr.Operand)"
    }
}

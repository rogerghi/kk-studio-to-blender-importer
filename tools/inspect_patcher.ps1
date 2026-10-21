Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\BepInEx\patchers\KK_ExtensibleSaveFormat_Patcher.dll")
foreach ($t in $assemblyDef.MainModule.Types) {
    Write-Host $t.FullName
    foreach ($m in $t.Methods) {
        Write-Host "   $($m.Name)"
    }
}

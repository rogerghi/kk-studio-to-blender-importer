Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\BepInEx\plugins\KK_BepisPlugins\ExtensibleSaveFormat.dll")
foreach ($t in $assemblyDef.MainModule.Types) {
    Write-Host $t.FullName
    foreach ($nested in $t.NestedTypes) {
        Write-Host "   nested: $($nested.FullName)"
    }
}

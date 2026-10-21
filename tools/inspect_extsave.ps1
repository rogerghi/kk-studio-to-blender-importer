Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\BepInEx\plugins\KK_BepisPlugins\ExtensibleSaveFormat.dll")
foreach ($t in $assemblyDef.MainModule.Types) {
    Write-Host $t.FullName
    foreach ($m in $t.Methods) {
        if ($m.IsPublic) {
            Write-Host "   $($m.Name)"
        }
    }
}

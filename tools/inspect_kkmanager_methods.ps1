Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\[UTILITY] KKManager\KKManager.Core.dll")
foreach ($t in $assemblyDef.MainModule.Types) {
    foreach ($m in $t.Methods) {
        if ($m.Name -like "*Scene*") {
            Write-Host "$($t.FullName)::$($m.Name)"
        }
    }
}

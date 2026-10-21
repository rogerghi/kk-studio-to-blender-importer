Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\[UTILITY] KKManager\KKManager.Core.dll")
foreach ($t in $assemblyDef.MainModule.Types) {
    if ($t.Name -like "*Scene*" -or $t.Name -like "*Card*" -or $t.Name -like "*Png*") {
        Write-Host $t.FullName
    }
}

Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll")
$type = $assemblyDef.MainModule.GetType("Studio.ObjectInfo")
$m = $type.Methods | Where-Object { $_.Name -eq "Save" -or $_.Name -eq "Load" }
foreach ($method in $m) {
    Write-Host "=== Method: $($method.FullName)"
    foreach ($i in $method.Body.Instructions) {
        Write-Host "  $($i.Offset): $($i.OpCode) $($i.Operand)"
    }
}

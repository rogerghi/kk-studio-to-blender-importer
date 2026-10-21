Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll")

function Show-Method($typeName, $methodName) {
    $type = $assemblyDef.MainModule.GetType($typeName)
    if ($null -eq $type) {
        Write-Host "Type not found: $typeName"
        return
    }
    Write-Host "================ $typeName :: $methodName ================"
    foreach ($m in $type.Methods) {
        if ($m.Name -eq $methodName) {
            foreach ($instr in $m.Body.Instructions) {
                Write-Host "$($instr.Offset): $($instr.OpCode) $($instr.Operand)"
            }
        }
    }
}

Show-Method "Studio.ObjectInfo" "Load"
Show-Method "Studio.ChangeAmount" "Load"
Show-Method "Studio.OIFolderInfo" "Load"
Show-Method "Studio.OILightInfo" "Load"
Show-Method "Studio.PatternInfo" "Load"

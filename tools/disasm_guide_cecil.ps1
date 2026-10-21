Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll")
$type = $assemblyDef.MainModule.GetType("Studio.GuideObject")
foreach ($m in $type.Methods) {
    if ($m.Name -in @("CalcPosition", "CalcRotation", "CalcScale", "SetScale", "Awake", "ForceUpdate")) {
        Write-Host "=== Method: $($m.FullName) ==="
        if ($m.HasBody) {
            foreach ($i in $m.Body.Instructions) {
                Write-Host "  $($i.Offset): $($i.OpCode) $($i.Operand)"
            }
        }
    }
}

Add-Type -Path 'K:\KK\BepInEx\core\Mono.Cecil.dll'
$asm = [Mono.Cecil.AssemblyDefinition]::ReadAssembly('K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll')
$type = $asm.MainModule.GetType('Studio.OCIChar')
foreach ($m in $type.Methods) {
    if ($m.Name -in @('OnLoadAttach', 'OnAttach')) {
        Write-Host "=== Method: $($m.Name) ==="
        foreach ($inst in $m.Body.Instructions) {
            Write-Host ("{0:X4}: {1} {2}" -f $inst.Offset, $inst.OpCode, $inst.Operand)
        }
    }
}

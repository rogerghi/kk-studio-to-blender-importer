Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll")
$type = $assemblyDef.MainModule.GetType("Studio.OICharInfo")
foreach ($m in $type.Methods) {
    if ($m.Name -eq "Load") {
        $instructions = $m.Body.Instructions
        for ($i = 0; $i -lt [Math]::Min(120, $instructions.Count); $i++) {
            $instr = $instructions[$i]
            Write-Host "$($instr.Offset): $($instr.OpCode) $($instr.Operand)"
        }
    }
}

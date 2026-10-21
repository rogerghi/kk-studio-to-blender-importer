Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$assemblyDef = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll")
$type = $assemblyDef.MainModule.GetType("Studio.TreeNodeObject/TreeState")
foreach ($f in $type.Fields) {
    Write-Host "$($f.Name) = $($f.Constant)"
}

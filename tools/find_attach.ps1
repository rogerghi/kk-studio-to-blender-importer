Add-Type -Path 'K:\KK\BepInEx\core\Mono.Cecil.dll'
$asm = [Mono.Cecil.AssemblyDefinition]::ReadAssembly('K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll')
foreach ($type in $asm.MainModule.Types) {
    if ($type.Name -like '*OCIChar*' -or $type.Name -like '*OICharInfo*') {
        foreach ($m in $type.Methods) {
            if ($m.Name -like '*Attach*' -or $m.Name -like '*Child*') {
                Write-Host ($type.FullName + '::' + $m.Name)
            }
        }
    }
}

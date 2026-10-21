Add-Type -Path "K:\KK\[UTILITY] KKManager\Mono.Cecil.dll"
$a = [Mono.Cecil.AssemblyDefinition]::ReadAssembly("K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll")
$m = $a.MainModule.GetType("Studio.OIBoneInfo").Methods | Where-Object { $_.Name -eq "Load" }
$m.Body.Instructions | ForEach-Object {
    "{0,4}: {1,-15} {2}" -f $_.Offset, $_.OpCode, $_.Operand
} | Out-File "c:\Users\harri\AppData\Roaming\Blender Foundation\Blender\3.3\scripts\addons\extra_files\kk_scene_reader\bone_load_full.txt"

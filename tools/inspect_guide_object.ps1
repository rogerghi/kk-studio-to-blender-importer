$asm = [System.Reflection.Assembly]::LoadFrom("K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll")
$t = $asm.GetType("Studio.ObjectCtrlInfo")
$t.GetFields([System.Reflection.BindingFlags]"Public,NonPublic,Instance,Static") | ForEach-Object {
    Write-Host "ObjectCtrlInfo Field: $($_.FieldType.Name) $($_.Name)"
}
$t = $asm.GetType("Studio.GuideObject")
$t.GetFields([System.Reflection.BindingFlags]"Public,NonPublic,Instance,Static") | ForEach-Object {
    Write-Host "GuideObject Field: $($_.FieldType.Name) $($_.Name)"
}
$t = $asm.GetType("Studio.GuideObject")
$t.GetMethods([System.Reflection.BindingFlags]"Public,NonPublic,Instance,Static,DeclaredOnly") | ForEach-Object {
    Write-Host "GuideObject Method: $($_.ReturnType.Name) $($_.Name)"
}

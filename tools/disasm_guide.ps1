$asm = [System.Reflection.Assembly]::LoadFrom("K:\KK\CharaStudio_Data\Managed\Assembly-CSharp.dll")
$t = $asm.GetType("Studio.GuideObject")

function Disassemble-Method($method) {
    Write-Host "=== Method: $($method.Name) ==="
    $body = $method.GetMethodBody()
    if ($null -eq $body) { Write-Host "No body"; return }
    $il = $body.GetILAsByteArray()
    # Format IL
    $hex = [System.BitConverter]::ToString($il)
    Write-Host "IL Length: $($il.Length)"
    Write-Host "Hex: $hex"
}

foreach ($mname in @("CalcPosition", "CalcRotation", "CalcScale", "ForceUpdate")) {
    $m = $t.GetMethod($mname, [System.Reflection.BindingFlags]"Public,NonPublic,Instance,Static")
    if ($m) { Disassemble-Method $m }
}

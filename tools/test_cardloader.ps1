Add-Type -Path "K:\KK\[UTILITY] KKManager\MessagePack.dll"
Add-Type -Path "K:\KK\[UTILITY] KKManager\KKManager.Core.dll"

$path = "K:\KK\UserData\Studio\scene\2026_0222_2203_14_452.png"
$card = [KKManager.Data.Cards.CardLoader]::LoadCard($path)
if ($card -ne $null) {
    Write-Host "Card loaded successfully: $($card.GetType().FullName)"
    $card | Format-List *
} else {
    Write-Host "CardLoader returned null (likely not a standalone chara card)."
}

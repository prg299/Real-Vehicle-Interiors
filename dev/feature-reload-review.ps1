& (Join-Path $PSScriptRoot 'verify-feature-save.ps1')
[void](Lua 'getPlayer():getStats():set(CharacterStat.THIRST,0); MEMCNativeLab.releaseKeys(); return true')
Write-Host (Lua (Get-Content -LiteralPath (Join-Path $Lens.Root 'dev\lua\feature-fixture.lua') -Raw))
[void](Lua 'MELens.Dashboard.open(getPlayer(),MELensTest.vehicle); local w=MELens.Dashboard.instance; w:setX(45); w:setY(45); w:setVisible(true); return true')
Write-Host 'RELOADED_FEATURES_READY'

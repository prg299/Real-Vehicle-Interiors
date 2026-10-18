# Developer helper: the "towed camper on the road" scene for screenshots and videos (disposable test world only):
# launches the test game if it is closed, puts a pickup pulling the Flying Cloud 22 on the road (dev\lua\tow_scene.lua),
# walks the test character in, dresses it in military gear, hides the interface and sets the zoom.
#   .\dev\tow_setup.ps1 [-Zoom 1.0] [-AllowOtherGames]
param([double]$Zoom = 1.0, [switch]$AllowOtherGames)
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
function Lua([string]$code) { try { $r = & $lua -Code $code 2>$null; return ($r | ConvertFrom-Json).result } catch { return $null } }

if ((Lua 'return getPlayer() and "ingame" or "menu"') -notmatch 'ingame') {
    & (Join-Path $PSScriptRoot 'restart.ps1') -NoBuild -AllowOtherGames:$AllowOtherGames | Select-Object -Last 1
}
# off the screen: an idle test window on the desktop gets closed, and a closed game ends the recording
& (Join-Path $PSScriptRoot 'hide_window.ps1')
Lua 'local p = getPlayer(); if p:getVehicle() then MELens.leave(p) end; return 1' | Out-Null
Start-Sleep -Seconds 2
Write-Host (& $lua -File (Join-Path $PSScriptRoot 'lua\tow_scene.lua'))
Lua 'local p = getPlayer(); p:setX(10819.5); p:setY(10131.5); p:setLastX(10819.5); p:setLastY(10131.5); return 1' | Out-Null
Start-Sleep -Seconds 4
& (Join-Path $PSScriptRoot 'wait_still.ps1')
& $lua -File (Join-Path $PSScriptRoot 'lua\walkin.lua') | Out-Null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    $s = Lua 'local p = getPlayer(); local v = p:getVehicle(); return (v and ("seat " .. v:getSeat(p)) or "outside") .. " standing=" .. tostring(MELens.isStanding(p))'
    if ($s -match 'standing=true') { break }
}
Write-Host "state: $s"
& $lua -File (Join-Path $PSScriptRoot 'lua\dress_military.lua') | Out-Null
[void](Lua 'ISUIHandler.setVisibleAllUI(false); getPlayer():setGodMod(true); return 1')
for ($i = 0; $i -lt 16; $i++) {
    $now = [double](Lua 'return getCore():getZoom(0)')
    if ([math]::Abs($now - $Zoom) -lt 0.01) { break }
    [void](Lua ("getCore():doZoomScroll(0, " + $(if ($now -gt $Zoom) { -1 } else { 1 }) + "); return 1"))
    Start-Sleep -Milliseconds 1300
}
Write-Host "zoom $(Lua 'return getCore():getZoom(0)')"

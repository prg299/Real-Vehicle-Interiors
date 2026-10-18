# Developer helper: ME: LENS' furniture next to the game's own in one shot, light and zoom: launches the test game
# if it is closed, spawns a camper, walks in, puts a row of the game's furniture tiles on the camera's side of it
# and captures. The captures are the evidence for whether the furniture looks like the game's.
#   .\dev\vanilla_compare.ps1 [-Vehicle Base.Trailer61Airflyte] [-OutDir dir] [-Zoom 0.5] [-AllowOtherGames]
param([string]$Vehicle = 'Base.Trailer61Airflyte', [string]$OutDir, [double]$Zoom = 0.5, [switch]$AllowOtherGames, [switch]$KeepOpen)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$lua = Join-Path $root 'scripts\lua.ps1'
if (-not $OutDir) { $OutDir = Join-Path $root ('build\rv\dbg\compare\' + (Get-Date -Format 'MMdd-HHmmss')) }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
function Lua([string]$code) { try { return (& $lua -Code $code 2>$null | ConvertFrom-Json).result } catch { return $null } }

if ((Lua 'return getPlayer() and "ingame" or "menu"') -ne 'ingame') {
    & (Join-Path $PSScriptRoot 'restart.ps1') -NoBuild -AllowOtherGames:$AllowOtherGames | Select-Object -Last 1
}
& (Join-Path $PSScriptRoot 'hide_window.ps1') | Out-Null
Start-Sleep -Seconds 4
[void](& $lua -File (Join-Path $PSScriptRoot 'lua\setup.lua'))
[void](Lua 'local p = getPlayer(); if p:getVehicle() then MELens.leave(p) end return 1')
Start-Sleep -Seconds 3
& (Join-Path $PSScriptRoot 'enter_vehicle.ps1') -Name $Vehicle | Select-Object -Last 1
[void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))
[void](& $lua -File (Join-Path $root 'dev\lua\clean_ground.lua'))
[void](& $lua -File (Join-Path $PSScriptRoot 'lua\clear_vanilla.lua'))
Write-Host (& $lua -File (Join-Path $PSScriptRoot 'lua\vanilla_by_vehicle.lua'))
[void](Lua 'local p = getPlayer(); local v = p:getVehicle(); local g = MELens.WalkGrids[MELens.profileFor(v).walkGrid]; MELens.walkTo(p, MELens.profileFor(v).aisleX or 0, g.z0 + #g.rows * g.cell / 2) return 1')
Start-Sleep -Seconds 6
for ($i = 0; $i -lt 14; $i++) {
    $now = [double](Lua 'return getCore():getZoom(0)')
    if ([math]::Abs($now - $Zoom) -lt 0.01) { break }
    [void](Lua ("getCore():doZoomScroll(0, " + $(if ($now -gt $Zoom) { -1 } else { 1 }) + "); return 1"))
    Start-Sleep -Milliseconds 1300
}
[void](Lua 'ISUIHandler.setVisibleAllUI(false) return 1')
Start-Sleep -Seconds 3
& (Join-Path $PSScriptRoot 'capture.ps1') -Out (Join-Path $OutDir 'compare.png') | Out-Null
# leave the camper and clear the row, so the saved world is as it was (a character saved inside a vehicle, and the
# row standing on the grass, spoil the next captures)
if (-not $KeepOpen) {
    [void](Lua 'local p = getPlayer(); if p:getVehicle() then MELens.leave(p) end return 1')
    for ($i = 0; $i -lt 20; $i++) { Start-Sleep -Seconds 2; if ((Lua 'return getPlayer():getVehicle() and "in" or "out"') -eq 'out') { break } }
    [void](& $lua -File (Join-Path $PSScriptRoot 'lua\clear_vanilla.lua'))
    & (Join-Path $PSScriptRoot 'close.ps1') | Out-Null
}
Write-Host "capture: $(Join-Path $OutDir 'compare.png')"

# Developer helper: animals inside a camper seen from every side. The camera never turns, so each heading shows
# other walls in front of the animals: the camper is spawned facing N, E, S and W (Real Vehicle Interiors'
# dev\lua\spawn_one.lua, walkin.lua), you walk in, a hen and a dog are put down beside a water bowl, and the game
# takes a screenshot with the interface hidden (getCore():TakeFullScreenshot; window captures come out white).
# Removes the other vehicles of the test world (remove_others.lua), animals inside them too.
#   .\dev\headings.ps1 [-Vehicle Base.Trailer54FlyingCloud22] [-Headings N,E,S,W] [-Zoom 0.5] [-Instance 4]
# Writes <test profile>\Zomboid\Screenshots\animals_<heading>.png and build\headings.png (crops side by side).
param([string]$Vehicle = 'Base.Trailer54FlyingCloud22', [string[]]$Headings = @('N', 'E', 'S', 'W'),
    [double]$Zoom = 0.5, [int]$Instance = 4)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$lens = $root
$env:MELENS_LUA_PORT = "$(18470 + 2 * ($Instance - 1))"
$lua = Join-Path $lens 'scripts\lua.ps1'
$test = Join-Path $PSScriptRoot 'animals_test.ps1'
$shots = Join-Path $lens "build\rv\testhome$Instance\Zomboid\Screenshots"

function Lua([string]$code) { $r = & $lua -Code $code; return ($r | ConvertFrom-Json).result }

function Set-Zoom([double]$target) {
    for ($i = 0; $i -lt 8; $i++) {
        $now = [double](Lua 'return getCore():getZoom(0)')
        if ([math]::Abs($now - $target) -lt 0.01) { return }
        $step = if ($now -gt $target) { -1 } else { 1 }
        [void](Lua "getCore():doZoomScroll(0, $step); return 1")
        Start-Sleep -Milliseconds 1300
    }
}

function Leave-Vehicle {
    if ((Lua 'return getPlayer():getVehicle() and "in" or "out"') -eq 'in') {
        [void](Lua 'MELens.leave(getPlayer()); return 1')
        for ($i = 0; $i -lt 20; $i++) { Start-Sleep -Seconds 2; if ((Lua 'return getPlayer():getVehicle() and "in" or "out"') -eq 'out') { break } }
    }
}

[void](Lua @'
local climate = getClimateManager()
climate:stopWeatherAndThunder()
local rain = climate:getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY)
rain:setEnableAdmin(true); rain:setAdminValue(0)
getGameTime():setTimeOfDay(12)
return 1
'@)

$names = @()
foreach ($heading in $Headings) {
    Write-Host "== $Vehicle facing $heading"
    Leave-Vehicle
    [void](Lua 'local p = getPlayer(); local s = MELensTest and MELensTest.start or { x = 10813.5, y = 10140.5 }; p:setX(s.x); p:setY(s.y); p:setLastX(s.x); p:setLastY(s.y); return 1')
    [void](& $lua -File (Join-Path $lens 'dev\lua\remove_others.lua'))
    $spawn = (Get-Content -LiteralPath (Join-Path $lens 'dev\lua\spawn_one.lua') -Raw).Replace('NAME', $Vehicle).Replace('tonumber("7")', 'tonumber("-9")').Replace('local HEADING = "E"', "local HEADING = ""$heading""")
    [void](Lua $spawn)
    Start-Sleep -Seconds 1
    & (Join-Path $lens 'dev\wait_still.ps1')
    [void](& $lua -File (Join-Path $lens 'dev\lua\walkin.lua'))
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 2
        $state = Lua 'local p = getPlayer(); local v = p:getVehicle(); return (v and ("seat " .. v:getSeat(p)) or "outside") .. " standing=" .. tostring(MELens.isStanding(p))'
        if ($state -match 'seat -?[0-9]+ standing=true') { break }
    }
    [void](Lua @'
local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v)
local g = MELens.WalkGrids[profile.walkGrid]
MELens.walkTo(p, profile.aisleX or 0, g.z0 + #g.rows * g.cell / 2)
return 1
'@)
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if ((Lua 'local s = MELens.debugState(); return tostring(s.pathing) .. "," .. tostring(s.moving)') -eq 'false,false') { break }
    }
    & $test give:hen drop | Write-Host
    Start-Sleep -Seconds 5
    & $test give:dogfemale drop | Write-Host
    Start-Sleep -Seconds 5
    & $test water state | Write-Host
    Set-Zoom $Zoom
    [void](Lua 'ISUIHandler.setVisibleAllUI(false); return 1')
    Start-Sleep -Seconds 3
    $name = "animals_$heading.png"
    $file = Join-Path $shots $name
    if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file }
    [void](Lua "getCore():TakeFullScreenshot(""$name""); return 1")
    for ($i = 0; $i -lt 10 -and -not (Test-Path -LiteralPath $file); $i++) { Start-Sleep -Seconds 1 }
    [void](Lua 'ISUIHandler.setVisibleAllUI(true); return 1')
    $names += $file
}
Leave-Vehicle
$sheet = Join-Path $root 'build\animals\headings.png'
python (Join-Path $PSScriptRoot 'sheet.py') $sheet @names
Write-Host "sheet: $sheet"

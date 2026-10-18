# Developer helper: look at the inside of vehicles the way a player sees it, from every side.
# The camera never turns, so the side of the vehicle that faces it depends on which way the
# vehicle points: each vehicle is spawned facing N, E, S and W, walked into, and captured close
# up with the interface hidden. Wheel wells, furniture and boxes that stand against the walls
# nearest the camera show over those walls only from some headings, so a single capture is not
# enough to judge a layout.
#   .\dev\review_interiors.ps1 [-Only Base.Trailer87Scamp16,...] [-Headings N,E,S,W] [-Zoom 0.5]
#                              [-OutDir build\rv\dbg\review] [-AfterEnter dev\lua\loose_fill.lua]
# -AfterEnter file.lua: a Lua driver run inside each vehicle once you stand in it, before the picture
#   (dev/lua/loose_fill.lua puts items on every surface, dev/lua/shelf_fill.lua stands a shelf unit with items)
# Writes <OutDir>\<key>_<heading>.png (raw window captures); dev\review_sheet.py makes the
# contact sheets and enlarged crops to look at.
param([string[]]$Only, [string[]]$Headings = @('N', 'E', 'S', 'W'), [double]$Zoom = 0.5, [string]$OutDir, [string]$AfterEnter)

$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
if (-not $OutDir) { $OutDir = Join-Path $root 'build\rv\dbg\review' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$vehicles = @(
    @('Base.Trailer54FlyingCloud22', 'FlyingCloud22'),
    @('Base.Trailer61Bambi16', 'Bambi16'),
    @('Base.Trailer61Airflyte', 'Airflyte'),
    @('Base.Trailer61Astrodome', 'Astrodome'),
    @('Base.Trailer87Scamp13', 'Scamp13'),
    @('Base.Trailer87Scamp16', 'Scamp16'),
    @('Base.87fordB700school', 'B700bus'),
    @('Base.87fordF700box', 'F700box')
)

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

# vehicles an earlier run left in the saved world would stand in the picture
[void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))
[void](& $lua -File (Join-Path $root 'dev\lua\clean_ground.lua'))   # (blood splatters of the map)

foreach ($v in $vehicles) {
    $name, $key = $v
    if ($Only -and ($Only -notcontains $name)) { continue }
    foreach ($heading in $Headings) {
        Write-Host "== $key facing $heading"
        Leave-Vehicle
        # back to the start spot, spawn facing $heading (west of the start: grass, no power lines)
        [void](Lua 'local p = getPlayer(); local s = MELensTest and MELensTest.start or { x = 10813.5, y = 10140.5 }; p:setX(s.x); p:setY(s.y); p:setLastX(s.x); p:setLastY(s.y); return 1')
        $spawn = (Get-Content -LiteralPath (Join-Path $root 'dev\lua\spawn_one.lua') -Raw).Replace('NAME', $name).Replace('tonumber("7")', 'tonumber("-9")').Replace('local HEADING = "E"', "local HEADING = ""$heading""")
        [void](Lua $spawn)
        Start-Sleep -Seconds 1
        & (Join-Path $PSScriptRoot 'wait_still.ps1')
        [void](& $lua -File (Join-Path $root 'dev\lua\walkin.lua'))
        $state = ''
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Seconds 2
            $state = Lua 'local p = getPlayer(); local v = p:getVehicle(); return (v and ("seat " .. v:getSeat(p)) or "outside") .. " standing=" .. tostring(MELens.isStanding(p))'
            if ($state -match 'seat -?[0-9]+ standing=true') { break }
        }
        # the middle of the floor
        # (the saved world can hold vehicles that load late: clear them once we are in)
        [void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))
        [void](Lua @'
local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v)
local g = MELens.WalkGrids[profile.walkGrid]
MELens.walkTo(p, profile.aisleX or 0, g.z0 + #g.rows * g.cell / 2)
return 1
'@)
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            $s = Lua 'local s = MELens.debugState(); return tostring(s.pathing) .. "," .. tostring(s.moving)'
            if ($s -eq 'false,false') { break }
        }
        if ($AfterEnter) {
            Write-Host (& $lua -File (Resolve-Path $AfterEnter))
            Start-Sleep -Seconds 2
        }
        Set-Zoom $Zoom
        [void](Lua 'ISUIHandler.setVisibleAllUI(false); return 1')
        Start-Sleep -Seconds 3
        & (Join-Path $PSScriptRoot 'capture.ps1') -Out (Join-Path $OutDir "${key}_$heading.png") | Out-Null
        [void](Lua 'ISUIHandler.setVisibleAllUI(true); return 1')
    }
}
Leave-Vehicle
Write-Host "captures in $OutDir"

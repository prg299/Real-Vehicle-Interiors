# Developer helper: look at an END of a vehicle's inside (the rear or the front) from every side, the way
# dev\review_interiors.ps1 looks at the middle. The camera follows the character, so walking to an end puts
# that end in the middle of the picture, where the rear door, the front bulkhead, lights and corners can be seen
# enlarged.
#   .\dev\review_ends.ps1 -Name Base.87fordB700school -Key B700bus [-Where rear,front] [-Headings N,E,S,W]
#                         [-Zoom 0.5] [-OutDir build\rv\dbg\ends]
# Writes <OutDir>\<Key>_<where>_<heading>.png (raw window captures).
param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][string]$Key, [string[]]$Where = @('rear', 'front'),
      [string[]]$Headings = @('N', 'E', 'S', 'W'), [double]$Zoom = 0.5, [string]$OutDir)

$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
if (-not $OutDir) { $OutDir = Join-Path $root 'build\rv\dbg\ends' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

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
[void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))
[void](& $lua -File (Join-Path $root 'dev\lua\clean_ground.lua'))   # (blood splatters of the map)

foreach ($heading in $Headings) {
    Leave-Vehicle
    [void](Lua 'local p = getPlayer(); local s = MELensTest and MELensTest.start or { x = 10813.5, y = 10140.5 }; p:setX(s.x); p:setY(s.y); p:setLastX(s.x); p:setLastY(s.y); return 1')
    $spawn = (Get-Content -LiteralPath (Join-Path $root 'dev\lua\spawn_one.lua') -Raw).Replace('NAME', $Name).Replace('tonumber("7")', 'tonumber("-9")').Replace('local HEADING = "E"', "local HEADING = ""$heading""")
    [void](Lua $spawn)
    Start-Sleep -Seconds 1
    & (Join-Path $PSScriptRoot 'wait_still.ps1')
    [void](& $lua -File (Join-Path $root 'dev\lua\walkin.lua'))
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 2
        $state = Lua 'local p = getPlayer(); local v = p:getVehicle(); return (v and ("seat " .. v:getSeat(p)) or "outside") .. " standing=" .. tostring(MELens.isStanding(p))'
        if ($state -match 'seat -?[0-9]+ standing=true') { break }
    }
    [void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))     # (vehicles of the saved world can load late)
    foreach ($end in $Where) {
        Write-Host "== $Key $end facing $heading"
        # the walkable cell nearest the end, on the aisle
        $code = @'
local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v)
local g = MELens.WalkGrids[profile.walkGrid]
local zFar = g.z0 + #g.rows * g.cell
local z = "END" == "rear" and (g.z0 + 0.7) or (zFar - 0.7)
MELens.walkTo(p, profile.aisleX or 0, z)
return z
'@.Replace('END', $end)
        [void](Lua $code)
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Seconds 1
            $s = Lua 'local s = MELens.debugState(); return tostring(s.pathing) .. "," .. tostring(s.moving)'
            if ($s -eq 'false,false') { break }
        }
        Set-Zoom $Zoom
        [void](Lua 'ISUIHandler.setVisibleAllUI(false); return 1')
        Start-Sleep -Seconds 3
        & (Join-Path $PSScriptRoot 'capture.ps1') -Out (Join-Path $OutDir "${Key}_${end}_$heading.png") | Out-Null
        [void](Lua 'ISUIHandler.setVisibleAllUI(true); return 1')
    }
}
Leave-Vehicle
Write-Host "captures in $OutDir"

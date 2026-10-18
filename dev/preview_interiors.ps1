# Developer helper: a clean capture of the inside of each vehicle ME: LENS supports, from
# the running test game (scripts\testgame.ps1 + dev\fresh_world.ps1): spawn, walk in, walk
# to the middle of the floor, set the camera zoom, hide the game's interface, capture, leave.
#   .\dev\preview_interiors.ps1 [-Only Base.87fordB700school,F700box,...] [-OutDir build\rv\dbg\interiors]
# (-Only takes script names or the file keys below)
# -Zombies N: N zombies stand round the vehicle outside during the capture (dev/lua/zombies_around.lua)
# -AfterEnter file.lua: a Lua driver run inside each vehicle once you stand in it, before the picture
#   (dev/lua/loose_fill.lua puts items on every surface)
# Raw window captures go to <OutDir>\<key>.png; dev\preview_crop.py makes the final images.
param([string[]]$Only, [string]$OutDir, [int]$Zombies = 0, [string]$AfterEnter)

$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
if (-not $OutDir) { $OutDir = Join-Path $root 'build\rv\dbg\interiors' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# script name, file key, camera zoom (lower is closer)
$vehicles = @(
    @('Base.Trailer54FlyingCloud22', 'FlyingCloud22', 0.5),
    @('Base.Trailer61Bambi16', 'Bambi16', 0.5),
    @('Base.Trailer61Airflyte', 'Airflyte', 0.5),
    @('Base.Trailer61Astrodome', 'Astrodome', 0.5),
    @('Base.Trailer87Scamp13', 'Scamp13', 0.5),
    @('Base.Trailer87Scamp16', 'Scamp16', 0.5),
    @('Base.87fordB700school', 'B700bus', 0.75),
    @('Base.87fordF700box', 'F700box', 0.75)
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

# Clear sky, and no other vehicles around the test spot (this is the disposable test world).
[void](Lua @'
local climate = getClimateManager()
climate:stopWeatherAndThunder()
local rain = climate:getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY)
rain:setEnableAdmin(true); rain:setAdminValue(0)
getGameTime():setTimeOfDay(12)
local p = getPlayer(); local cell = getCell(); local n = 0
local px, py = math.floor(p:getX()), math.floor(p:getY())
-- Short grass and ground scatter poke up through a vehicle's floor when it is parked on a
-- lawn (a quirk of the game's depth sorting): clear it around the spot for clean previews.
local s = MELensTest and MELensTest.start
if s then
    for x = math.floor(s.x) - 3, math.floor(s.x) + 16 do
        for y = math.floor(s.y) - 5, math.floor(s.y) + 5 do
            local sq = cell:getGridSquare(x, y, 0)
            if sq then
                for i = sq:getObjects():size() - 1, 1, -1 do
                    local o = sq:getObjects():get(i)
                    local name = o:getSprite() and o:getSprite():getName() or ""
                    if name:find("^e_newgrass") or name:find("^blends_grassoverlays") or name:find("^d_generic") then
                        sq:RemoveTileObject(o)
                    end
                end
            end
        end
    end
end
local seen = {}
for x = px - 25, px + 35 do
    for y = py - 25, py + 25 do
        local sq = cell:getGridSquare(x, y, 0)
        local v = sq and sq:getVehicleContainer()
        if v and not seen[v] then
            seen[v] = true
            if v ~= MELensTest.vehicle then v:permanentlyRemove(); n = n + 1 end
        end
    end
end
return n
'@)

# vehicles of the saved test world load late and stand in the picture: clear them, and the map's blood splatters
[void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))
[void](& $lua -File (Join-Path $root 'dev\lua\clean_ground.lua'))
[void](& $lua -File (Join-Path $root 'dev\lua\clear_vanilla.lua'))
[void](& $lua -File (Join-Path $root 'dev\lua\clean_items.lua'))

foreach ($v in $vehicles) {
    $name, $key, $zoom = $v
    if ($Only -and ($Only -notcontains $name) -and ($Only -notcontains $key)) { continue }
    Write-Host "== $key"
    # leave a vehicle we are still in
    if ((Lua 'return getPlayer():getVehicle() and "in" or "out"') -eq 'in') {
        [void](Lua 'MELens.leave(getPlayer()); return 1')
        for ($i = 0; $i -lt 20; $i++) { Start-Sleep -Seconds 2; if ((Lua 'return getPlayer():getVehicle() and "in" or "out"') -eq 'out') { break } }
    }
    & (Join-Path $PSScriptRoot 'enter_vehicle.ps1') -Name $name | Out-Null
    [void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))
    # the middle of the floor, on the walkable cell nearest the aisle
    [void](Lua @'
local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v)
local g = MELens.WalkGrids[profile.walkGrid]
local zc = g.z0 + #g.rows * g.cell / 2
MELens.walkTo(p, profile.aisleX or 0, zc)
return zc
'@)
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        $s = Lua 'local s = MELens.debugState(); return tostring(s.pathing) .. "," .. tostring(s.moving)'
        if ($s -eq 'false,false') { break }
    }
    Set-Zoom $zoom
    if ($AfterEnter) {
        Write-Host (& $lua -File (Resolve-Path $AfterEnter))
        Start-Sleep -Seconds 3
    }
    [void](Lua 'ISUIHandler.setVisibleAllUI(false); return 1')
    if ($Zombies -gt 0) {
        $z = (Get-Content (Join-Path $PSScriptRoot 'lua\zombies_around.lua') -Raw).Replace('"COUNT"', """$Zombies""").Replace('"RADIUS"', '"4.5"')
        Write-Host (& $lua -Code $z)
        Start-Sleep -Seconds 4
    }
    Start-Sleep -Seconds 3
    & (Join-Path $PSScriptRoot 'capture.ps1') -Out (Join-Path $OutDir "$key.png") | Out-Null
    [void](Lua 'ISUIHandler.setVisibleAllUI(true); return 1')
    # the zombies go before the next vehicle's walk-in (they crowd the door)
    if ($Zombies -gt 0) { [void](Lua 'for _, z in ipairs(MELensTest.zombies or {}) do pcall(function() z:removeFromWorld(); z:removeFromSquare() end) end; MELensTest.zombies = {}; return 1') }
}
# leave the last one
if ($Zombies -gt 0) { [void](Lua 'for _, z in ipairs(MELensTest.zombies or {}) do pcall(function() z:removeFromWorld(); z:removeFromSquare() end) end; MELensTest.zombies = {}; return 1') }
if ((Lua 'return getPlayer():getVehicle() and "in" or "out"') -eq 'in') {
    [void](Lua 'MELens.leave(getPlayer()); return 1')
    for ($i = 0; $i -lt 20; $i++) { Start-Sleep -Seconds 2; if ((Lua 'return getPlayer():getVehicle() and "in" or "out"') -eq 'out') { break } }
}
Write-Host "captures in $OutDir"

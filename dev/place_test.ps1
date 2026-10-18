# Developer helper: how forgiving the Place mode is (2.0.1). In a Flying Cloud 22 in the test game it points the place
# mode (dev\lua\loose_test.lua through dev\loose.ps1) at spots that used to be refused and checks that the preview is
# green there, moved only a little: the floor right against a wall, the floor touching a bed, the same spot as an item
# already lying there, the very edge of the counter. Then it sets one of them down to check the server's own check
# takes it. Prints PASS or FAIL for each check; exit code 1 if any failed.
#   .\dev\place_test.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0

function Value([string]$code) { $r = & $lua -Code $code; return ($r | ConvertFrom-Json).result }
function Loose([string]$mode, [string]$arg = '') { $r = & (Join-Path $PSScriptRoot 'loose.ps1') $mode $arg; return ($r | ConvertFrom-Json).result }
function Check([string]$name, [bool]$ok, $detail = '') {
    if ($ok) { Write-Host "PASS  $name" } else { Write-Host "FAIL  $name  $detail"; $script:failed++ }
}
function Wait-Idle([int]$seconds = 40) {
    for ($i = 0; $i -lt $seconds / 0.7; $i++) {
        Start-Sleep -Milliseconds 700
        $s = Value 'local p = getPlayer(); return tostring(MELens.pathing(p)) .. "," .. tostring(ISTimedActionQueue.isPlayerDoingAction(p)) .. "," .. #ISTimedActionQueue.getTimedActionQueue(p).queue'
        if ($s -match 'false,false,0') { Start-Sleep -Milliseconds 900; return }
    }
}
# the hover the mode shows for a passenger-space point: "valid moved" e.g. "true 0.04"
function Hover-At([string]$point) {
    [void](Loose 'at' $point)
    Start-Sleep -Milliseconds 400
    $h = Loose 'hover'
    $x, $y, $z = $point -split ','
    if ($h -match 'at ([-0-9.]+),([-0-9.]+),([-0-9.]+) valid=(\w+) reason=(\w+)') {
        $dx = [double]::Parse($Matches[1], [Globalization.CultureInfo]::InvariantCulture) - [double]::Parse($x, [Globalization.CultureInfo]::InvariantCulture)
        $dz = [double]::Parse($Matches[3], [Globalization.CultureInfo]::InvariantCulture) - [double]::Parse($z, [Globalization.CultureInfo]::InvariantCulture)
        $moved = [math]::Sqrt($dx * $dx + $dz * $dz)
        return @{ valid = ($Matches[4] -eq 'true'); moved = $moved; text = $h }
    }
    return @{ valid = $false; moved = 99; text = "$h" }
}

$consolePath = Join-Path $root 'build\rv\testhome\Zomboid\console.txt'
$consoleStart = (Get-Item -LiteralPath $consolePath).Length

# --- in a camper with two pots and a hammer
if ((Value 'return tostring(MELens.isStanding(getPlayer()) and getPlayer():getVehicle():getScript():getName() == "Trailer54FlyingCloud22")') -ne 'true') {
    [void](Value 'local p = getPlayer(); if p:getVehicle() then MELens.leave(p) end; return 1')
    Start-Sleep -Seconds 8
    [void](& (Join-Path $PSScriptRoot 'enter_vehicle.ps1') -Name 'Base.Trailer54FlyingCloud22')
    Wait-Idle
}
Check 'standing in a Flying Cloud 22' ((Value 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true')
[void](Value 'MELens.LooseUI.testMouse = nil; return 1')
[void](Loose 'clear')
[void](Loose 'give' 'Base.Pot,Base.Pot,Base.Hammer')
$mode = Loose 'start' 'Pot'
Check 'the place mode starts' ($mode -eq 'mode on') $mode
$floorY = Value 'return tostring(MELens.profileFor(getPlayer():getVehicle()).floorY)'

# Points the old rules refused although a pot fits close by: its middle right at a wall where the floor next to the
# wall is open, and right at the front edge of the side bed. Asked through MELens.LooseUI.placeNear (the controller's
# way in: what the camera hides does not matter here); the answer is "valid moved" for each.
# (the pot's size is known once its model has loaded)
for ($i = 0; $i -lt 20; $i++) {
    if ((Value 'local item = getPlayer():getInventory():getFirstTypeRecurse("Pot"); return tostring(item ~= nil and MELens.LooseUI.size(item) ~= nil)') -eq 'true') { break }
    Start-Sleep -Milliseconds 500
}
$nearChecks = Value @'
local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v); local L = MELens.Loose; local UI = MELens.LooseUI
local item = p:getInventory():getFirstTypeRecurse("Pot")
local w, h, d = UI.size(item)
if not w then return "size unknown" end
local hx, hz = L.half(w, d, 0)
local floor = { kind = "floor", s = 0, y = profile.floorY }
local out = {}
local function ask(name, x, z)
    local r = UI.placeNear(v, profile, item, 0, floor, x, z)
    local old = L.fitsSurface(v, profile, floor, x, z, hx + L.WALL_SLACK, hz + L.WALL_SLACK)
    out[#out + 1] = string.format("%s %s %.3f old=%s", name, tostring(r and r.valid), r and math.sqrt((r.x - x) ^ 2 + (r.z - z) ^ 2) or 99, tostring(old))
end
local x0, x1, z0, z1 = L.roomBounds(profile)
local found = false
for zz = z0 + 0.2, z1 - 0.2, 0.05 do
    for _, dir in ipairs({ 1, -1 }) do
        local x = 0
        while L.inRoom(profile, x + 0.01 * dir, zz) and math.abs(x) < 3 do x = x + 0.01 * dir end
        if not found and L.fitsSurface(v, profile, floor, x - dir * (hx + 0.04), zz, hx, hz) then
            ask("wall", x - 0.005 * dir, zz)
            found = true
        end
    end
end
if not found then out[#out + 1] = "wall none" end
local r = L.solids(v, profile)[2]
local bx = math.abs(r.x0) < math.abs(r.x1) and r.x0 - 0.01 or r.x1 + 0.01
ask("bed", bx, (r.z0 + r.z1) / 2)
return table.concat(out, "|")
'@
Check 'the pot''s size is known' ($nearChecks -ne 'size unknown' -and $nearChecks) "$nearChecks"
foreach ($line in ($nearChecks -split '\|')) {
    $parts = $line -split ' '
    if ($parts.Count -lt 4 -and $parts[1] -ne 'none') { continue }
    if ($parts[1] -eq 'none') { Write-Host "      (no $($parts[0]) point found)"; continue }
    $moved = [double]::Parse($parts[2], [Globalization.CultureInfo]::InvariantCulture)
    $what = if ($parts[0] -eq 'wall') { 'a pot right at a wall' } else { 'a pot right at the front of a bed' }
    Check "$($what): green, moved only a little (the old rules refused it)" (($parts[1] -eq 'true') -and $moved -lt 0.31 -and ($parts[3] -eq 'old=false')) $line
}

# set a pot down in the aisle, then point the second pot at the same place
$aisle = Value 'local v = getPlayer():getVehicle(); local profile = MELens.profileFor(v); local g = MELens.WalkGrids[profile.walkGrid]; return string.format("%.3f,%.3f", profile.aisleX or 0, g.z0 + #g.rows * g.cell / 2)'
$ax, $az = $aisle -split ','
[void](Value 'if MELens.LooseUI.active then MELens.LooseUI.active:stop() end; return 1')
[void](Loose 'place' ("Pot|{0},{1},{2},0,0" -f $ax, $floorY, $az))
Wait-Idle
$count = Value 'local v = getPlayer():getVehicle(); local n = 0; for _ in pairs(MELens.Loose.positions(v, false) or {}) do n = n + 1 end; return n'
Check 'a pot set down in the aisle' ($count -eq 1) "positions=$count"
[void](Loose 'start' 'Pot')
$h = Hover-At "$ax,$floorY,$az"
Check 'a second pot at the same place: green (next to it, or over it), not refused' $h.valid $h.text

# the very edge of the counter
$counter = Value @'
local v = getPlayer():getVehicle(); local profile = MELens.profileFor(v)
for _, s in ipairs(MELens.Loose.surfaces(v, profile)) do
    if s.name == "counter" then return string.format("%.3f,%.3f,%.3f", s.x0, s.y, (s.z0 + s.z1) / 2) end
end
return "none"
'@
if ($counter -ne 'none') {
    $h = Hover-At $counter
    Check 'the very edge of the counter: green' ($h.valid -and $h.text -match '^piece') $h.text
}

# what the mode shows is what the server takes: set the second pot down where it showed
$shown = Value 'local h = MELens.LooseUI.active and MELens.LooseUI.active.hover; return h and string.format("%.3f,%.3f,%.3f,%d", h.x, h.y, h.z, h.surface.s) or "none"'
[void](Value 'if MELens.LooseUI.active then MELens.LooseUI.active:stop() end; return 1')
if ($shown -ne 'none') {
    $sx, $sy, $sz, $ss = $shown -split ','
    [void](Loose 'place' ("Pot|{0},{1},{2},0,{3}" -f $sx, $sy, $sz, $ss))
    Wait-Idle
    $count = Value 'local v = getPlayer():getVehicle(); local n = 0; for _ in pairs(MELens.Loose.positions(v, false) or {}) do n = n + 1 end; return n'
    Check 'set down where the preview was: it is taken' ($count -eq 2) "positions=$count ($shown)"
}

$stream = [IO.File]::Open($consolePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
try {
    [void]$stream.Seek([Math]::Min($consoleStart, $stream.Length), [IO.SeekOrigin]::Begin)
    $text = [IO.StreamReader]::new($stream).ReadToEnd()
} finally { $stream.Dispose() }
$errors = @($text -split "`n" | Where-Object { $_ -cmatch 'MELens[A-Za-z_]*\.lua:\d+\)|\[ME_LENS\].*(failed|not shown|not drawn)' } | Select-Object -First 3)
Check 'no mod errors in the console during this run' ($errors.Count -eq 0) ($errors -join '; ')
[void](Loose 'clear')

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

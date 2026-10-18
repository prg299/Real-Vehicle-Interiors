# Developer helper: the seats inside a camper (2.0.1). In the test game it spawns a Flying Cloud 22 and checks that its
# beds and benches cannot be entered from outside (the game's seat picker, its enter action queued directly, the
# enter function with a bed's seat: each walks you in or is refused), that E next to a dinette or a bed sits or lays
# you down there, that E or the game's Exit there gets you up inside, that E away from any seat does nothing, and
# that E on the green exit marker leaves. Prints PASS or FAIL for each check; exit code 1 if any failed.
#   .\dev\seats_test.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0

function Value([string]$code) { $r = & $lua -Code $code; return ($r | ConvertFrom-Json).result }
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
# where the character is: outside, standing, or the id of the seat it is on
$where = 'local p = getPlayer(); local v = p:getVehicle(); if not v then return "outside" end; if MELens.isStanding(p) then return "standing" end; return "seat " .. v:getScript():getPassenger(v:getSeat(p)):getId()'
function Get-Place { return Value $where }
function Wait-Where([string]$pattern, [int]$seconds = 20) {
    $w = ''
    for ($i = 0; $i -lt $seconds * 2; $i++) {
        $w = Get-Place
        if ($w -match $pattern) { return $w }
        Start-Sleep -Milliseconds 500
    }
    return $w
}
function Press-E { [void](Value 'local p = getPlayer(); triggerEvent("OnUseVehicle", p, p:getVehicle() or MELensTest.vehicle, false); return 1') }

# --- a camper, and we stand outside it
[void](Value 'local p = getPlayer(); if p:getVehicle() then MELens.leave(p) end; return 1')
[void](Wait-Where '^outside$' 30)
[void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))
$spawn = (Get-Content -LiteralPath (Join-Path $root 'dev\lua\spawn_one.lua') -Raw).Replace('NAME', 'Base.Trailer54FlyingCloud22').Replace('tonumber("7")', 'tonumber("-9")')
[void](Value 'local p = getPlayer(); local s = MELensTest and MELensTest.start or { x = 10813.5, y = 10140.5 }; p:setX(s.x); p:setY(s.y); p:setLastX(s.x); p:setLastY(s.y); return 1')
[void](Value $spawn)
Start-Sleep -Seconds 1
& (Join-Path $PSScriptRoot 'wait_still.ps1')
$bed = Value 'return MELens.seatIndex(MELensTest.vehicle, "FrontB")'
Check 'a camper with a bed seat' ($bed -ge 0) $bed

# --- outside: another mod's entry key (Get In The Damn Car! calls ISVehicleMenu.onEnterAux for the nearest free
# seat, a bed through the camper's door) does nothing away from the way in, and walks you in close to it; E at the
# way in, facing it, walks in
$wayIn = Value 'local v = MELensTest.vehicle; local pos = Vector3f.new(); v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v), "outside"), pos); MELensTest.wayIn = { x = pos:x(), y = pos:y() }; return string.format("%.1f,%.1f", pos:x(), pos:y())'
$far = Value @'
local p = getPlayer(); local v = MELensTest.vehicle; local w = MELensTest.wayIn
local vec = Vector3f.new()
for _, lz in ipairs({ -2.6, -2.2, 2.6, 2.2, -1.8 }) do
    for _, lx in ipairs({ 1.4, -1.4 }) do
        v:getWorldPos(lx, 0, lz, vec)
        local d = math.sqrt((vec:x() - w.x) ^ 2 + (vec:y() - w.y) ^ 2)
        if d > MELens.DOOR_REACH + 1 then
            ISTimedActionQueue.clear(p)
            p:setX(vec:x()); p:setY(vec:y()); p:setLastX(vec:x()); p:setLastY(vec:y())
            return string.format("%.1f,%.1f (%.1f tiles from the way in)", vec:x(), vec:y(), d)
        end
    end
end
return "none"
'@
Check 'a place beside the camper, away from its way in' ($far -ne 'none') "way in at $wayIn"
Start-Sleep -Seconds 1
[void](Value "ISVehicleMenu.onEnterAux(getPlayer(), MELensTest.vehicle, $bed); return 1")
Start-Sleep -Seconds 3
$q = Value 'local p = getPlayer(); return #ISTimedActionQueue.getTimedActionQueue(p).queue .. " " .. tostring(ISTimedActionQueue.isPlayerDoingAction(p))'
$w = Get-Place
Check 'another mod taking you to a bed from beside the wall: nothing happens (no running round to the door)' (($q -eq '0 false') -and ($w -eq 'outside')) "queue $q, $w at $far"
[void](Value 'local p = getPlayer(); local w = MELensTest.wayIn; ISTimedActionQueue.clear(p); p:setX(w.x + 0.6); p:setY(w.y + 0.6); p:setLastX(w.x + 0.6); p:setLastY(w.y + 0.6); return 1')
Start-Sleep -Seconds 1
[void](Value "ISVehicleMenu.onEnterAux(getPlayer(), MELensTest.vehicle, $bed); return 1")
$w = Wait-Where '^standing$' 30
Check 'the same close to the way in walks you in' ($w -eq 'standing') $w
Wait-Idle
[void](Value 'local p = getPlayer(); if p:getVehicle() then MELens.leave(p) end; return 1')
[void](Wait-Where '^outside$' 30)
[void](Value 'local p = getPlayer(); local w = MELensTest.wayIn; local v = MELensTest.vehicle; ISTimedActionQueue.clear(p); p:setX(w.x); p:setY(w.y); p:setLastX(w.x); p:setLastY(w.y); local lp = v:getLocalPos(w.x, w.y, v:getZ(), Vector3f.new()); local c = Vector3f.new(); v:getWorldPos(0, 0, lp:z(), c); p:faceLocation(c:x(), c:y()); return 1')
Start-Sleep -Seconds 1
$part = Value 'local p = getPlayer(); local part = MELensTest.vehicle:getUseablePart(p); return part and part:getId() or "none"'
Press-E
$w = Wait-Where '^standing$' 30
Check 'E at the way in, facing it, walks in' ($w -eq 'standing') "$w (E reaches $part)"
Wait-Idle
[void](Value 'local p = getPlayer(); if p:getVehicle() then MELens.leave(p) end; return 1')
[void](Wait-Where '^outside$' 30)

# --- from outside: never onto a bed
[void](Value "local p = getPlayer(); ISTimedActionQueue.clear(p); ISTimedActionQueue.add(ISPathFindAction:pathToVehicleSeat(p, MELensTest.vehicle, $bed)); ISTimedActionQueue.add(ISEnterVehicle:new(p, MELensTest.vehicle, $bed)); return 1")
Start-Sleep -Seconds 8
$w = Get-Place
Check 'the game''s enter action queued for a bed from outside is refused' ($w -eq 'outside') $w
[void](Value 'local p = getPlayer(); ISTimedActionQueue.clear(p); return 1')
[void](Value 'ISVehicleMenu.onShowSeatUI(getPlayer(), MELensTest.vehicle); return 1')
$picker = Value 'local ui = ISVehicleMenu.seatUI and ISVehicleMenu.seatUI[0]; local q = ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue; local names = {}; for _, a in ipairs(q) do names[#names + 1] = tostring(a.Type) end; return tostring(ui ~= nil and ui:isReallyVisible()) .. " " .. table.concat(names, ",")'
Check '"Enter vehicle" outside a camper walks in instead of offering the beds' ($picker -match '^false .*MELensEnterCabin') $picker
$w = Wait-Where '^standing$' 30
Check 'and you stand inside' ($w -eq 'standing') $w
Wait-Idle

# --- E next to a dinette: sit; E again: up
$spots = Value 'local v = getPlayer():getVehicle(); local profile = MELens.profileFor(v); local out = {}; for i, s in ipairs(profile.spots) do local piece = MELens.Parts.pieceAt(MELens.Parts.spotPart(v, i)); out[#out + 1] = i .. "=" .. tostring(piece) end; return table.concat(out, " ")'
Write-Host "      pieces: $spots"
function Stand-Near([string]$piece) {
    # in front of the first piece of that kind: its seat's stand point
    return Value @"
local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v)
for i, s in ipairs(profile.spots) do
    if MELens.Parts.pieceAt(MELens.Parts.spotPart(v, i)) == "$piece" and s.seats then
        local x, z = MELens.seatStandPoint(v, profile, MELens.seatIndex(v, s.seats[1]))
        if x then MELens.walkTo(p, x, z); return string.format("%.2f,%.2f", x, z) end
    end
end
return "none"
"@
}
$at = Stand-Near 'dinette'
Wait-Idle
Press-E
$w = Wait-Where '^seat (FrontL|FrontR|RearL|RearR)$' 20
Check 'E next to the dinette sits you at it' ($w -match '^seat (FrontL|FrontR|RearL|RearR)$') "$w (walked to $at)"
Wait-Idle
Press-E
$w = Wait-Where '^standing$' 15
Check 'E at the dinette gets you up, standing inside' ($w -eq 'standing') $w
Wait-Idle

# --- E next to a bed: lie down; the game's Exit: up, inside
$at = Stand-Near 'bed'
Wait-Idle
Press-E
$w = Wait-Where '^seat (FrontB|SideB)$' 20
Check 'E next to a bed lays you on it' ($w -match '^seat (FrontB|SideB)$') "$w (walked to $at)"
Wait-Idle
[void](Value 'ISVehicleMenu.onExit(getPlayer()); return 1')
$w = Wait-Where '^standing$' 15
Check 'the game''s Exit on the bed gets you up inside, not out of the camper' ($w -eq 'standing') $w
Wait-Idle

# --- E with no seat in reach: nothing
$free = Value @'
local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v)
local g = MELens.WalkGrids[profile.walkGrid]
local m = profile.exitMarker
for r = 0, #g.rows - 1, 4 do
    for c = 0, g.cols - 1, 4 do
        local x, z = g.x0 + (c + 0.5) * g.cell, g.z0 + (r + 0.5) * g.cell
        local mdx = m and math.max(0, math.abs(x - m.x) - m.halfX) or 9
        local mdz = m and math.max(0, math.abs(z - m.z) - m.halfZ) or 9
        local nearMarker = mdx * mdx + mdz * mdz < 1.45 * 1.45
        if not nearMarker and MELens.walkableAt(profile, x, z) then
            local px, pz = MELens.nearestWalkableAt(profile, x, z)
            MELensTest.probe = { x = px, z = pz }
            local saved = { MELens.Parts.characterAt }
            MELens.Parts.characterAt = function() return px, pz end
            local ok, seat = pcall(MELens.Interact.seatNear, p, v, profile)
            MELens.Parts.characterAt = saved[1]
            if ok and not seat then MELens.walkTo(p, px, pz); return string.format("%.2f,%.2f", px, pz) end
        end
    end
end
return "none"
'@
if ($free -ne 'none') {
    Wait-Idle
    Press-E
    Start-Sleep -Seconds 3
    $w = Get-Place
    Check 'E with no seat in reach does nothing (still standing)' ($w -eq 'standing') "$w at $free"
} else {
    Write-Host '      (every walkable point of this camper has a seat in reach: no E-does-nothing check)'
}

# --- E by the door, off the marker, with no seat nearer than the door: out
$byDoor = Value @'
local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v)
local m = profile.exitMarker
for _, r in ipairs({ 0.35, 0.5, 0.7, 0.9 }) do
    for k = 0, 15 do
        local a = k * math.pi / 8
        local x, z = m.x + (m.halfX + r) * math.cos(a), m.z + (m.halfZ + r) * math.sin(a)
        if MELens.walkableAt(profile, x, z) then
            local mdx = math.max(0, math.abs(x - m.x) - m.halfX)
            local mdz = math.max(0, math.abs(z - m.z) - m.halfZ)
            local md = math.sqrt(mdx * mdx + mdz * mdz)
            local saved = MELens.Parts.characterAt
            MELens.Parts.characterAt = function() return x, z end
            local ok, seat = pcall(MELens.Interact.seatNear, p, v, profile)
            MELens.Parts.characterAt = saved
            if md > 0.05 and ok and (not seat or seat.d > md) then
                MELens.walkTo(p, x, z)
                return string.format("%.2f,%.2f", x, z)
            end
        end
    end
end
return "none"
'@
if ($byDoor -ne 'none') {
    Wait-Idle
    Press-E
    $w = Wait-Where '^outside$' 30
    Check 'E by the door, off the marker, leaves the camper' ($w -eq 'outside') "$w at $byDoor"
    $state = (& (Join-Path $PSScriptRoot 'enter_vehicle.ps1') -Name 'Base.Trailer54FlyingCloud22' | Select-Object -Last 1)
    Wait-Idle
} else {
    Write-Host '      (no point by the door without a nearer seat: no by-the-door check)'
}

# --- E on the exit marker: out
[void](Value 'local p = getPlayer(); local v = p:getVehicle(); local m = MELens.profileFor(v).exitMarker; MELens.walkTo(p, m.x, m.z); return 1')
Wait-Idle
Press-E
$w = Wait-Where '^outside$' 30
Check 'E on the green exit marker leaves the camper' ($w -eq 'outside') $w

# --- errors
$errors = Select-String -LiteralPath (Join-Path $root 'build\rv\testhome\Zomboid\console.txt') -CaseSensitive -Pattern 'MELens[A-Za-z_]*\.lua:\d+\)|\[ME_LENS\].*(failed|not shown|not drawn)' | Select-Object -First 3
Check 'no mod errors in the console' ($null -eq $errors) (($errors | ForEach-Object { $_.Line }) -join '; ')

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

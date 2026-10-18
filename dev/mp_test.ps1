# Developer helper: a multiplayer smoke test of ME: LENS 2.0 against the disposable local server. Start the server
# (dev\mp_server.ps1) and connect the test game (dev\mp_connect.ps1) first. It spawns a Flying Cloud 22 next to the
# connected admin, walks in and exercises what 2.0 added through the real timed actions (whose work runs on the
# server), comparing what the server holds (asked through the developer mod's "eval" command, see
# dev\RealVehicleInteriors_Dev) with what the client sees. Prints PASS or FAIL for each check; exit code 1 if any failed.
#   .\dev\mp_test.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0
$script:evalId = 100

function C([string]$code) { $r = & $lua -Code $code; return ($r | ConvertFrom-Json).result }

# Lua on the server; its answer as text.
function S([string]$code, [int]$seconds = 25) {
    $script:evalId++
    $id = $script:evalId
    [void](C "MELensDevResult = nil; sendClientCommand(getPlayer(), 'MELensDev', 'eval', { id = $id, code = [==[$code]==] }); return 1")
    for ($i = 0; $i -lt $seconds * 2; $i++) {
        Start-Sleep -Milliseconds 500
        $r = C 'return MELensDevResult and (tostring(MELensDevResult.id) .. "|" .. tostring(MELensDevResult.text)) or "none"'
        if ($r -like "$id|*") { return $r.Substring("$id|".Length) }
    }
    return 'TIMEOUT'
}

function Check([string]$name, [bool]$ok, $detail = '') {
    if ($ok) { Write-Host "PASS  $name" } else { Write-Host "FAIL  $name  $detail"; $script:failed++ }
}

function Wait-Idle([int]$seconds = 60) {
    for ($i = 0; $i -lt $seconds / 0.7; $i++) {
        Start-Sleep -Milliseconds 700
        $s = C 'local p = getPlayer(); return tostring(MELens.pathing(p)) .. "," .. tostring(ISTimedActionQueue.isPlayerDoingAction(p)) .. "," .. #ISTimedActionQueue.getTimedActionQueue(p).queue'
        if ($s -match 'false,false,0') { Start-Sleep -Milliseconds 1200; return }
    }
}

# A moment for the server's answer to reach the client (part data goes out when the action is done).
function Settle { Start-Sleep -Seconds 2 }

# an item for the connected player, given by the server (so that the server knows it): returns once the client has it
function Give([string]$type, [string]$short) {
    [void](S ("local p = getOnlinePlayers():get(0); local it = p:getInventory():AddItem('$type'); sendAddItemToContainer(p:getInventory(), it); return it:getID()"))
    for ($i = 0; $i -lt 30; $i++) {
        if ((C "return tostring(getPlayer():getInventory():getFirstTypeRecurse('$short') ~= nil)") -eq 'true') { return }
        Start-Sleep -Milliseconds 500
    }
}

# --- connected
$who = C 'local p = getPlayer(); return p:getUsername() .. " isClient=" .. tostring(isClient())'
Check 'the client is connected to a server' ($who -match 'isClient=true') $who
$srv = S 'return "isServer=" .. tostring(isServer()) .. " loose=" .. tostring(MELens ~= nil and MELens.Loose ~= nil) .. " home=" .. tostring(MELens ~= nil and MELens.Home ~= nil) .. " propane=" .. tostring(MELens ~= nil and MELens.Utilities ~= nil and MELens.Utilities.PROPANE_CAPACITY)'
Check 'the server runs ME: LENS 2.0 (loose items, home, propane)' ($srv -match 'isServer=true loose=true home=true propane=2') $srv

# (what earlier runs left in the test character's inventory goes, on the server: a Grab needs weight room, and the
# propane check takes the first tank it finds)
[void](S "local p = getOnlinePlayers():get(0); local inv = p:getInventory(); local items = inv:getItems(); local doomed = {}; for i = 0, items:size() - 1 do local it = items:get(i); if not p:isEquippedClothing(it) and not p:isEquipped(it) then doomed[#doomed + 1] = it end end; for _, it in ipairs(doomed) do inv:Remove(it); sendRemoveItemFromContainer(inv, it) end; return #doomed")

# --- a camper next to us, and in
[void](C 'MELensTest = MELensTest or {}; local v = MELensTest.vehicle; if v and getPlayer():getVehicle() ~= v then MELensTest.vehicle = nil end; return 1')
$existing = C 'local p = getPlayer(); local v = p:getVehicle(); return v and v:getId() or "none"'
if ($existing -eq 'none') {
    $pos = C 'local p = getPlayer(); return math.floor(p:getX()) .. "," .. math.floor(p:getY())'
    $x, $y = $pos -split ','
    $spawnX = [int]$x - 9
    $spawnY = [int]$y
    $vid = & (Join-Path $PSScriptRoot 'mp_spawn.ps1') -Name 'Base.Trailer54FlyingCloud22' -X $spawnX -Y $spawnY
    Check 'a camper was spawned by the server and the client sees it' ($vid -ne 'none') $vid
    [void](C "MELensTest = MELensTest or {}; MELensTest.vehicle = getVehicleById($vid); return 1")
    & (Join-Path $PSScriptRoot 'wait_still.ps1')
    [void](& $lua -File (Join-Path $root 'dev\lua\walkin.lua'))
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 2
        $state = C 'local p = getPlayer(); local v = p:getVehicle(); return (v and ("seat " .. v:getSeat(p)) or "outside") .. " standing=" .. tostring(MELens.isStanding(p))'
        if ($state -match 'standing=true') { break }
    }
} else {
    $vid = $existing
}
$state = C 'local p = getPlayer(); local v = p:getVehicle(); return (v and v:getScript():getFullName() or "outside") .. " standing=" .. tostring(MELens.isStanding(p))'
Check 'walk into the camper on a server' ($state -match 'Trailer54FlyingCloud22 standing=true') $state
$vid = C 'return tostring(getPlayer():getVehicle():getId())'
$seen = S 'local p = getOnlinePlayers():get(0); local v = p:getVehicle(); return v and ("vehicle " .. v:getId() .. " seat " .. v:getSeat(p)) or "none"'
Check 'the server has the character in the camper (a standing seat is accepted)' ($seen -match "vehicle $vid seat") $seen

$count = 'local v = getVehicleById(VID); local n = 0; for _ in pairs(MELens.Loose.positions(v, false) or {}) do n = n + 1 end; local f = MELens.Loose.floorContainer(v); return n .. "/" .. (f and f:getItems():size() or -1)'
function Both([string]$code) { return @((S $code.Replace('VID', $vid)), (C $code.Replace('VID', $vid))) }

[void](S ('local v = getVehicleById(VID); local L = MELens.Loose; local f = L.floorContainer(v); local gone = {}; for i = 0, f:getItems():size() - 1 do gone[#gone + 1] = f:getItems():get(i) end; for _, it in ipairs(gone) do f:Remove(it); sendRemoveItemFromContainer(f, it) end; L.floorPart(v):getModData().loose = nil; v:transmitPartModData(L.floorPart(v)); return "cleared"').Replace('VID', $vid))
Settle

# --- place, drop, move, grab
Give 'Base.Pot' 'Pot'
Give 'Base.Hammer' 'Hammer'
Give 'Base.Spiffo' 'Spiffo'
[void](& (Join-Path $PSScriptRoot 'loose.ps1') place 'Pot|0.0,0.145,2.4,0,1')
Wait-Idle; Settle
$n = Both $count
Check 'a pot placed on the bed: server and client agree (positions/items)' (($n[0] -eq '1/1') -and ($n[1] -eq '1/1')) ($n -join ' | ')
$entry = S ('local v = getVehicleById(VID); for k, e in pairs(MELens.Loose.positions(v, false)) do return e.t .. " s=" .. e.s .. " y=" .. string.format("%.2f", e.y) end').Replace('VID', $vid)
Check 'the server keeps its type, surface and height' ($entry -match 'Base\.Pot s=1 y=0\.1') $entry

[void](& (Join-Path $PSScriptRoot 'loose.ps1') drop 'Hammer')
Wait-Idle; Settle
$n = Both $count
Check 'a dropped hammer lies on the floor on both sides' (($n[0] -eq '2/2') -and ($n[1] -eq '2/2')) ($n -join ' | ')

# move the pot (an item already lying in the Floor) onto the floor beside us
[void](C @'
local p = getPlayer(); local v = p:getVehicle(); local L = MELens.Loose
local floor = L.floorContainer(v)
local pot = floor:getFirstType("Pot")
if not pot then return "no pot on the client" end
local x, z = MELens.Parts.characterAt(v, p)
local profile = MELens.profileFor(v)
local px, pz = L.dropSpot(v, profile, x + 0.3, z, pot:getID())
ISTimedActionQueue.add(MELensPlaceLoose:new(p, v, pot, px, profile.floorY, pz, 30, 0))
return "queued"
'@)
Wait-Idle; Settle
$moved = Both 'local v = getVehicleById(VID); for k, e in pairs(MELens.Loose.positions(v, false)) do if e.t == "Base.Pot" then return "s=" .. e.s .. " r=" .. e.r end end return "no pot"'
Check 'moving what lies there: on the floor, turned 30 degrees, server and client agree' (($moved[0] -eq 's=0 r=30') -and ($moved[1] -eq 's=0 r=30')) ($moved -join ' | ')

# turn an item the server put in the Floor without a place (an orphan)
[void](S 'local v = getVehicleById(VID); local f = MELens.Loose.floorContainer(v); local it = instanceItem("Base.Spiffo"); f:AddItem(it); sendAddItemToContainer(f, it); return it:getID()'.Replace('VID', $vid))
Settle
$orphan = C 'local v = getPlayer():getVehicle(); local f = MELens.Loose.floorContainer(v); local it = f:getFirstType("Spiffo"); return it and it:getID() or "none"'
[void](C "local p = getPlayer(); ISTimedActionQueue.add(MELensTurnLoose:new(p, p:getVehicle(), $orphan, 90)); return 1")
Wait-Idle; Settle
$turned = Both ('local v = getVehicleById(VID); local e = MELens.Loose.entry(v, {0}); return e and ("r=" .. e.r .. " s=" .. e.s) or "no record"' -f $orphan)
Check 'Turn works on an item that had no place' (($turned[0] -eq 'r=90 s=0') -and ($turned[1] -eq 'r=90 s=0')) ($turned -join ' | ')

# grab the pot again (the menu at its place)
$potAt = C 'local v = getPlayer():getVehicle(); for k, e in pairs(MELens.Loose.positions(v, false)) do if e.t == "Base.Pot" then return string.format("%.3f,%.3f,%.3f", e.x, e.y + 0.15, e.z) end end return "none"'
[void](& (Join-Path $PSScriptRoot 'loose.ps1') menu "$potAt|Grab")
Wait-Idle; Settle
$have = C 'return tostring(getPlayer():getInventory():getFirstTypeRecurse("Pot") ~= nil)'
$n = Both $count
Check 'grabbing the pot: in the inventory, gone from the floor on both sides' (($have -eq 'true') -and ($n[0] -eq '2/2') -and ($n[1] -eq '2/2')) "$have | $($n -join ' | ')"

# --- name and paint (the strip has no can, brush or colour at all)
[void](C "local p = getPlayer(); ISTimedActionQueue.add(MELensRename:new(p, p:getVehicle(), 'MP Rig')); return 1")
Wait-Idle; Settle
$names = Both 'return MELens.Home.name(getVehicleById(VID))'
Check 'rename reaches the server and comes back' (($names[0] -eq 'MP Rig') -and ($names[1] -eq 'MP Rig')) ($names -join ' | ')
Give 'Base.PaintGreen' 'PaintGreen'
Give 'Base.Paintbrush' 'Paintbrush'
[void](C @'
local p = getPlayer(); local inv = p:getInventory()
local can, brush = inv:getFirstTypeRecurse("PaintGreen"), inv:getFirstTypeRecurse("Paintbrush")
ISTimedActionQueue.add(MELensPaintWalls:new(p, p:getVehicle(), can, brush, 0.41, 0.80, 0.41))
return 1
'@)
Wait-Idle 120; Settle
$paint = Both 'local r = MELens.Home.paint(getVehicleById(VID)); return tostring(r)'
Check 'paint reaches the server and comes back' (($paint[0] -eq '0.41') -and ($paint[1] -eq '0.41')) ($paint -join ' | ')
[void](C "local p = getPlayer(); ISTimedActionQueue.add(MELensPaintWalls:new(p, p:getVehicle(), nil, nil, nil, nil, nil)); return 1")
Wait-Idle 60; Settle
$paint = Both 'local r = MELens.Home.paint(getVehicleById(VID)); return tostring(r)'
Check 'stripping the paint works with no arguments' (($paint[0] -eq 'nil') -and ($paint[1] -eq 'nil')) ($paint -join ' | ')

# --- propane
[void](S 'MELens.Utilities.setPropane(getVehicleById(VID), 0.1, true); return 1'.Replace('VID', $vid))
Settle
$level = C 'return string.format("%.2f", MELens.Utilities.propaneLevel(getPlayer():getVehicle()))'
Check 'the propane level reaches the client' ($level -eq '0.10') $level
Give 'Base.PropaneTank' 'PropaneTank'
[void](C "local p = getPlayer(); local t = p:getInventory():getFirstTypeRecurse('PropaneTank'); ISTimedActionQueue.add(MELensInsertPropane:new(p, p:getVehicle(), t)); return 1")
Wait-Idle; Settle
$level = Both 'return string.format("%.2f", MELens.Utilities.propaneLevel(getVehicleById(VID)))'
Check 'a propane tank put in: 1.10 tanks on both sides' (($level[0] -eq '1.10') -and ($level[1] -eq '1.10')) ($level -join ' | ')
$tank = C 'local t = getPlayer():getInventory():getFirstTypeRecurse("PropaneTank"); return t and string.format("%.2f", t:getCurrentUsesFloat()) or "none"'
Check 'and the tank is empty' ($tank -eq '0.00') $tank

# --- things fall in a crash
Give 'Base.Hammer' 'Hammer'
[void](& (Join-Path $PSScriptRoot 'loose.ps1') place 'Hammer|0.0,0.145,2.4,0,1')
Wait-Idle; Settle
$up = Both 'local v = getVehicleById(VID); return tostring(MELens.Loose.hasRaised(v))'
Check 'a hammer lies up on the bed' (($up[0] -eq 'true') -and ($up[1] -eq 'true')) ($up -join ' | ')
[void](S 'return tostring(MELens.Loose.tumble(getVehicleById(VID)))'.Replace('VID', $vid))
Settle
$down = Both 'local v = getVehicleById(VID); return tostring(MELens.Loose.hasRaised(v)) .. " tumbles=" .. tostring(MELens.Loose.floorPart(v):getModData().tumbles)'
Check 'a crash puts it on the floor on both sides and the client learns of it' (($down[0] -eq 'false tumbles=1') -and ($down[1] -eq 'false tumbles=1')) ($down -join ' | ')

# --- errors in the consoles
$clientErrors = Select-String -LiteralPath (Join-Path $root 'build\rv\testhome\Zomboid\console.txt') -CaseSensitive -Pattern 'MELens[A-Za-z_]*\.lua:\d+\)|\[ME_LENS\].*(failed|not shown|not drawn)' | Select-Object -First 4
Check 'no mod errors in the client console' ($null -eq $clientErrors) (($clientErrors | ForEach-Object { $_.Line }) -join '; ')
$serverLog = Join-Path $root 'build\rv\mphome\server\Zomboid\server-console.txt'
$serverErrors = Select-String -LiteralPath $serverLog -CaseSensitive -Pattern 'MELens[A-Za-z_]*\.lua:\d+\)' | Select-Object -First 4
Check 'no mod errors in the server console' ($null -eq $serverErrors) (($serverErrors | ForEach-Object { $_.Line }) -join '; ')

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

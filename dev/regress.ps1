# Developer helper: a regression run in the test game (scripts\testgame.ps1 / dev\restart.ps1 first). It spawns a
# Flying Cloud 22, walks in and checks, one after the other, what the mod has to keep doing: entering, resting on a
# bed, the generator, picking up and placing furniture, placing / dropping / grabbing loose items, the dashboard's
# name and paint, leaving. Prints PASS or FAIL for each and exits 1 if anything failed.
#   .\dev\regress.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0

function Lua([string]$code) { $r = & $lua -Code $code; return ($r | ConvertFrom-Json) }
function Value([string]$code) { return (Lua $code).result }
function Wait-Idle([int]$seconds = 60) {
    for ($i = 0; $i -lt $seconds / 0.7; $i++) {
        Start-Sleep -Milliseconds 700
        $s = Value 'local p = getPlayer(); return tostring(MELens.pathing(p)) .. "," .. tostring(ISTimedActionQueue.isPlayerDoingAction(p)) .. "," .. #ISTimedActionQueue.getTimedActionQueue(p).queue'
        if ($s -match 'false,false,0') { return }
    }
}
function Check([string]$name, [bool]$ok, $detail = '') {
    if ($ok) { Write-Host "PASS  $name" } else { Write-Host "FAIL  $name  $detail"; $script:failed++ }
}

# a clean start: the test character carries what earlier test runs left
# (and what its own runs leave: tools, cans of paint and brushes, furniture, plush toys, tanks; they weigh down the character,
# and a Grab needs room in the inventory)
[void](Lua 'local p = getPlayer(); p:setGodMod(true); local inv = p:getInventory(); local items = inv:getItems(); local rm = {}; local gone = { ["Base.CarKey"] = true, ["Base.Pot"] = true, ["Base.Hammer"] = true, ["Base.Spiffo"] = true, ["Base.PaintGreen"] = true, ["Base.PaintRed"] = true, ["Base.Paintbrush"] = true, ["Base.PropaneTank"] = true, ["Base.WaterBottle"] = true }; for i = 0, items:size() - 1 do local it = items:get(i); if gone[it:getFullType()] or string.find(it:getType(), "^MELensRV_") then rm[#rm + 1] = it end end; for _, it in ipairs(rm) do inv:Remove(it) end; return #rm')

# --- entering (vehicles earlier runs left would block the spawn; a spawn can need a second try to settle)
[void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))
for ($try = 1; $try -le 3; $try++) {
    & (Join-Path $PSScriptRoot 'enter_vehicle.ps1') -Name 'Base.Trailer54FlyingCloud22' | Out-Null
    if ((Value 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true') { break }
}
$state = Value 'local p = getPlayer(); local v = p:getVehicle(); return (v and v:getScript():getFullName() or "outside") .. " standing=" .. tostring(MELens.isStanding(p))'
Check 'walk into the camper' ($state -match 'Trailer54FlyingCloud22 standing=true') $state

# --- loose items: place, persist in the data, grab
[void](Lua 'MELens.LooseUI.testMouse = nil; return 1')
[void](Lua 'local p = getPlayer(); for _, t in ipairs({ "Base.Pot", "Base.Hammer", "Base.Spiffo" }) do p:getInventory():AddItem(t) end; return 1')
[void](& (Join-Path $PSScriptRoot 'loose.ps1') clear)
[void](& (Join-Path $PSScriptRoot 'loose.ps1') place 'Pot|0.0,0.145,2.4,0,1')
Wait-Idle
[void](& (Join-Path $PSScriptRoot 'loose.ps1') place 'Spiffo|0.594,0.457,-0.555,0,3')
Wait-Idle
$count = Value 'local v = getPlayer():getVehicle(); local n = 0; for _ in pairs(MELens.Loose.positions(v, false) or {}) do n = n + 1 end; return n'
Check 'two items placed (bed, table)' ($count -eq 2) "positions=$count"
for ($i = 0; $i -lt 10; $i++) {            # the view hands them on a few times a second, once their models have loaded
    $java = Value 'return MELensRV.looseStatus()'
    if ($java -match 'entries=2') { break }
    Start-Sleep -Milliseconds 700
}
Check 'both are drawn' ($java -match 'entries=2') $java
$block = Value 'local v = getPlayer():getVehicle(); local part = MELens.Parts.spotPart(v, 3); return tostring(MELens.Parts.pickUpTest(v, part, getPlayer()))'
Check 'the table cannot be picked up with the plush on it' ($block -eq 'false') $block
[void](& (Join-Path $PSScriptRoot 'loose.ps1') drop 'Hammer')
Wait-Idle
$count = Value 'local v = getPlayer():getVehicle(); local n = 0; for _ in pairs(MELens.Loose.positions(v, false) or {}) do n = n + 1 end; return n'
Check 'a dropped hammer lies on the floor' ($count -eq 3) "positions=$count"
# grab the pot by the menu at its place
[void](& (Join-Path $PSScriptRoot 'loose.ps1') menu '0.0,0.3,2.4|Grab')
Wait-Idle
$count = Value 'local v = getPlayer():getVehicle(); local n = 0; for _ in pairs(MELens.Loose.positions(v, false) or {}) do n = n + 1 end; return n'
Check 'grabbing the pot takes it off the floor' ($count -eq 2) "positions=$count"
$have = Value 'return tostring(getPlayer():getInventory():getFirstTypeRecurse("Pot") ~= nil)'
Check 'and into the inventory' ($have -eq 'true') $have

# --- home: name and paint
$set = Value @'
local p = getPlayer(); local v = p:getVehicle(); local inv = p:getInventory()
local can, brush = inv:AddItem("Base.PaintGreen"), inv:AddItem("Base.Paintbrush")
ISTimedActionQueue.add(MELensRename:new(p, v, "Regression Rig"))
ISTimedActionQueue.add(MELensPaintWalls:new(p, v, can, brush, 0.41, 0.80, 0.41))
return "queued"
'@
Wait-Idle 120
$painted = Value 'local v = getPlayer():getVehicle(); local r, g, b = MELens.Home.paint(v); return MELens.Home.name(v) .. "|" .. tostring(r)'
Check 'rename and paint' ($painted -eq 'Regression Rig|0.41') $painted

# --- the generator
$gen = Value @'
local v = getPlayer():getVehicle(); local U = MELens.Utilities
local state = U.generatorState(v)
state.part:getModData().fuel = 5
U.setSwitch(v, "generator", true)
return tostring(U.hasPower(v))
'@
Check 'the generator powers the camper' ($gen -eq 'true') $gen
[void](Value 'MELens.Utilities.setSwitch(getPlayer():getVehicle(), "generator", false) return 1')

# --- furniture: pick up the heater and put it back
$pick = Value @'
local p = getPlayer(); local v = p:getVehicle(); local P = MELens.Parts
local part = P.spotPart(v, 8)
local had = P.pieceAt(part)
ISTimedActionQueue.add(MELensPickUpFurniture:new(p, v, part))
return tostring(had)
'@
Wait-Idle
$gone = Value 'local v = getPlayer():getVehicle(); local P = MELens.Parts; return tostring(P.pieceAt(P.spotPart(v, 8)))'
Check 'pick up the heater' (($pick -eq 'heater') -and ($gone -eq 'nil')) "$pick -> $gone"
[void](Value @'
local p = getPlayer(); local v = p:getVehicle(); local P = MELens.Parts
local item = p:getInventory():getFirstTypeRecurse("MELensRV_Heater")
if item then ISTimedActionQueue.add(MELensPlaceFurniture:new(p, v, P.spotPart(v, 8), item)) end
return 1
'@)
Wait-Idle
$back = Value 'local v = getPlayer():getVehicle(); local P = MELens.Parts; return tostring(P.pieceAt(P.spotPart(v, 8)))'
Check 'place it again' ($back -eq 'heater') $back

# --- resting on a bed and getting up
[void](Value @'
local p = getPlayer(); local v = p:getVehicle()
local profile = MELens.profileFor(v)
local seatId = profile.spots[1].seats[1]
local index, sx, sz = MELens.Parts.seatPoint(v, profile, seatId)
MELens.useSeat(p, seatId, sx, sz, false)
return 1
'@)
Wait-Idle 40
$seated = Value 'local p = getPlayer(); local v = p:getVehicle(); return tostring(MELens.isStanding(p))'
Check 'rest on the bed (not standing)' ($seated -eq 'false') $seated
[void](Value 'MELens.standUp(getPlayer()) return 1')
Wait-Idle 40
$stand = Value 'return tostring(MELens.isStanding(getPlayer()))'
Check 'and stand up again' ($stand -eq 'true') $stand

# --- leaving
[void](Value 'MELens.leave(getPlayer()) return 1')
for ($i = 0; $i -lt 30; $i++) { Start-Sleep -Seconds 2; if ((Value 'return getPlayer():getVehicle() and "in" or "out"') -eq 'out') { break } }
Check 'leave the camper' ((Value 'return getPlayer():getVehicle() and "in" or "out"') -eq 'out')

# a Lua error of ours is logged with the frames of its stack trace (MELens_Loose.lua:503), the mod's own notes with [ME_LENS]
$errors = Select-String -LiteralPath (Join-Path $root 'build\rv\testhome\Zomboid\console.txt') -CaseSensitive -Pattern 'MELens[A-Za-z_]*\.lua:\d+\)|\[ME_LENS\].*(failed|not shown|not drawn)' |
    Select-Object -First 5
Check 'no mod errors in the console' ($null -eq $errors) (($errors | ForEach-Object { $_.Line }) -join '; ')

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

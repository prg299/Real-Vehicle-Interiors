# Developer helper: does what is set down in a camper survive a save and a reload? It spawns a Flying Cloud 22, walks
# in, puts a pot on a bed, a plush toy on the table and a hammer on the floor, names and paints the vehicle, writes down
# where everything lies, saves and quits through the game (dev\restart.ps1 -NoBuild: the build stays as it is), loads the
# same world again and compares. The standing places of the vehicle must hold their marker item again, and the items must
# be drawn once you stand inside. Run it as a background task with its output in a file: the game it starts keeps the
# pipe open, so a pipe into another command never ends.
#   .\dev\persist_test.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts/lua.ps1'
$failed = 0

function Value([string]$code) { $r = & $lua -Code $code; return ($r | ConvertFrom-Json).result }
function Wait-Idle([int]$seconds = 60) {
    for ($i = 0; $i -lt $seconds / 0.7; $i++) {
        Start-Sleep -Milliseconds 700
        $s = Value 'local p = getPlayer(); return tostring(MELens.pathing(p)) .. "," .. tostring(ISTimedActionQueue.isPlayerDoingAction(p)) .. "," .. #ISTimedActionQueue.getTimedActionQueue(p).queue'
        if ($s -match 'false,false,0') { Start-Sleep -Milliseconds 800; return }
    }
}
function Check([string]$name, [bool]$ok, $detail = '') {
    if ($ok) { Write-Host "PASS  $name" } else { Write-Host "FAIL  $name  $detail"; $script:failed++ }
}

# what lies in the nearest Flying Cloud 22, where, its name and paint, and how many standing places hold their marker item
$snapshot = @'
local p = getPlayer(); local best, bestD
local it = getCell():getVehicles():iterator()
while it:hasNext() do
    local v = it:next()
    if v:getScript():getFullName() == "Base.Trailer54FlyingCloud22" then
        local d = p:DistToSquared(v:getX(), v:getY())
        if not bestD or d < bestD then best, bestD = v, d end
    end
end
if not best then return "no camper" end
local profile = MELens.profileFor(best)
local out = {}
for _, e in ipairs(MELens.Loose.list(best, profile)) do
    out[#out + 1] = string.format("%s@%.3f,%.3f,%.3f r%.0f s%.0f", e.t, e.x, e.y, e.z, e.r, e.s)
end
table.sort(out)
local seats = 0
for i = 0, best:getPartCount() - 1 do
    local part = best:getPartByIndex(i)
    if string.find(part:getId(), "^SeatMELensCabin") and part:getInventoryItem() then seats = seats + 1 end
end
return table.concat(out, "; ") .. " | name=" .. tostring(MELens.Home.name(best)) .. " paint=" .. tostring((MELens.Home.paint(best))) .. " seatItems=" .. seats
'@

# --- before: a camper with things in it
[void](Value 'local p = getPlayer(); p:setGodMod(true); local inv = p:getInventory(); local items = inv:getItems(); local rm = {}; local gone = { ["Base.Pot"] = true, ["Base.Hammer"] = true, ["Base.Spiffo"] = true, ["Base.PaintGreen"] = true, ["Base.Paintbrush"] = true }; for i = 0, items:size() - 1 do local it = items:get(i); if gone[it:getFullType()] then rm[#rm + 1] = it end end; for _, it in ipairs(rm) do inv:Remove(it) end; return #rm')
[void](& $lua -File (Join-Path $root 'dev/lua/remove_others.lua'))
for ($try = 1; $try -le 3; $try++) {
    & (Join-Path $PSScriptRoot 'enter_vehicle.ps1') -Name 'Base.Trailer54FlyingCloud22' | Out-Null
    if ((Value 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true') { break }
}
Check 'walk into the camper' ((Value 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true')
[void](Value 'MELens.LooseUI.testMouse = nil; return 1')
[void](Value 'local p = getPlayer(); for _, t in ipairs({ "Base.Pot", "Base.Hammer", "Base.Spiffo" }) do p:getInventory():AddItem(t) end; return 1')
[void](& (Join-Path $PSScriptRoot 'loose.ps1') clear)
[void](& (Join-Path $PSScriptRoot 'loose.ps1') place 'Pot|0.0,0.145,2.4,0,1')
Wait-Idle
[void](& (Join-Path $PSScriptRoot 'loose.ps1') place 'Spiffo|0.594,0.457,-0.555,0,3')
Wait-Idle
[void](& (Join-Path $PSScriptRoot 'loose.ps1') drop 'Hammer')
Wait-Idle
[void](Value @'
local p = getPlayer(); local v = p:getVehicle(); local inv = p:getInventory()
local can, brush = inv:AddItem("Base.PaintGreen"), inv:AddItem("Base.Paintbrush")
ISTimedActionQueue.add(MELensRename:new(p, v, "Persist Rig"))
ISTimedActionQueue.add(MELensPaintWalls:new(p, v, can, brush, 0.41, 0.80, 0.41))
return "queued"
'@)
Wait-Idle 120
$before = Value $snapshot
Write-Host "before: $before"
Check 'three items, the name, the paint and the standing places before the save' (($before -match '^(\S+@\S+ r\d+ s-?\d+; ){2}\S+@\S+ r\d+ s-?\d+ \| name=Persist Rig paint=0\.41 seatItems=[1-9]')) $before

# --- save, quit, load the same world again
$restart = & (Join-Path $PSScriptRoot 'restart.ps1') -NoBuild 2>&1 | Out-String
Write-Host ($restart.Trim() -split "`n" | Select-Object -Last 2)
Start-Sleep -Seconds 5

# --- after
$after = Value $snapshot
Write-Host "after:  $after"
Check 'the same items in the same places, the same name and paint, the standing places hold their item' ($after -eq $before) "before: $before | after: $after"
# once inside, the items are drawn again
[void](Value 'local p = getPlayer(); local best, bestD; local it = getCell():getVehicles():iterator(); while it:hasNext() do local v = it:next(); if v:getScript():getFullName() == "Base.Trailer54FlyingCloud22" then local d = p:DistToSquared(v:getX(), v:getY()); if not bestD or d < bestD then best, bestD = v, d end end end; MELensTest = MELensTest or {}; MELensTest.vehicle = best; return best and best:getId() or "none"')
if ((Value 'return tostring(MELens.isStanding(getPlayer()))') -ne 'true') {
    if ((Value 'return tostring(getPlayer():getVehicle() ~= nil)') -eq 'true') { [void](Value 'MELens.leave(getPlayer()); return 1'); Start-Sleep -Seconds 6 }
    [void](& $lua -File (Join-Path $root 'dev/lua/walkin.lua'))
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        if ((Value 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true') { break }
    }
}
$java = ''
for ($i = 0; $i -lt 15; $i++) {
    $java = Value 'return MELensRV.looseStatus()'
    if ($java -match 'entries=3') { break }
    Start-Sleep -Milliseconds 700
}
Check 'and they are drawn again once you stand inside' ($java -match 'entries=3') $java
$errors = Select-String -LiteralPath (Join-Path $root 'build/rv/testhome/Zomboid/console.txt') -CaseSensitive -Pattern 'MELens[A-Za-z_]*\.lua:\d+\)|\[ME_LENS\].*(failed|not shown|not drawn)' | Select-Object -First 3
Check 'no mod errors in the console after the reload' ($null -eq $errors) (($errors | ForEach-Object { $_.Line }) -join '; ')

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

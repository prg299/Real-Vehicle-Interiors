# Developer helper: a box truck's boxes on the local test server (2.0.2). The game sends a vehicle's part changes
# between the server and its players by the part's place in the vehicle's part list (and names the vehicle storage an
# item moves from or to the same way). Up to 2.0.2 the inside's shell part was declared only where ME: LENS' Java runs,
# so on a server without it (a hosted world, an ordinary dedicated server) every ME: LENS part after the shell sat one
# place earlier than on the players' games: a box taken off on the server vanished from another place for the players,
# and what they took out of a box or laid on the floor was looked for in the next part. Start the server without the
# Java agent (dev\mp_server.ps1 -NoJava, as players run it) and connect the test game (dev\mp_connect.ps1) first.
# It spawns an F700 box truck with the game's /addvehicle command, compares the vehicle's parts on both sides, walks
# in, empties boxes through the game's own transfer, picks them up through the right-click menu, lays an item on the
# floor, and checks after each step that the client and the server agree. Prints PASS or FAIL; exit code 1 if any failed.
#   .\dev\mp_boxes.ps1 [-At 10813,10140]   (where to stand first: the single-player tests' open street, grass to the west;
#                                          the truck is spawned on the grass, its back door free)
param([string]$At = '10813,10140')
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0
$script:evalId = 8100
$boxDriver = Get-Content -LiteralPath (Join-Path $root 'dev\lua\box_pick.lua') -Raw

function C([string]$code) { $r = & $lua -Code $code; return ($r | ConvertFrom-Json).result }
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
function Box([string]$mode) { return C ($boxDriver.Replace('local MODE = "MODE"', "local MODE = ""$mode""")) }
function Check([string]$name, [bool]$ok, $detail = '') {
    if ($ok) { Write-Host "PASS  $name" } else { Write-Host "FAIL  $name  $detail"; $script:failed++ }
}
function Wait-Idle([int]$seconds = 40) {
    for ($i = 0; $i -lt $seconds / 0.7; $i++) {
        Start-Sleep -Milliseconds 700
        $s = C 'local p = getPlayer(); return tostring(MELens.pathing(p)) .. "," .. tostring(ISTimedActionQueue.isPlayerDoingAction(p)) .. "," .. #ISTimedActionQueue.getTimedActionQueue(p).queue'
        if ($s -match 'false,false,0') { Start-Sleep -Milliseconds 1500; return }
    }
}
$consolePath = Join-Path $root 'build\rv\testhome\Zomboid\console.txt'
$consoleStart = (Get-Item -LiteralPath $consolePath).Length
$serverConsole = Join-Path $root 'build\rv\mphome\server\Zomboid\server-console.txt'
$serverStart = if (Test-Path -LiteralPath $serverConsole) { (Get-Item -LiteralPath $serverConsole).Length } else { 0 }
function New-Lines([string]$path, [long]$start, [string]$pattern) {
    if (-not (Test-Path -LiteralPath $path)) { return @() }
    $stream = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        [void]$stream.Seek([Math]::Min($start, $stream.Length), [IO.SeekOrigin]::Begin)
        $text = [IO.StreamReader]::new($stream).ReadToEnd()
    } finally { $stream.Dispose() }
    return @($text -split "`n" | Where-Object { $_ -cmatch $pattern } | Select-Object -First 3)
}

$who = C 'return getPlayer():getUsername() .. " isClient=" .. tostring(isClient())'
Check 'connected to the test server' ($who -match 'isClient=true') $who
$serverJava = S 'return tostring(MELensRV ~= nil)'
Write-Host "      (the server has ME: LENS' Java part: $serverJava; players' servers do not)"

# --- an F700 box truck beside us, spawned the way an admin does
if ((C 'return tostring(getPlayer():getVehicle() ~= nil)') -eq 'true') {
    [void](C 'local p = getPlayer(); if MELens.isStanding(p) then MELens.leave(p) else ISVehicleMenu.onExit(p) end; return 1')
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 1
        if ((C 'return tostring(getPlayer():getVehicle() == nil)') -eq 'true') { break }
    }
    Start-Sleep -Seconds 2
}
$findTrucks = @'
local p = getPlayer(); local it = getCell():getVehicles():iterator(); local ids = {}
while it:hasNext() do local v = it:next(); if v:getScript():getFullName() == "Base.87fordF700box" and p:DistToSquared(v:getX(), v:getY()) < 3600 then ids[#ids + 1] = tostring(v:getId()) end end
return table.concat(ids, ",")
'@
# (box trucks left by earlier runs go: this world is the test server's own)
[void](S "local it = getCell():getVehicles():iterator(); local doomed = {}; while it:hasNext() do local v = it:next(); if v:getScript():getFullName() == 'Base.87fordF700box' then doomed[#doomed + 1] = v end end; for _, v in ipairs(doomed) do v:permanentlyRemove() end; return #doomed")
$px, $py = $At -split ','
[void](C "SendCommandToServer('/teleportto $px,$py,0'); return 1")
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if ((C "local p = getPlayer(); return tostring(math.abs(p:getX() - $px) < 3 and math.abs(p:getY() - $py) < 3)") -eq 'true') { break }
}
Start-Sleep -Seconds 4
$before = @((C $findTrucks) -split ',' | Where-Object { $_ })
$vid = 'none'
foreach ($offset in @(@(-9, 0), @(-9, 8), @(-9, -8), @(-15, 0), @(-15, 8))) {
    [void](C ("SendCommandToServer('/addvehicle Base.87fordF700box {0},{1},0'); return 1" -f ([int]$px + $offset[0]), ([int]$py + $offset[1])))
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 2
        $now = @((C $findTrucks) -split ',' | Where-Object { $_ })
        $new = @($now | Where-Object { $before -notcontains $_ })
        if ($new.Count -gt 0) { $vid = $new[0]; break }
    }
    if ($vid -ne 'none') { break }
}
Check 'an F700 box truck beside the player' ($vid -ne 'none') $vid
if ($vid -eq 'none') { exit 1 }
# (/addvehicle leaves the doors as chance has them; the developer spawn unlocks them, so does this)
[void](S "local v = getVehicleById($vid); for i = 0, v:getPartCount() - 1 do local part = v:getPartByIndex(i); local door = part:getDoor(); if door and door:isLocked() then door:setLocked(false); v:transmitPartDoor(part) end end; return 1")
Start-Sleep -Seconds 3

# --- the same parts in the same places on both sides
$partsCode = "local v = getVehicleById($vid); local t = {}; for i = 0, v:getPartCount() - 1 do t[#t + 1] = v:getPartByIndex(i):getId() end; return table.concat(t, ',')"
$partsC = C $partsCode
$partsS = S $partsCode
$detail = ''
if ($partsC -ne $partsS) {
    $a = $partsC -split ','; $b = $partsS -split ','
    for ($i = 0; $i -lt [Math]::Max($a.Count, $b.Count); $i++) {
        if ($a[$i] -ne $b[$i]) { $detail = "first difference at part $i`: client $($a[$i]), server $($b[$i]) ($($a.Count) / $($b.Count) parts)"; break }
    }
}
Check 'the vehicle''s parts are in the same order on the client and on the server' ($partsC -eq $partsS) $detail

# --- inside (from right behind its back door: the brush round the spot can block a longer path)
[void](C "MELensTest = MELensTest or {}; MELensTest.vehicle = getVehicleById($vid); return 1")
$door = C "local v = getVehicleById($vid); local s = MELens.profileFor(v).standing; local o = v:getScript():getModel():getOffset(); local w = v:getWorldPos(o:x() + s.outside[1], 0, o:z() + s.outside[3] - 0.6, Vector3f.new()); return math.floor(w:x()) .. ',' .. math.floor(w:y())"
[void](C "SendCommandToServer('/teleportto $door,0'); return 1")
Start-Sleep -Seconds 4
& (Join-Path $PSScriptRoot 'wait_still.ps1')
[void](& $lua -File (Join-Path $root 'dev\lua\walkin.lua'))
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    if ((C 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true') { break }
}
$inside = (C 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true'
Check 'standing inside the box truck' $inside
if (-not $inside) { Write-Host 'cannot go on without getting in'; exit 1 }
Wait-Idle
# (the game on a server finds no part for a place to stand without ME: LENS' Java part and turns the walk-in down;
# MELens_Sync.lua seats the player on the first position they send)
$seen = S "local list = getOnlinePlayers(); for i = 0, list:size() - 1 do local pl = list:get(i); if pl:getUsername() == '$((C 'return getPlayer():getUsername()'))' then local v = pl:getVehicle(); return v and ('vehicle ' .. v:getId() .. ' seat ' .. v:getSeat(pl)) or 'outside' end end; return 'no player'"
$mine = C "local p = getPlayer(); return 'vehicle ' .. p:getVehicle():getId() .. ' seat ' .. p:getVehicle():getSeat(p)"
Check 'the server has the player standing in the truck too' ($seen -eq $mine) "server: $seen, client: $mine"

$layoutCode = "local v = getVehicleById($vid); local t = {}; for i = 1, 63 do local p = v:getPartById('MELensSpot' .. i); t[i] = (p and p:getInventoryItem()) and '1' or '0' end; return table.concat(t)"
function Contents([string]$side, [string]$part) {
    $code = "local v = getVehicleById($vid); local p = v:getPartById('$part'); local c = p and p:getItemContainer(); if not c then return 'no container' end; local t = {}; for i = 0, c:getItems():size() - 1 do t[#t + 1] = c:getItems():get(i):getID() end; table.sort(t); return table.concat(t, ',')"
    if ($side -eq 'server') { return S $code } else { return C $code }
}
$startC = C $layoutCode
Check 'the same boxes on both sides at the start' ($startC -eq (S $layoutCode)) $startC

$serverPlayer = "local pl; local list = getOnlinePlayers(); for i = 0, list:size() - 1 do if list:get(i):getUsername() == '$((C 'return getPlayer():getUsername()'))' then pl = list:get(i) end end"
# empties a box the way the loot window does (one transfer per item into the player's inventory), then picks it up
# through the right-click menu; checks both sides after each
function Take-Box([string]$label) {
    $index = Box 'which'
    if ($index -notmatch '^\d+$') { Check "$label`: a box to take" $false $index; return }
    $part = "MELensSpot$index"
    # (the game's /addvehicle repairs the vehicle, which fills every empty place with a new, empty box: give it
    # something to take out, from the server, as loot would be)
    if ((Contents 'server' $part) -eq '') {
        [void](S "local v = getVehicleById($vid); local c = v:getPartById('$part'):getItemContainer(); for _, t in ipairs({ 'Base.Hammer', 'Base.Apple' }) do local item = c:AddItem(t); if item then sendAddItemToContainer(c, item) end end; return c:getItems():size()")
        Start-Sleep -Seconds 2
    }
    $inBox = Contents 'client' $part
    Check "$label`: box $index holds the same on both sides" ($inBox -eq (Contents 'server' $part)) $inBox
    $moved = C "local p = getPlayer(); local v = getVehicleById($vid); local c = v:getPartById('$part'):getItemContainer(); local items = {}; for i = 0, c:getItems():size() - 1 do items[#items + 1] = c:getItems():get(i) end; for _, item in ipairs(items) do ISTimedActionQueue.add(ISInventoryTransferAction:new(p, item, c, p:getInventory())) end; return #items"
    Wait-Idle 60
    $leftS = Contents 'server' $part
    $leftC = Contents 'client' $part
    Check "$label`: the $moved item(s) are out of box $index on the server too" (($leftS -eq '') -and ($leftC -eq '')) "server [$leftS] client [$leftC]"
    if ($inBox) {
        $ids = $inBox -split ','
        $carried = S "$serverPlayer; if not pl then return 'no player' end; local n = 0; for _, id in ipairs({ $($ids -join ', ') }) do if pl:getInventory():containsID(id) then n = n + 1 end end; return n"
        Check "$label`: the server put them in the player's inventory" ($carried -eq "$($ids.Count)") "$carried of $($ids.Count)"
    }
    $before = C $layoutCode
    $picked = Box 'next'
    Wait-Idle 40
    $afterC = C $layoutCode
    $afterS = S $layoutCode
    $expected = $before.Substring(0, [int]$index - 1) + '0' + $before.Substring([int]$index)
    Check "$label`: $picked - only that box is gone, on the server and on the client" (($afterS -eq $expected) -and ($afterC -eq $expected)) "expected $expected | server $afterS | client $afterC"
}

$carriedBefore = [int]((Box 'count') -split ' ')[1]
Take-Box 'first box'
Take-Box 'second box'
Take-Box 'third box'
$carriedAfter = [int]((Box 'count') -split ' ')[1]
Check 'three boxes carried' (($carriedAfter - $carriedBefore) -eq 3) "$carriedBefore -> $carriedAfter"

# --- the floor: an item laid down through the Floor tab arrives in the floor's storage on the server
$floorItem = C "local p = getPlayer(); local items = p:getInventory():getItems(); for i = 0, items:size() - 1 do local it = items:get(i); if not it:isEquipped() and it:getType() ~= 'MELensRV_Box' and not instanceof(it, 'InventoryContainer') then return tostring(it:getID()) end end; return 'none'"
if ($floorItem -match '^\d+$') {
    [void](C "local p = getPlayer(); local v = getVehicleById($vid); local floor = v:getPartById('MELensFloor'):getItemContainer(); local item = p:getInventory():getItemWithID($floorItem); ISTimedActionQueue.add(ISInventoryTransferAction:new(p, item, p:getInventory(), floor)); return 1")
    Wait-Idle 30
    $onFloor = S "local v = getVehicleById($vid); local c = v:getPartById('MELensFloor'):getItemContainer(); return tostring(c:getItemWithID($floorItem) ~= nil)"
    Check 'an item laid on the floor is in the floor''s storage on the server' ($onFloor -eq 'true') $onFloor
} else {
    Check 'an item to lay on the floor' $false $floorItem
}

$errors = New-Lines $consolePath $consoleStart 'MELens[A-Za-z_]*\.lua:\d+\)|Lua fail'
Check 'no ME: LENS Lua errors on the client' ($errors.Count -eq 0) ($errors -join ' / ')
$serverErrors = New-Lines $serverConsole $serverStart 'has no container|invalid part index|MELens[A-Za-z_]*\.lua:\d+\)'
Check 'no wrong-storage or ME: LENS errors on the server' ($serverErrors.Count -eq 0) ($serverErrors -join ' / ')

if ($failed -gt 0) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

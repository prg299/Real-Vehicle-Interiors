# Developer helper for the multiplayer tests: spawns a vehicle near a point on the local test server, as an admin.
# With ZombieBuddy on the server (dev\mp_server.ps1) the developer endpoint's spawn helper does it; on a server without
# it (dev\mp_server.ps1 -NoJava, the server players run) the game's own /addvehicle command, tried at a few points
# round the asked one. Either way every door is unlocked on the server and the players are told (/addvehicle only
# unlocks the driver's door, and a walk-in stops at a locked door it has no key for). Prints the new vehicle's id,
# or "none".
#   .\dev\mp_spawn.ps1 -Name Base.Trailer54FlyingCloud22 -X 10628 -Y 9368
param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][int]$X, [Parameter(Mandatory)][int]$Y)
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$script:evalId = Get-Random -Minimum 20000 -Maximum 30000

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
$find = @"
local p = getPlayer(); local it = getCell():getVehicles():iterator(); local ids = {}
while it:hasNext() do local v = it:next(); if v:getScript():getFullName() == "$Name" and p:DistToSquared(v:getX(), v:getY()) < 6400 then ids[#ids + 1] = tostring(v:getId()) end end
return table.concat(ids, ",")
"@
$before = @((C $find) -split ',' | Where-Object { $_ })
function New-Id([int]$tries = 10) {
    for ($i = 0; $i -lt $tries; $i++) {
        Start-Sleep -Seconds 2
        $new = @(@((C $find) -split ',' | Where-Object { $_ }) | Where-Object { $before -notcontains $_ })
        if ($new.Count -gt 0) { return $new[0] }
    }
    return 'none'
}

$vid = 'none'
# (vehicles earlier runs left on the spot go first: the test server's world is disposable; the one you are in stays)
[void](S "local it = getCell():getVehicles():iterator(); local doomed = {}; while it:hasNext() do local v = it:next(); if math.abs(v:getX() - $X) < 15 and math.abs(v:getY() - $Y) < 15 and v:getDriver() == nil and (v:getMaxPassengers() == 0 or not v:getCharacter(0)) then local busy = false; for i = 0, v:getMaxPassengers() - 1 do if v:getCharacter(i) then busy = true end end; if not busy then doomed[#doomed + 1] = v end end end; for _, v in ipairs(doomed) do v:permanentlyRemove() end; return #doomed")
$before = @((C $find) -split ',' | Where-Object { $_ })
if ((S 'return tostring(MELensDevSpawn ~= nil)') -eq 'true') {
    [void](C "sendClientCommand(getPlayer(), 'MELensDev', 'spawn', { name = '$Name', x = $X, y = $Y }); return 1")
    $vid = New-Id
} else {
    # (a town has few places a long vehicle may stand; the open ground west of 10813,10140 has room, and the game's
    # own position check cannot be asked from Lua: it refuses every square for a vehicle made there)
    foreach ($offset in @(@(0, 0), @(0, 6), @(0, -6), @(-6, 0), @(-6, 6), @(6, 0), @(0, 12), @(0, -12))) {
        [void](C ("SendCommandToServer('/addvehicle {0} {1},{2},0'); return 1" -f $Name, ($X + $offset[0]), ($Y + $offset[1])))
        $vid = New-Id 3
        if ($vid -ne 'none') { break }
    }
}
if ($vid -ne 'none') {
    [void](S "local v = getVehicleById($vid); for i = 0, v:getPartCount() - 1 do local part = v:getPartByIndex(i); local door = part:getDoor(); if door and door:isLocked() then door:setLocked(false); v:transmitPartDoor(part) end end; return 1")
}
Write-Output $vid

# Developer helper: the seats inside a camper on the local test server (2.0.1). Start the server (dev\mp_server.ps1) and
# connect the test game (dev\mp_connect.ps1) first. It spawns a Flying Cloud 22 beside the player, walks in, and with E
# sits at the dinette, gets up, lies on a bed and gets up through the game's Exit, comparing the seat the client shows
# with the one the server holds after each step. Prints PASS or FAIL for each check; exit code 1 if any failed.
#   .\dev\mp_seats.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0
$script:evalId = 6900

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
function Check([string]$name, [bool]$ok, $detail = '') {
    if ($ok) { Write-Host "PASS  $name" } else { Write-Host "FAIL  $name  $detail"; $script:failed++ }
}
function Wait-Idle([int]$seconds = 40) {
    for ($i = 0; $i -lt $seconds / 0.7; $i++) {
        Start-Sleep -Milliseconds 700
        $s = C 'local p = getPlayer(); return tostring(MELens.pathing(p)) .. "," .. tostring(ISTimedActionQueue.isPlayerDoingAction(p)) .. "," .. #ISTimedActionQueue.getTimedActionQueue(p).queue'
        if ($s -match 'false,false,0') { Start-Sleep -Milliseconds 1200; return }
    }
}
# the seat's passenger id, or outside: on the client, and as the server holds it
$mine = 'local p = getPlayer(); local v = p:getVehicle(); if not v then return "outside" end; return v:getScript():getPassenger(v:getSeat(p)):getId()'
$theirs = 'local p = getOnlinePlayers():get(0); local v = p:getVehicle(); if not v then return "outside" end; local s = v:getSeat(p); if s < 0 then return "no seat" end; return v:getScript():getPassenger(s):getId()'
function Both { $a = C $mine; Start-Sleep -Seconds 2; $b = S $theirs; return @($a, $b) }
function Press-E { [void](C 'local p = getPlayer(); triggerEvent("OnUseVehicle", p, p:getVehicle(), false); return 1') }
function Stand-Near([string]$piece) {
    return C @"
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

$who = C 'return getPlayer():getUsername() .. " isClient=" .. tostring(isClient())'
Check 'connected to the test server' ($who -match 'isClient=true') $who

# --- a camper beside us, and in
if ((C 'return tostring(getPlayer():getVehicle() ~= nil)') -eq 'true') {
    [void](C 'local p = getPlayer(); if MELens.isStanding(p) then MELens.leave(p) else MELens.standUp(p) end; return 1')
    Start-Sleep -Seconds 6
    [void](C 'local p = getPlayer(); if p:getVehicle() then MELens.leave(p) end; return 1')
    Start-Sleep -Seconds 8
}
$pos = C 'local p = getPlayer(); return math.floor(p:getX()) .. "," .. math.floor(p:getY())'
$x, $y = $pos -split ','
$vid = & (Join-Path $PSScriptRoot 'mp_spawn.ps1') -Name 'Base.Trailer54FlyingCloud22' -X ([int]$x - 9) -Y ([int]$y)
Check 'a camper beside the player' ($vid -ne 'none') $vid
[void](C "MELensTest = MELensTest or {}; MELensTest.vehicle = getVehicleById($vid); return 1")
& (Join-Path $PSScriptRoot 'wait_still.ps1')
[void](& $lua -File (Join-Path $root 'dev\lua\walkin.lua'))
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    if ((C 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true') { break }
}
$b = Both
Check 'standing in the camper, on both sides' (($b[0] -like 'MELensCabin*') -and ($b[1] -like 'MELensCabin*')) ($b -join ' | ')
Wait-Idle

# --- E at the dinette, E again
$at = Stand-Near 'dinette'
Wait-Idle
Press-E
Wait-Idle
Start-Sleep -Seconds 2
$b = Both
Check 'E at the dinette: seated there on both sides' (($b[0] -match '^(FrontL|FrontR|RearL|RearR)$') -and ($b[1] -eq $b[0])) "$($b -join ' | ') (stood at $at)"
Press-E
Start-Sleep -Seconds 3
$b = Both
Check 'E on the bench: standing again on both sides' (($b[0] -like 'MELensCabin*') -and ($b[1] -like 'MELensCabin*')) ($b -join ' | ')
Wait-Idle

# --- E at a bed, the game's Exit
$at = Stand-Near 'bed'
Wait-Idle
Press-E
Wait-Idle
Start-Sleep -Seconds 2
$b = Both
Check 'E at a bed: lying there on both sides' (($b[0] -match '^(FrontB|SideB)$') -and ($b[1] -eq $b[0])) "$($b -join ' | ') (stood at $at)"
[void](C 'ISVehicleMenu.onExit(getPlayer()); return 1')
Start-Sleep -Seconds 3
$b = Both
Check 'the game''s Exit on the bed: standing inside on both sides, not outside' (($b[0] -like 'MELensCabin*') -and ($b[1] -like 'MELensCabin*')) ($b -join ' | ')

# --- errors
$errors = Select-String -LiteralPath (Join-Path $root 'build\rv\testhome\Zomboid\console.txt') -CaseSensitive -Pattern 'MELens[A-Za-z_]*\.lua:\d+\)|\[ME_LENS\].*(failed|not shown|not drawn)' | Select-Object -First 3
Check 'no mod errors in the client console' ($null -eq $errors) (($errors | ForEach-Object { $_.Line }) -join '; ')
$serverErrors = Select-String -LiteralPath (Join-Path $root 'build\rv\mphome\server\Zomboid\server-console.txt') -CaseSensitive -Pattern 'MELens[A-Za-z_]*\.lua:\d+\)' | Select-Object -First 3
Check 'no mod errors in the server console' ($null -eq $serverErrors) (($serverErrors | ForEach-Object { $_.Line }) -join '; ')

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

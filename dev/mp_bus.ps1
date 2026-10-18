# Developer helper: the school bus on the local test server (2.0.2). With 2.0.1 a player inside a B700 bus in
# multiplayer crashed every frame (the game's PassengerMap holds 16 seats; the bus had 15 of its own and 4 places to
# stand) and was disconnected; a hosted world with a player saved in the bus could no longer be joined. Start the
# server (dev\mp_server.ps1) and connect the test game (dev\mp_connect.ps1) first. It spawns a B700 school bus beside
# the player, checks its seat count on both sides, walks in, stands, sits in the driver's seat with E and gets out,
# and checks the game stays connected without a PassengerMap error. Prints PASS or FAIL; exit code 1 if any failed.
#   .\dev\mp_bus.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0
$script:evalId = 7900

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
$place = 'local p = getPlayer(); if not p then return "no player" end; local v = p:getVehicle(); if not v then return "outside" end; return v:getScript():getPassenger(v:getSeat(p)):getId() .. " of " .. v:getMaxPassengers()'
$consolePath = Join-Path $root 'build\rv\testhome\Zomboid\console.txt'
$consoleStart = (Get-Item -LiteralPath $consolePath).Length
function New-Errors {
    $stream = [IO.File]::Open($consolePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        [void]$stream.Seek([Math]::Min($consoleStart, $stream.Length), [IO.SeekOrigin]::Begin)
        $text = [IO.StreamReader]::new($stream).ReadToEnd()
    } finally { $stream.Dispose() }
    return @($text -split "`n" | Where-Object { $_ -cmatch 'PassengerMap|MELens[A-Za-z_]*\.lua:\d+\)|doDisconnect|\[ME_LENS\].*(failed|not shown|not drawn)' } | Select-Object -First 3)
}

$who = C 'return getPlayer():getUsername() .. " isClient=" .. tostring(isClient())'
Check 'connected to the test server' ($who -match 'isClient=true') $who

# --- a school bus beside us
if ((C 'return tostring(getPlayer():getVehicle() ~= nil)') -eq 'true') {
    [void](C 'local p = getPlayer(); if MELens.isStanding(p) then MELens.leave(p) else ISVehicleMenu.onExit(p) end; return 1')
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 1
        if ((C 'return tostring(getPlayer():getVehicle() == nil)') -eq 'true') { break }
    }
    Start-Sleep -Seconds 2
}
$pos = C 'local p = getPlayer(); return math.floor(p:getX()) .. "," .. math.floor(p:getY())'
$x, $y = $pos -split ','
$vid = & (Join-Path $PSScriptRoot 'mp_spawn.ps1') -Name 'Base.87fordB700school' -X ([int]$x - 10) -Y ([int]$y)
Check 'a school bus beside the player' ($vid -ne 'none') $vid
$seats = @((C "return getVehicleById($vid):getMaxPassengers()"), (S "return getVehicleById($vid):getMaxPassengers()"))
Check 'the bus has 16 seats at most, on the client and on the server (the game''s limit)' (([int]$seats[0] -le 16) -and ($seats[1] -eq "$($seats[0])")) ($seats -join ' | ')

# --- inside, standing: the frames that crashed
[void](C "MELensTest = MELensTest or {}; MELensTest.vehicle = getVehicleById($vid); return 1")
& (Join-Path $PSScriptRoot 'wait_still.ps1')
[void](& $lua -File (Join-Path $root 'dev\lua\walkin.lua'))
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    if ((C 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true') { break }
}
Start-Sleep -Seconds 6
$p = C $place
$errors = New-Errors
Check 'standing in the bus on a server: still connected, no PassengerMap error' (($p -like 'MELensCabin*') -and ($errors.Count -eq 0)) "$p $($errors -join '; ')"
Wait-Idle

# --- the driver's seat with E (the game checks the passengers' loaded chunks for a driver), then out
[void](C 'local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v); local x, z = MELens.driverStandPoint(profile); MELens.walkTo(p, x, z); return 1')
Wait-Idle
[void](C 'local p = getPlayer(); triggerEvent("OnUseVehicle", p, p:getVehicle(), false); return 1')
Wait-Idle
Start-Sleep -Seconds 6
$p = C $place
$errors = New-Errors
Check 'in the driver''s seat on a server: still connected, no PassengerMap error' (($p -like 'FrontLeft*') -and ($errors.Count -eq 0)) "$p $($errors -join '; ')"
[void](C 'local p = getPlayer(); triggerEvent("OnUseVehicle", p, p:getVehicle(), false); return 1')
Start-Sleep -Seconds 6
$p = C $place
Check 'E in the driver''s seat gets out of the bus' ($p -eq 'outside') $p

$errors = New-Errors
Check 'no PassengerMap, mod or disconnect errors in the client console during the run' ($errors.Count -eq 0) ($errors -join '; ')
$serverErrors = Select-String -LiteralPath (Join-Path $root 'build\rv\mphome\server\Zomboid\server-console.txt') -CaseSensitive -Pattern 'PassengerMap|MELens[A-Za-z_]*\.lua:\d+\)' | Select-Object -First 3
Check 'no PassengerMap or mod errors in the server console' ($null -eq $serverErrors) (($serverErrors | ForEach-Object { $_.Line }) -join '; ')

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

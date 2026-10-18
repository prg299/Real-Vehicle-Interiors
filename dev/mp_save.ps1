# Developer helper: does what is set down in a camper survive a restart of the server? Run it after dev\mp_late.ps1 (a
# camper with three items, a name and a paint on the test server, the first player connected): it records what the server
# holds, saves and quits the server through the admin commands, starts it again on the same world, starts the first game
# again, connects, and compares what the server and the player hold. Prints PASS or FAIL for each check; exit code 1 if
# any failed. The second game, if one runs, is closed first.
#   .\dev\mp_save.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0
$script:evalId = 3900

function A([string]$code) { $r = & $lua -Code $code -Port 18470; return ($r | ConvertFrom-Json).result }

# Lua on the server (asked through the first game, an admin); its answer as text.
function S([string]$code, [int]$seconds = 25) {
    $script:evalId++
    $id = $script:evalId
    [void](A "MELensDevResult = nil; sendClientCommand(getPlayer(), 'MELensDev', 'eval', { id = $id, code = [==[$code]==] }); return 1")
    for ($i = 0; $i -lt $seconds * 2; $i++) {
        Start-Sleep -Milliseconds 500
        $r = A 'return MELensDevResult and (tostring(MELensDevResult.id) .. "|" .. tostring(MELensDevResult.text)) or "none"'
        if ($r -like "$id|*") { return $r.Substring("$id|".Length) }
    }
    return 'TIMEOUT'
}

function Check([string]$name, [bool]$ok, $detail = '') {
    if ($ok) { Write-Host "PASS  $name" } else { Write-Host "FAIL  $name  $detail"; $script:failed++ }
}

# what a vehicle holds, in one line (the same as dev\mp_late.ps1)
$snapshot = @'
local v = getVehicleById(VID)
if not v then return "no vehicle" end
local out = {}
for _, e in pairs(MELens.Loose.positions(v, false) or {}) do
    out[#out + 1] = string.format("%s@%.3f,%.3f,%.3f r%.0f s%.0f", e.t, e.x, e.y, e.z, e.r, e.s)
end
table.sort(out)
local f = MELens.Loose.floorContainer(v)
return table.concat(out, "; ") .. " | items=" .. (f and f:getItems():size() or -1) .. " name=" .. tostring(MELens.Home.name(v)) .. " paint=" .. tostring((MELens.Home.paint(v)))
'@

# --- before
$vid = A @'
local p = getPlayer(); local v = p:getVehicle()
if v then return tostring(v:getId()) end
local it = getCell():getVehicles():iterator()
while it:hasNext() do local w = it:next(); if w:getScript():getFullName() == "Base.Trailer54FlyingCloud22" and p:DistToSquared(w:getX(), w:getY()) < 2500 then return tostring(w:getId()) end end
return "none"
'@
Check 'there is a camper to look at' ($vid -ne 'none') $vid
$truth = S $snapshot.Replace('VID', $vid)
Write-Host "      the server holds: $truth"
Check 'the server holds three items, a name and a paint' ($truth -match '^(\S+@\S+ r\d+ s-?\d+; ){2}\S+@\S+ r\d+ s-?\d+ \| items=3 name=Late Rig paint=0\.41$') $truth

# --- save and quit through the admin commands
& (Join-Path $PSScriptRoot 'second_client.ps1') -Stop | Out-Null
[void](A "SendCommandToServer('/save'); return 1")
Start-Sleep -Seconds 10
[void](A "SendCommandToServer('/quit'); return 1")
$pidFile = Join-Path $root 'build\rv\mphome\server\server.pid'
$serverPid = [int](Get-Content -LiteralPath $pidFile)
for ($i = 0; $i -lt 60; $i++) {
    if (-not (Get-Process -Id $serverPid -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Seconds 2
}
$exited = -not (Get-Process -Id $serverPid -ErrorAction SilentlyContinue)
Check 'the server saved and quit on the admin''s command' $exited "process $serverPid still runs"
if (-not $exited) { Write-Host 'Cannot tell whether the world was saved; stopping.'; exit 1 }
$log = Get-Content -LiteralPath (Join-Path $root 'build\rv\mphome\server\Zomboid\server-console.txt') -Tail 12
$tail = (($log | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join ' / ')
if ($tail.Length -gt 400) { $tail = $tail.Substring($tail.Length - 400) }
Write-Host ("      the server's last lines: $tail")

# --- again, on the same world
Remove-Item -LiteralPath $pidFile -ErrorAction SilentlyContinue
& (Join-Path $PSScriptRoot 'mp_server.ps1')
& (Join-Path $root 'scripts\testgame.ps1') -Mode Stop | Out-Null
# (the launcher refuses to start while the old process is still listed)
. (Join-Path $root 'scripts\common.ps1')
for ($i = 0; $i -lt 30; $i++) {
    if (@(Get-LensGameProcesses).Count -eq 0) { break }
    Start-Sleep -Seconds 1
}
& (Join-Path $root 'scripts\testgame.ps1') | Out-Null
$menu = $false
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 2
    try {
        if ((A 'return (MainScreen and MainScreen.instance and not getPlayer()) and "menu" or "loading"') -eq 'menu') { $menu = $true; break }
    } catch { }
}
if (-not $menu) { throw 'The first game did not reach its main menu.' }
Start-Sleep -Seconds 3
& (Join-Path $PSScriptRoot 'mp_connect.ps1')

# (the server loads the map round the player after the login: the camper is there a minute or two later)
$clock = [Diagnostics.Stopwatch]::StartNew()
$again = ''
for ($i = 0; $i -lt 60; $i++) {
    $again = S $snapshot.Replace('VID', $vid)
    if ($again -eq $truth) { break }
    Start-Sleep -Seconds 2
}
Check 'after the restart the server holds the same items, name and paint' ($again -eq $truth) "$again | $truth"
Write-Host ("      the server had the camper {0:N0} s after the connection" -f $clock.Elapsed.TotalSeconds)
$mine = ''
for ($i = 0; $i -lt 90; $i++) {
    $mine = A $snapshot.Replace('VID', $vid)
    if ($mine -eq $truth) { break }
    Start-Sleep -Seconds 1
}
Check 'the player sees the same' ($mine -eq $truth) "$mine | $truth"
Write-Host ("      the player had it {0:N0} s after the connection" -f $clock.Elapsed.TotalSeconds)

# --- and the items are drawn once inside
$state = A 'local p = getPlayer(); local v = p:getVehicle(); return (v and ("seat " .. v:getSeat(p)) or "outside") .. " standing=" .. tostring(MELens.isStanding(p))'
Write-Host "      after the connection: $state"
if ($state -notmatch 'standing=true') {
    if ($state -notmatch '^outside') { [void](A 'MELens.leave(getPlayer()); return 1'); Start-Sleep -Seconds 6 }
    [void](A "MELensTest = MELensTest or {}; MELensTest.vehicle = getVehicleById($vid); return 1")
    for ($i = 0; $i -lt 30; $i++) {
        $ready = A 'local v = MELensTest.vehicle; if not v then return "novehicle" end; local ok, why = MELens.canWalkIn(getPlayer(), v); return ok and "ready" or tostring(why)'
        if ($ready -eq 'ready') { break }
        Start-Sleep -Seconds 2
    }
    [void](& $lua -File (Join-Path $root 'dev\lua\walkin.lua') -Port 18470)
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 2
        if ((A 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true') { break }
    }
}
$java = ''
for ($i = 0; $i -lt 20; $i++) {
    $java = A 'return MELensRV.looseStatus()'
    if ($java -match 'entries=3') { break }
    Start-Sleep -Milliseconds 700
}
Check 'the three items are drawn' ($java -match 'entries=3') $java

# --- errors (both consoles are new since the restart)
foreach ($pair in @(@('client', 'build\rv\testhome\Zomboid\console.txt'), @('server', 'build\rv\mphome\server\Zomboid\server-console.txt'))) {
    $errors = Select-String -LiteralPath (Join-Path $root $pair[1]) -CaseSensitive -Pattern 'MELens[A-Za-z_]*\.lua:\d+\)|\[ME_LENS\].*(failed|not shown|not drawn)' | Select-Object -First 3
    Check ("no mod errors in the " + $pair[0] + "'s console after the restart") ($null -eq $errors) (($errors | ForEach-Object { $_.Line }) -join '; ')
}

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

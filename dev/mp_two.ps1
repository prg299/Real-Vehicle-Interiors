# Developer helper: two players in one camper on the local test server. Start the server (dev\mp_server.ps1), connect the
# first game (dev\mp_connect.ps1) and start the second one (dev\second_client.ps1). This script puts both players into one
# Flying Cloud 22 and checks that the server has both in it, that each client sees the other walk, and that what one player
# places the other sees and can take. Prints PASS or FAIL for each check; exit code 1 if any failed.
#   .\dev\mp_two.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0
$script:evalId = 900
# the consoles only grow while the games run: errors are looked for in what is written from here on (an older run's
# stack frames are still in the file)
$consoles = @(@('first client', 'build\rv\testhome\Zomboid\console.txt'), @('second client', 'build\rv\testhome2\Zomboid\console.txt'), @('server', 'build\rv\mphome\server\Zomboid\server-console.txt'))
$consoleStart = @{}
foreach ($log in $consoles) {
    $path = Join-Path $root $log[1]
    $consoleStart[$log[0]] = if (Test-Path -LiteralPath $path) { (Get-Item -LiteralPath $path).Length } else { 0 }
}

function A([string]$code) { $r = & $lua -Code $code -Port 18470; return ($r | ConvertFrom-Json).result }
function B([string]$code) { $r = & $lua -Code $code -Port 18472; return ($r | ConvertFrom-Json).result }

# Lua on the server (asked through the first game); its answer as text.
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

function Idle([scriptblock]$ask, [int]$seconds = 60) {
    for ($i = 0; $i -lt $seconds / 0.7; $i++) {
        Start-Sleep -Milliseconds 700
        $s = & $ask 'local p = getPlayer(); return tostring(MELens.pathing(p)) .. "," .. tostring(ISTimedActionQueue.isPlayerDoingAction(p)) .. "," .. #ISTimedActionQueue.getTimedActionQueue(p).queue'
        if ($s -match 'false,false,0') { Start-Sleep -Milliseconds 1200; return }
    }
}

# --- both are there
$names = @((A 'return getPlayer():getUsername() .. " " .. tostring(isClient())'), (B 'return getPlayer():getUsername() .. " " .. tostring(isClient())'))
Check 'two different players are connected' (($names[0] -ne $names[1]) -and ($names[0] -like '* true') -and ($names[1] -like '* true')) ($names -join ' | ')

# --- one camper, both inside
# The players start at different places of the map. The first one (an admin: the server takes its position from the
# client) goes to the second one; a camper is spawned beside them.
$pa = (A 'local p = getPlayer(); return math.floor(p:getX()) .. "," .. math.floor(p:getY())') -split ','
$pb = (B 'local p = getPlayer(); return math.floor(p:getX()) .. "," .. math.floor(p:getY())') -split ','
$near = ([double]$pa[0] - [double]$pb[0]) * ([double]$pa[0] - [double]$pb[0]) + ([double]$pa[1] - [double]$pb[1]) * ([double]$pa[1] - [double]$pb[1])
if ($near -gt 900) {
    if ((A 'return tostring(getPlayer():getVehicle() ~= nil)') -eq 'true') {
        [void](A 'MELens.leave(getPlayer()); return 1')
        for ($i = 0; $i -lt 20; $i++) { Start-Sleep -Seconds 2; if ((A 'return tostring(getPlayer():getVehicle() ~= nil)') -eq 'false') { break } }
    }
    $gpos = B 'local p = getPlayer(); return math.floor(p:getX()) .. "," .. math.floor(p:getY())'
    $gx, $gy = $gpos -split ','
    [void](A ("local p = getPlayer(); p:setX({0}.5); p:setY({1}.5); p:setLastX({0}.5); p:setLastY({1}.5); p:setZ(0); return 1" -f ([int]$gx + 4), [int]$gy))
    Start-Sleep -Seconds 8
}
$vid = A 'local v = getPlayer():getVehicle(); return v and tostring(v:getId()) or "none"'
if ($vid -eq 'none') {
    $pos = A 'local p = getPlayer(); return math.floor(p:getX()) .. "," .. math.floor(p:getY())'
    $x, $y = $pos -split ','
    $spawnX = [int]$x - 9
    $spawnY = [int]$y
    [void](A "sendClientCommand(getPlayer(), 'MELensDev', 'spawn', { name = 'Base.Trailer54FlyingCloud22', x = $spawnX, y = $spawnY }); return 1")
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        $vid = A @'
local p = getPlayer(); local it = getCell():getVehicles():iterator()
while it:hasNext() do local v = it:next(); if v:getScript():getFullName() == "Base.Trailer54FlyingCloud22" and p:DistToSquared(v:getX(), v:getY()) < 2500 then return tostring(v:getId()) end end
return "none"
'@
        if ($vid -ne 'none') { break }
    }
}
Check 'a camper stands next to the first player' ($vid -ne 'none') $vid

function Enter($ask, [string]$vehicleId) {
    for ($i = 0; $i -lt 40; $i++) {
        $seen = & $ask "return tostring(getVehicleById($vehicleId) ~= nil)"
        if ($seen -eq 'true') { break }
        Start-Sleep -Seconds 2
    }
    [void](& $ask "MELensTest = MELensTest or {}; MELensTest.vehicle = getVehicleById($vehicleId); return 1")
    for ($i = 0; $i -lt 30; $i++) {
        $ready = & $ask 'local v = MELensTest.vehicle; if not v then return "novehicle" end; local ok, why = MELens.canWalkIn(getPlayer(), v); return ok and "ready" or tostring(why)'
        if ($ready -eq 'ready') { break }
        Start-Sleep -Seconds 2
    }
    [void](& $ask (Get-Content -LiteralPath (Join-Path $root 'dev\lua\walkin.lua') -Raw))
    $state = ''
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 2
        $state = & $ask 'local p = getPlayer(); local v = p:getVehicle(); return (v and ("seat " .. v:getSeat(p)) or "outside") .. " standing=" .. tostring(MELens.isStanding(p))'
        if ($state -match 'standing=true') { break }
    }
    return $state
}

$stateA = if ((A 'return tostring(getPlayer():getVehicle() ~= nil)') -eq 'true') { A 'local p = getPlayer(); return "seat " .. p:getVehicle():getSeat(p) .. " standing=" .. tostring(MELens.isStanding(p))' } else { Enter ${function:A} $vid }
Check 'the first player stands in the camper' ($stateA -match 'standing=true') $stateA
$stateB = Enter ${function:B} $vid
Check 'the second player walks in too' ($stateB -match 'standing=true') $stateB
$seats = @((A 'local p = getPlayer(); return p:getVehicle():getSeat(p)'), (B 'local p = getPlayer(); return p:getVehicle():getSeat(p)'))
Check 'in different standing places' ($seats[0] -ne $seats[1]) ($seats -join ' | ')

$onServer = S 'local out = {}; local ps = getOnlinePlayers(); for i = 0, ps:size() - 1 do local p = ps:get(i); local v = p:getVehicle(); out[#out + 1] = p:getUsername() .. "=" .. (v and (tostring(v:getId()) .. "/" .. tostring(v:getSeat(p))) or "none") end; return table.concat(out, " ")'
Check 'the server has both players in the camper' (($onServer -match "MELensAdmin=$vid/") -and ($onServer -match "MELensGuest=$vid/")) $onServer

# --- each sees the other walk
$aid = A 'return getPlayer():getOnlineID()'
$bid = B 'return getPlayer():getOnlineID()'
$walkTo = 'local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v); local g = MELens.WalkGrids[profile.walkGrid]; MELens.walkTo(p, profile.aisleX or 0, g.z0 + #g.rows * g.cell / TARGET); return 1'
[void](A $walkTo.Replace('TARGET', '2'))
Idle ${function:A}
Start-Sleep -Seconds 3
$mine = A 'local p = getPlayer(); local x, z = MELens.Parts.characterAt(p:getVehicle(), p); return string.format("%.2f,%.2f", x, z)'
$theirs = B ("local r = MELens.Sync.remote[$aid]; return r and string.format('%.2f,%.2f', r.x, r.z) or 'none'")
$close = $false
if ($theirs -ne 'none') {
    $m = $mine -split ','; $t = $theirs -split ','
    $close = ([math]::Abs([double]$m[0] - [double]$t[0]) -lt 0.2) -and ([math]::Abs([double]$m[1] - [double]$t[1]) -lt 0.2)
}
Check 'the second player sees the first one where it walked' $close "first at $mine, seen at $theirs"
[void](B $walkTo.Replace('TARGET', '3'))
Idle ${function:B}
Start-Sleep -Seconds 3
$mine = B 'local p = getPlayer(); local x, z = MELens.Parts.characterAt(p:getVehicle(), p); return string.format("%.2f,%.2f", x, z)'
$theirs = A ("local r = MELens.Sync.remote[$bid]; return r and string.format('%.2f,%.2f', r.x, r.z) or 'none'")
$close = $false
if ($theirs -ne 'none') {
    $m = $mine -split ','; $t = $theirs -split ','
    $close = ([math]::Abs([double]$m[0] - [double]$t[0]) -lt 0.2) -and ([math]::Abs([double]$m[1] - [double]$t[1]) -lt 0.2)
}
Check 'and the first player sees the second one where it walked' $close "second at $mine, seen at $theirs"

# --- what one places, the other sees and takes
# (taken off the floor the way the mod does it, so that the clients are told: a bare container:clear() on the server
# sends nothing and leaves the clients with items that are no longer there)
[void](S 'local v = getVehicleById(VID); local f = MELens.Loose.floorContainer(v); local gone = {}; for i = 0, f:getItems():size() - 1 do gone[#gone + 1] = f:getItems():get(i) end; for _, it in ipairs(gone) do f:Remove(it); sendRemoveItemFromContainer(f, it) end; local part = MELens.Loose.floorPart(v); part:getModData().loose = nil; v:transmitPartModData(part); return #gone'.Replace('VID', $vid))
[void](S "local ps = getOnlinePlayers(); for i = 0, ps:size() - 1 do local p = ps:get(i); if p:getUsername() == 'MELensAdmin' then local it = p:getInventory():AddItem('Base.Pot'); sendAddItemToContainer(p:getInventory(), it) end end; return 1")
Start-Sleep -Seconds 3
$count = 'local v = getPlayer():getVehicle(); local n = 0; for _, e in ipairs(MELens.Loose.list(v, MELens.profileFor(v))) do n = n + 1 end; return n'
Check 'the floor is empty for both players before the pot' (((A $count) -eq 0) -and ((B $count) -eq 0)) ("first " + (A $count) + ", second " + (B $count))
# where the second player stands: the pot goes there (the first walks over)
$at = B 'local p = getPlayer(); local x, z = MELens.Parts.characterAt(p:getVehicle(), p); return string.format("%.3f,%.3f", x, z)'
$px, $pz = $at -split ','
# (as text from Lua: a number would be written with this computer's decimal comma by -f)
$floorY = A 'return tostring(MELens.profileFor(getPlayer():getVehicle()).floorY)'
$clock = [Diagnostics.Stopwatch]::StartNew()
$placed = & (Join-Path $PSScriptRoot 'loose.ps1') place ("Pot|{0},{1},{2},0,0" -f $px, $floorY, $pz)
Idle ${function:A}
# the item and its place reach the second player separately, a moment after the first player's action
$status = 'local v = getPlayer():getVehicle(); local n = 0; for _, e in ipairs(MELens.Loose.list(v, MELens.profileFor(v))) do n = n + 1 end; return n .. " " .. MELensRV.looseStatus()'
$seenByB = ''
$seenAfter = $null
for ($i = 0; $i -lt 40; $i++) {
    $seenByB = B $status
    if ($seenByB -match '^1 .*entries=1') { $seenAfter = $clock.Elapsed.TotalSeconds; break }
    Start-Sleep -Milliseconds 500
}
Check 'the second player sees the pot the first one set down' ($seenByB -match '^1 .*entries=1') "$seenByB (place said: $placed)"
if ($seenAfter) { Write-Host ("      the pot reached the second player after {0:N1} s, with the walk" -f $seenAfter) }
$potId = B 'local v = getPlayer():getVehicle(); local e; for _, x in ipairs(MELens.Loose.list(v, MELens.profileFor(v))) do e = x end; return e and tostring(e.id) or "none"'
[void](B "local p = getPlayer(); local v = p:getVehicle(); local e; for _, x in ipairs(MELens.Loose.list(v, MELens.profileFor(v))) do e = x end; ISTimedActionQueue.add(MELensGrabLoose:new(p, v, e.id, 1)); return 1")
Idle ${function:B}
Start-Sleep -Seconds 3
$left = @((A $count), (B "return tostring(getPlayer():getInventory():getItemById($potId) ~= nil)"), (S "local f = MELens.Loose.floorContainer(getVehicleById($vid)); return f:getItems():size()"))
Check 'the second player takes it: gone for the first and the server, in the second one''s inventory' (($left[0] -eq '0') -and ($left[1] -eq 'true') -and ($left[2] -eq '0')) ($left -join ' | ')

# --- errors in the consoles
foreach ($log in $consoles) {
    $path = Join-Path $root $log[1]
    $errors = @()
    if (Test-Path -LiteralPath $path) {
        $stream = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        try {
            [void]$stream.Seek([Math]::Min($consoleStart[$log[0]], $stream.Length), [IO.SeekOrigin]::Begin)
            $text = [IO.StreamReader]::new($stream).ReadToEnd()
        } finally { $stream.Dispose() }
        $errors = @($text -split "`n" | Where-Object { $_ -cmatch 'MELens[A-Za-z_]*\.lua:\d+\)|\[ME_LENS\].*(failed|not shown|not drawn)' } | Select-Object -First 3)
    }
    Check ("no mod errors in the " + $log[0] + "'s console") ($errors.Count -eq 0) ($errors -join '; ')
}

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

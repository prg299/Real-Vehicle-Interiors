# Developer helper: a player who arrives later. The first player builds in a camper on the local test server (three items,
# a name and a paint), while the second player is far away and has never seen that camper. The second player is then
# brought next to it, the camper loads on its side, and it must see exactly what the server holds, walk in, and see the
# items drawn. Start the server fresh (dev\mp_server.ps1 -Fresh), connect the first game (dev\mp_connect.ps1) and start the
# second one (dev\second_client.ps1) first: the two players start far apart. Prints PASS or FAIL for each check; exit
# code 1 if any failed.
#   .\dev\mp_late.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0
$script:evalId = 2900

function A([string]$code) { $r = & $lua -Code $code -Port 18470; return ($r | ConvertFrom-Json).result }
function B([string]$code) { $r = & $lua -Code $code -Port 18472; return ($r | ConvertFrom-Json).result }

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

function Idle([scriptblock]$ask, [int]$seconds = 60) {
    for ($i = 0; $i -lt $seconds / 0.7; $i++) {
        Start-Sleep -Milliseconds 700
        $s = & $ask 'local p = getPlayer(); return tostring(MELens.pathing(p)) .. "," .. tostring(ISTimedActionQueue.isPlayerDoingAction(p)) .. "," .. #ISTimedActionQueue.getTimedActionQueue(p).queue'
        if ($s -match 'false,false,0') { Start-Sleep -Milliseconds 1500; return }
    }
}

# an item for the first player, given by the server (so that the server knows it); returns once the client has it
function Give([string]$type, [string]$short) {
    [void](S "local ps = getOnlinePlayers(); for i = 0, ps:size() - 1 do local p = ps:get(i); if p:getUsername() == 'MELensAdmin' then local it = p:getInventory():AddItem('$type'); sendAddItemToContainer(p:getInventory(), it) end end; return 1")
    for ($i = 0; $i -lt 30; $i++) {
        if ((A "return tostring(getPlayer():getInventory():getFirstTypeRecurse('$short') ~= nil)") -eq 'true') { return }
        Start-Sleep -Milliseconds 500
    }
}

# the errors the consoles collect from here on (the files only grow while the games run)
$consoles = @(@('first client', 'build\rv\testhome\Zomboid\console.txt'), @('second client', 'build\rv\testhome2\Zomboid\console.txt'), @('server', 'build\rv\mphome\server\Zomboid\server-console.txt'))
$consoleStart = @{}
foreach ($log in $consoles) {
    $path = Join-Path $root $log[1]
    $consoleStart[$log[0]] = if (Test-Path -LiteralPath $path) { (Get-Item -LiteralPath $path).Length } else { 0 }
}

# what a vehicle holds, in one line: where each item lies, how many items the Floor container has, name and paint
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

# --- two players, far apart
$names = @((A 'return getPlayer():getUsername() .. " " .. tostring(isClient())'), (B 'return getPlayer():getUsername() .. " " .. tostring(isClient())'))
Check 'two different players are connected' (($names[0] -ne $names[1]) -and ($names[0] -like '* true') -and ($names[1] -like '* true')) ($names -join ' | ')
$pa = (A 'local p = getPlayer(); return math.floor(p:getX()) .. "," .. math.floor(p:getY())') -split ','
$pb = (B 'local p = getPlayer(); return math.floor(p:getX()) .. "," .. math.floor(p:getY())') -split ','
$apart = [math]::Sqrt(([double]$pa[0] - [double]$pb[0]) * ([double]$pa[0] - [double]$pb[0]) + ([double]$pa[1] - [double]$pb[1]) * ([double]$pa[1] - [double]$pb[1]))
# (what counts is the check below that the camper is unknown to it; the distance is only for the log)
Check 'the second player is some way from the first' ($apart -gt 60) ("{0:N0} tiles" -f $apart)

# --- the first player builds
$vid = A 'local v = getPlayer():getVehicle(); return v and tostring(v:getId()) or "none"'
if ($vid -eq 'none') {
    $x, $y = $pa
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
    Check 'a camper stands next to the first player' ($vid -ne 'none') $vid
    [void](A "MELensTest = MELensTest or {}; MELensTest.vehicle = getVehicleById($vid); return 1")
    & (Join-Path $PSScriptRoot 'wait_still.ps1')
    [void](& $lua -File (Join-Path $root 'dev\lua\walkin.lua') -Port 18470)
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 2
        if ((A 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true') { break }
    }
}
Check 'the first player stands in the camper' ((A 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true')

[void](A 'MELens.LooseUI.testMouse = nil; return 1')
Give 'Base.Pot' 'Pot'
Give 'Base.Hammer' 'Hammer'
Give 'Base.Spiffo' 'Spiffo'
Give 'Base.PaintGreen' 'PaintGreen'
Give 'Base.Paintbrush' 'Paintbrush'
[void](& (Join-Path $PSScriptRoot 'loose.ps1') place 'Pot|0.0,0.145,2.4,0,1')
Idle ${function:A}
[void](& (Join-Path $PSScriptRoot 'loose.ps1') place 'Spiffo|0.594,0.457,-0.555,0,3')
Idle ${function:A}
[void](& (Join-Path $PSScriptRoot 'loose.ps1') drop 'Hammer')
Idle ${function:A}
[void](A @'
local p = getPlayer(); local v = p:getVehicle(); local inv = p:getInventory()
local can, brush = inv:getFirstTypeRecurse("PaintGreen"), inv:getFirstTypeRecurse("Paintbrush")
ISTimedActionQueue.add(MELensRename:new(p, v, "Late Rig"))
ISTimedActionQueue.add(MELensPaintWalls:new(p, v, can, brush, 0.41, 0.80, 0.41))
return "queued"
'@)
Idle ${function:A} 120
$truth = S $snapshot.Replace('VID', $vid)
Write-Host "      the server holds: $truth"
Check 'the server holds three items, the name and the paint' ($truth -match '^(\S+@\S+ r\d+ s-?\d+; ){2}\S+@\S+ r\d+ s-?\d+ \| items=3 name=Late Rig paint=0\.41$') $truth
$first = A $snapshot.Replace('VID', $vid)
Check 'the first player sees the same' ($first -eq $truth) "$first | $truth"

# --- the second player has never seen the camper
$known = B "return tostring(getVehicleById($vid) ~= nil)"
Check 'the second player does not know the camper yet' ($known -eq 'false') $known

# --- and arrives (next to the camper; an admin is moved by its client, so the second player is given the rank for the move)
$at = A 'local v = getPlayer():getVehicle(); return math.floor(v:getX()) .. "," .. math.floor(v:getY())'
$vx, $vy = $at -split ','
$clock = [Diagnostics.Stopwatch]::StartNew()
[void](B ("local p = getPlayer(); p:setX({0}.5); p:setY({1}.5); p:setLastX({0}.5); p:setLastY({1}.5); p:setZ(0); return 1" -f ([int]$vx + 5), [int]$vy))
$loaded = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    if ((B "return tostring(getVehicleById($vid) ~= nil)") -eq 'true') { $loaded = $true; break }
}
$near = B ("local p = getPlayer(); return math.floor(math.sqrt((p:getX() - {0}) ^ 2 + (p:getY() - {1}) ^ 2))" -f $vx, $vy)
Check 'the camper loads on the second player''s side when it arrives' $loaded ("player is $near tiles from the camper")
if ($loaded) { Write-Host ("      loaded after {0:N0} s" -f $clock.Elapsed.TotalSeconds) }

# what it holds arrives with the camper, or a moment after
$late = ''
$sameAfter = $null
for ($i = 0; $i -lt 40; $i++) {
    $late = B $snapshot.Replace('VID', $vid)
    if ($late -eq $truth) { $sameAfter = $clock.Elapsed.TotalSeconds; break }
    Start-Sleep -Milliseconds 500
}
Check 'the second player sees the same items in the same places, the same name and paint as the server' ($late -eq $truth) "$late | $truth"
if ($sameAfter) { Write-Host ("      the same after {0:N0} s" -f $sameAfter) }

# --- and walks in: the items are drawn
function Enter($ask, [string]$vehicleId) {
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
$state = Enter ${function:B} $vid
Check 'the second player walks in' ($state -match 'standing=true') $state
$java = ''
for ($i = 0; $i -lt 20; $i++) {
    $java = B 'return MELensRV.looseStatus()'
    if ($java -match 'entries=3') { break }
    Start-Sleep -Milliseconds 700
}
Check 'and the three items are drawn for it' ($java -match 'entries=3') $java

# --- errors in the consoles since the start
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

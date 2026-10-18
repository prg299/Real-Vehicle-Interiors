# Developer helper: the loot window's Floor tab on a server. With the first player standing in a camper that has a pot on
# its floor (dev\mp_late.ps1 leaves one), it takes the pot with the game's own transfer action (what dragging it out of
# the Floor tab does) and puts it back the same way, and compares the server's Floor container with what the player
# sees and what is drawn. Prints PASS or FAIL for each check; exit code 1 if any failed.
#   .\dev\mp_floor_tab.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0
$script:evalId = 4900

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

function Idle([int]$seconds = 60) {
    for ($i = 0; $i -lt $seconds / 0.7; $i++) {
        Start-Sleep -Milliseconds 700
        $s = A 'local p = getPlayer(); return tostring(MELens.pathing(p)) .. "," .. tostring(ISTimedActionQueue.isPlayerDoingAction(p)) .. "," .. #ISTimedActionQueue.getTimedActionQueue(p).queue'
        if ($s -match 'false,false,0') { Start-Sleep -Milliseconds 1500; return }
    }
}

$start = (Get-Item -LiteralPath (Join-Path $root 'build\rv\testhome\Zomboid\console.txt')).Length
$serverStart = (Get-Item -LiteralPath (Join-Path $root 'build\rv\mphome\server\Zomboid\server-console.txt')).Length

$vid = A 'local v = getPlayer():getVehicle(); return v and tostring(v:getId()) or "none"'
Check 'the first player is in a camper' ($vid -ne 'none') $vid
# how many items the server's Floor holds, and how many the player lists
$serverCount = "local f = MELens.Loose.floorContainer(getVehicleById($vid)); local pot = f:getFirstType('Pot'); return f:getItems():size() .. ' pot=' .. tostring(pot ~= nil)"
$clientCount = 'local v = getPlayer():getVehicle(); local n = 0; for _ in ipairs(MELens.Loose.list(v, MELens.profileFor(v))) do n = n + 1 end; return n'

$before = S $serverCount
Check 'the server''s Floor holds three items with the pot' ($before -eq '3 pot=true') $before

# --- take it out the way the Floor tab does
[void](A @'
local p = getPlayer(); local v = p:getVehicle(); local floor = MELens.Loose.floorContainer(v)
local pot = floor:getFirstType("Pot")
if not pot then return "no pot" end
MELensTest = MELensTest or {}; MELensTest.potId = pot:getID()
ISTimedActionQueue.add(ISInventoryTransferUtil.newInventoryTransferAction(p, pot, floor, p:getInventory()))
return "queued"
'@)
Idle
Start-Sleep -Seconds 2
$inInventory = A 'return tostring(getPlayer():getInventory():getItemById(MELensTest.potId) ~= nil)'
Check 'the pot is in the player''s inventory' ($inInventory -eq 'true') $inInventory
$after = S $serverCount
Check 'and gone from the server''s Floor' ($after -eq '2 pot=false') $after
$mine = A $clientCount
Check 'the player lists two items on the floor' ($mine -eq 2) "$mine"
$java = ''
for ($i = 0; $i -lt 15; $i++) {
    $java = A 'return MELensRV.looseStatus()'
    if ($java -match 'entries=2') { break }
    Start-Sleep -Milliseconds 700
}
Check 'and two are drawn' ($java -match 'entries=2') $java

# --- and back in
[void](A @'
local p = getPlayer(); local v = p:getVehicle(); local floor = MELens.Loose.floorContainer(v)
local pot = p:getInventory():getItemById(MELensTest.potId)
if not pot then return "no pot" end
ISTimedActionQueue.add(ISInventoryTransferUtil.newInventoryTransferAction(p, pot, p:getInventory(), floor))
return "queued"
'@)
Idle
Start-Sleep -Seconds 2
$back = S $serverCount
Check 'put back, the server''s Floor holds three items with the pot' ($back -eq '3 pot=true') $back
$mine = A $clientCount
Check 'the player lists three' ($mine -eq 3) "$mine"
for ($i = 0; $i -lt 15; $i++) {
    $java = A 'return MELensRV.looseStatus()'
    if ($java -match 'entries=3') { break }
    Start-Sleep -Milliseconds 700
}
Check 'and three are drawn' ($java -match 'entries=3') $java
$where = S ("local v = getVehicleById($vid); for _, e in pairs(MELens.Loose.positions(v, false) or {}) do if e.t == 'Base.Pot' then return string.format('s=%.0f at %.2f,%.2f,%.2f', e.s, e.x, e.y, e.z) end end return 'no place recorded'")
Write-Host "      the server's record of the pot: $where"

# --- errors in the consoles since the start
foreach ($pair in @(@('client', 'build\rv\testhome\Zomboid\console.txt', $start), @('server', 'build\rv\mphome\server\Zomboid\server-console.txt', $serverStart))) {
    $path = Join-Path $root $pair[1]
    $stream = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        [void]$stream.Seek([Math]::Min($pair[2], $stream.Length), [IO.SeekOrigin]::Begin)
        $text = [IO.StreamReader]::new($stream).ReadToEnd()
    } finally { $stream.Dispose() }
    $errors = @($text -split "`n" | Where-Object { $_ -cmatch 'MELens[A-Za-z_]*\.lua:\d+\)|\[ME_LENS\].*(failed|not shown|not drawn)' } | Select-Object -First 3)
    Check ("no mod errors in the " + $pair[0] + "'s console") ($errors.Count -eq 0) ($errors -join '; ')
}

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

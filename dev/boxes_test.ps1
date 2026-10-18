# Developer helper: every box in an F700 box truck, picked up one by one the way a player does it (2.0.3), in the test
# game. Spawns a box truck and walks in (dev\enter_vehicle.ps1), empties the boxes (Pick up wants an empty box), then
# right-clicks the next box nothing rests on, the one nearest the door first, through the real menu with the scripted
# mouse on a part of it that is in view (dev\lua\box_pick.lua), and checks after each that exactly that box is gone
# and one more is carried. Takes about three minutes. Prints PASS or FAIL; exit code 1 if any failed.
#   .\dev\boxes_test.ps1 [-Keep]    (-Keep: leave the truck and the carried boxes as they are at the end)
param([switch]$Keep)
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0
$driver = Get-Content -LiteralPath (Join-Path $root 'dev\lua\box_pick.lua') -Raw

function C([string]$code) { $r = & $lua -Code $code; $j = $r | ConvertFrom-Json; if ($j.ok) { return $j.result } else { return "ERR $($j.error)" } }
function Box([string]$mode) { return C ($driver.Replace('local MODE = "MODE"', "local MODE = ""$mode""")) }
function Check([string]$name, [bool]$ok, $detail = '') {
    if ($ok) { Write-Host "PASS  $name" } else { Write-Host "FAIL  $name  $detail"; $script:failed++ }
}
function Wait-Idle([int]$seconds = 30) {
    for ($i = 0; $i -lt $seconds / 0.7; $i++) {
        Start-Sleep -Milliseconds 700
        $s = C 'local p = getPlayer(); return tostring(MELens.pathing(p)) .. "," .. tostring(ISTimedActionQueue.isPlayerDoingAction(p)) .. "," .. #ISTimedActionQueue.getTimedActionQueue(p).queue'
        if ($s -match 'false,false,0') { Start-Sleep -Milliseconds 500; return $true }
    }
    return $false
}
$consolePath = Join-Path $root 'build\rv\testhome\Zomboid\console.txt'
$consoleStart = (Get-Item -LiteralPath $consolePath).Length

# --- a box truck, inside, standing
if ((C 'local v = getPlayer():getVehicle(); return tostring(v ~= nil and v:getScript():getName() == "87fordF700box" and MELens.isStanding(getPlayer()))') -ne 'true') {
    [void](C 'local p = getPlayer(); if p:getVehicle() then MELens.leave(p) end; return 1')
    Start-Sleep -Seconds 6
    [void](& (Join-Path $PSScriptRoot 'enter_vehicle.ps1') -Name 'Base.87fordF700box')
    [void](Wait-Idle)
}
Check 'standing in an F700 box truck' ((C 'return tostring(MELens.isStanding(getPlayer()))') -eq 'true')
[void](C 'getPlayer():getInventory():RemoveAll("MELensRV_Box"); return 1')
[void](Box 'empty')
$start = Box 'count'
$boxes = [int](($start -split ' ')[0])
Check 'the truck has its boxes, none carried' (($boxes -gt 40) -and ($start -match ' 0$')) $start

# --- one after the other
$layout = "local v = getPlayer():getVehicle(); local t = {}; for i = 1, 63 do local p = v:getPartById('MELensSpot' .. i); t[i] = (p and p:getInventoryItem()) and '1' or '0' end; return table.concat(t)"
$wrong = @()
$stuck = ''
for ($k = 1; $k -le $boxes; $k++) {
    $before = C $layout
    $index = Box 'which'
    if ($index -notmatch '^\d+$') { $stuck = "after $($k - 1): $index"; break }
    $picked = Box 'next'
    if ($picked -notmatch '^picking') { $stuck = "box $index`: $picked"; break }
    [void](Wait-Idle)
    $after = C $layout
    $expected = $before.Substring(0, [int]$index - 1) + '0' + $before.Substring([int]$index)
    if ($after -ne $expected) { $wrong += "box $index" }
}
Check 'every box could be picked up through the menu' ($stuck -eq '') $stuck
Check 'each time exactly the box picked was gone' ($wrong.Count -eq 0) ($wrong -join ', ')
$end = Box 'count'
Check "all $boxes boxes carried, none left in the truck" ($end -eq "0 $boxes") $end

$stream = [IO.File]::Open($consolePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
try {
    [void]$stream.Seek([Math]::Min($consoleStart, $stream.Length), [IO.SeekOrigin]::Begin)
    $text = [IO.StreamReader]::new($stream).ReadToEnd()
} finally { $stream.Dispose() }
$errors = @($text -split "`n" | Where-Object { $_ -cmatch 'MELens[A-Za-z_]*\.lua:\d+\)|Lua fail' } | Select-Object -First 3)
Check 'no ME: LENS Lua errors' ($errors.Count -eq 0) ($errors -join ' / ')

if (-not $Keep) {
    # the carried boxes go (a later Grab needs weight room); a fresh truck comes with the next enter_vehicle run
    [void](C 'getPlayer():getInventory():RemoveAll("MELensRV_Box"); return 1')
}
if ($failed -gt 0) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

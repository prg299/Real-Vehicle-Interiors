# Developer helper: rain fills a camper's water tank on the test server, and the player sees the new level. With the first
# player standing in a camper (dev\mp_late.ps1 leaves one) it empties the tank, makes it rain on the server through the
# climate manager's admin override, runs the rain tick the game runs every ten minutes, and compares the tank on the
# server with the one on the client. Prints PASS or FAIL for each check; exit code 1 if any failed.
#   .\dev\mp_rain.ps1
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$failed = 0
$script:evalId = 5900

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

$vid = A 'local v = getPlayer():getVehicle(); return v and tostring(v:getId()) or "none"'
Check 'the first player is in a camper' ($vid -ne 'none') $vid
# the tank as text: litres and whether it is tainted (the part's data; the same code runs on both sides)
$tank = "local v = getVehicleById($vid); local part = MELens.Utilities.part(v, MELens.Parts.WATER); local d = part:getModData(); return string.format('%.2f tainted=%s outside=%s', d.water or 0, tostring(d.tainted == true), tostring(v:getSquare() ~= nil and v:getSquare():isOutside()))"

[void](S "MELens.Utilities.changeWater(getVehicleById($vid), -1000, false); return 1")
Start-Sleep -Seconds 2
$empty = @((S $tank), (A $tank))
Check 'the tank is empty on the server and on the client' (($empty[0] -like '0.00 tainted=false*') -and ($empty[1] -like '0.00 tainted=false*')) ($empty -join ' | ')
Check 'the camper stands outside' ($empty[0] -like '*outside=true') $empty[0]

# rain on the server (the admin value is followed after a moment)
$rain = ''
[void](S "local c = getClimateManager(); local r = c:getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY); r:setEnableAdmin(true); r:setAdminValue(1.0); return 1")
for ($i = 0; $i -lt 30; $i++) {
    $rain = S "return string.format('%.2f', getClimateManager():getRainIntensity())"
    if ([double]::Parse($rain, [Globalization.CultureInfo]::InvariantCulture) -gt 0.5) { break }
    Start-Sleep -Seconds 1
}
Check 'it rains on the server' ([double]::Parse($rain, [Globalization.CultureInfo]::InvariantCulture) -gt 0.5) $rain
[void](S 'MELens.Home.rainTick(); return 1')
Start-Sleep -Seconds 3
$full = @((S $tank), (A $tank))
Check 'the tank took rain, tainted, on the server' ($full[0] -match '^[1-9]\d*\.\d\d tainted=true') $full[0]
Check 'and the player sees the same level' ($full[0] -eq $full[1]) ($full -join ' | ')

# back to the weather the world had
[void](S "local r = getClimateManager():getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY); r:setEnableAdmin(false); return 1")
[void](S "MELens.Utilities.changeWater(getVehicleById($vid), -1000, false); return 1")

if ($failed) { Write-Host "$failed check(s) failed"; exit 1 }
Write-Host 'all checks passed'

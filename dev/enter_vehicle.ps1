# Developer helper: spawn a vehicle next to the test character (dev\lua\spawn_one.lua,
# replacing the previous test vehicle), walk in through the normal action queue, wait
# until standing inside and capture the window.
#   .\dev\enter_vehicle.ps1 -Name Base.87fordB700school -Out build\rv\dbg\bus.png [-Heading N|E|S|W]
param([Parameter(Mandatory)][string]$Name, [string]$Out, [ValidateSet('N', 'E', 'S', 'W')][string]$Heading = 'E')

$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'

# back to the start spot (MELensTest.start from dev\lua\find_open.lua, else the street spot)
& $lua -Code 'local p = getPlayer(); if p:getVehicle() then return "inside" end; local s = MELensTest and MELensTest.start or { x = 10813.5, y = 10140.5 }; p:setX(s.x); p:setY(s.y); p:setLastX(s.x); p:setLastY(s.y); return "at start"'
# west of the start spot (grass): east of it the road and its power lines cross every capture
$spawn = (Get-Content -LiteralPath (Join-Path $root 'dev\lua\spawn_one.lua') -Raw).Replace('NAME', $Name).Replace('tonumber("7")', 'tonumber("-9")').Replace('local HEADING = "E"', "local HEADING = ""$Heading""")
& $lua -Code $spawn
Start-Sleep -Seconds 1
& (Join-Path $PSScriptRoot 'wait_still.ps1')
& $lua -File (Join-Path $root 'dev\lua\walkin.lua')
$state = ''
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    $state = & $lua -Code 'local p = getPlayer(); local v = p:getVehicle(); return (v and ("seat " .. v:getSeat(p)) or "outside") .. " standing=" .. tostring(MELens.isStanding(p))'
    if ($state -match 'seat -?[0-9]+ standing=true') { break }
}
Write-Output "state: $state"
if ($Out) {
    Start-Sleep -Seconds 2
    & (Join-Path $root 'dev\capture.ps1') -Out $Out
}

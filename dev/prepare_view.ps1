# Developer helper: get the test character standing in the middle of a freshly spawned vehicle,
# the camera zoomed in and the interface hidden, ready to capture (dev\capture.ps1).
#   .\dev\prepare_view.ps1 -Name Base.Trailer87Scamp16 [-Heading N] [-Zoom 0.5]
# Leaves whatever vehicle the character is in first; the interface stays hidden until
# Lua 'ISUIHandler.setVisibleAllUI(true)'.
param([Parameter(Mandatory)][string]$Name, [ValidateSet('N', 'E', 'S', 'W')][string]$Heading = 'N', [double]$Zoom = 0.5)

$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'

function Lua([string]$code) { $r = & $lua -Code $code; return ($r | ConvertFrom-Json).result }
function Set-Zoom([double]$target) {
    for ($i = 0; $i -lt 8; $i++) {
        $now = [double](Lua 'return getCore():getZoom(0)')
        if ([math]::Abs($now - $target) -lt 0.01) { return }
        $step = if ($now -gt $target) { -1 } else { 1 }
        [void](Lua "getCore():doZoomScroll(0, $step); return 1")
        Start-Sleep -Milliseconds 1300
    }
}

if ((Lua 'return getPlayer():getVehicle() and "in" or "out"') -eq 'in') {
    [void](Lua 'MELens.leave(getPlayer()); return 1')
    for ($i = 0; $i -lt 20; $i++) { Start-Sleep -Seconds 2; if ((Lua 'return getPlayer():getVehicle() and "in" or "out"') -eq 'out') { break } }
}
# vehicles an earlier run left in the saved world would stand in the picture
[void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))
& (Join-Path $PSScriptRoot 'enter_vehicle.ps1') -Name $Name -Heading $Heading | Out-Null
[void](Lua @'
local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v)
local g = MELens.WalkGrids[profile.walkGrid]
MELens.walkTo(p, profile.aisleX or 0, g.z0 + #g.rows * g.cell / 2)
return 1
'@)
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if ((Lua 'local s = MELens.debugState(); return tostring(s.pathing) .. "," .. tostring(s.moving)') -eq 'false,false') { break }
}
Set-Zoom $Zoom
[void](Lua 'ISUIHandler.setVisibleAllUI(false); return 1')
Start-Sleep -Seconds 2
Lua 'local p = getPlayer(); local v = p:getVehicle(); return tostring(v and v:getScriptName()) .. " standing=" .. tostring(MELens.isStanding(p))'

# Developer helper: which of KI5's models draws something in the picture? Enters a vehicle,
# lists the models the cutaway draws (MELensRV.surveyInfo), then hides them one at a time and
# reports, for each, how many pixels of the capture change and where (client-area pixels).
# A model that changes the pixels of a stray object is the one to hide or cut.
#   .\dev\bisect_models.ps1 -Name Base.Trailer87Scamp16 [-Heading N] [-Zoom 0.5] [-Roi x0,y0,x1,y1] [-Where middle|rear|front]
# -Roi counts only the changes inside that box (client-area pixels of the capture).
param([Parameter(Mandatory)][string]$Name, [ValidateSet('N', 'E', 'S', 'W')][string]$Heading = 'N', [double]$Zoom = 0.5, [int[]]$Roi,
      [ValidateSet('middle', 'rear', 'front')][string]$Where = 'middle')

$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
$out = Join-Path $root 'build\rv\dbg\bisect'
New-Item -ItemType Directory -Force -Path $out | Out-Null

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
& (Join-Path $PSScriptRoot 'enter_vehicle.ps1') -Name $Name -Heading $Heading | Out-Null
# vehicles an earlier run left in the saved world would stand in the picture (and draw uncut)
[void](& $lua -File (Join-Path $root 'dev\lua\remove_others.lua'))
# -Where rear / front: walk to that end of the inside, so the end is in the middle of the picture
[void](Lua @'
local p = getPlayer(); local v = p:getVehicle(); local profile = MELens.profileFor(v)
local g = MELens.WalkGrids[profile.walkGrid]
local zFar = g.z0 + #g.rows * g.cell
local z = "WHERE" == "rear" and (g.z0 + 0.7) or ("WHERE" == "front" and (zFar - 0.7) or (g.z0 + #g.rows * g.cell / 2))
MELens.walkTo(p, profile.aisleX or 0, z)
return 1
'@.Replace('WHERE', $Where))
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if ((Lua 'local s = MELens.debugState(); return tostring(s.pathing) .. "," .. tostring(s.moving)') -eq 'false,false') { break }
}
Set-Zoom $Zoom
[void](Lua 'ISUIHandler.setVisibleAllUI(false); MELensRV.setSurvey(true); return 1')
Start-Sleep -Seconds 3
$names = @()
foreach ($line in ((Lua 'return MELensRV.surveyInfo()') -split "`n")) {
    if ($line -match '^(\S+) \[mesh:([^\]]+)\]: mesh \(\s*([-+0-9.E]+)') {
        if ($matches[1] -notlike 'MELens*' -and $matches[3] -ne '3.403E+38') { $names += ,@($matches[1], $matches[2]) }
    }
}
Write-Host "models drawn: $($names.Count)"
& (Join-Path $PSScriptRoot 'capture.ps1') -Out (Join-Path $out 'base.png') | Out-Null
Start-Sleep -Milliseconds 700
& (Join-Path $PSScriptRoot 'capture.ps1') -Out (Join-Path $out 'noise.png') | Out-Null
foreach ($n in $names) {
    $model, $mesh = $n
    [void](Lua "MELensRV.setKeepPlane('$model', 0, 0, 0, 1); return 1")
    Start-Sleep -Milliseconds 900
    $file = Join-Path $out "$model.png"
    & (Join-Path $PSScriptRoot 'capture.ps1') -Out $file | Out-Null
    $roiArgs = if ($Roi) { @('--roi') + $Roi } else { @() }
    $diff = & python (Join-Path $PSScriptRoot 'image_diff.py') (Join-Path $out 'base.png') $file (Join-Path $out 'noise.png') @roiArgs
    Write-Host ("{0,-44} {1}" -f $model, $diff)
    [void](& $lua -File (Join-Path $PSScriptRoot 'lua\reset_hides.lua'))
    Start-Sleep -Milliseconds 300
}
[void](Lua 'ISUIHandler.setVisibleAllUI(true); MELensRV.setSurvey(false); return 1')

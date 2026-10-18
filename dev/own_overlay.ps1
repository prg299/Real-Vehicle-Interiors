# Developer helper: which of ME: LENS' models draws what, in the picture, to find any of it sticking
# out past the hull. Enters a vehicle (dev\prepare_view.ps1), captures it, then hides ME: LENS'
# models group by group (the floor, the walls, all the furniture) and paints what each group
# draws in its own colour over the capture: magenta floor, cyan walls, yellow furniture.
#   .\dev\own_overlay.ps1 -Name Base.Trailer87Scamp13 -Heading N [-Out build\rv\dbg\own] [-Zoom 0.5]
# Writes <Out>\<Name>_<Heading>.png (the capture with the colours, the vehicle enlarged 2x).
param([Parameter(Mandatory)][string]$Name, [ValidateSet('N', 'E', 'S', 'W')][string]$Heading = 'N',
      [string]$Out, [double]$Zoom = 0.5, [switch]$SkipPrepare)

$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
if (-not $Out) { $Out = Join-Path $root 'build\rv\dbg\own' }
New-Item -ItemType Directory -Force -Path $Out | Out-Null
function Lua([string]$code) { $r = & $lua -Code $code; return ($r | ConvertFrom-Json).result }

if (-not $SkipPrepare) { & (Join-Path $PSScriptRoot 'prepare_view.ps1') -Name $Name -Heading $Heading -Zoom $Zoom | Out-Null }
[void](Lua 'MELensRV.setSurvey(true); return 1')
Start-Sleep -Seconds 3
$floor = @(); $walls = @(); $furniture = @()
foreach ($line in ((Lua 'return MELensRV.surveyInfo()') -split "`n")) {
    if ($line -match '^(\S+) \[mesh:([^\]]+)\]') {
        $n = $matches[1]
        if ($n -like 'MELensShell_*_floor') { $floor += $n }
        elseif ($n -like 'MELensShell_*_walls') { $walls += $n }
        elseif ($n -like 'MELensRV_*') { $furniture += $n }
    }
}
[void](Lua 'MELensRV.setSurvey(false); return 1')
Start-Sleep -Milliseconds 800
$key = ($Name -replace '^Base\.', '') + '_' + $Heading
& (Join-Path $PSScriptRoot 'capture.ps1') -Out (Join-Path $Out "${key}_base.png") | Out-Null
Start-Sleep -Milliseconds 600
& (Join-Path $PSScriptRoot 'capture.ps1') -Out (Join-Path $Out "${key}_noise.png") | Out-Null
$groups = @(@('floor', $floor), @('walls', $walls), @('furniture', $furniture))
foreach ($g in $groups) {
    $label, $names = $g
    foreach ($n in $names) { [void](Lua "MELensRV.setKeepPlane('$n', 0, 0, 0, 1); return 1") }
    Start-Sleep -Milliseconds 1000
    & (Join-Path $PSScriptRoot 'capture.ps1') -Out (Join-Path $Out "${key}_no_$label.png") | Out-Null
    [void](& $lua -File (Join-Path $PSScriptRoot 'lua\reset_hides.lua'))
    Start-Sleep -Milliseconds 300
}
python (Join-Path $PSScriptRoot 'own_overlay.py') $Out $key

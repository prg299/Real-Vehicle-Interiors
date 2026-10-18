# Developer helper: dev\own_overlay.ps1 for every vehicle from every heading: the pictures to look at to
# see whether anything of ME: LENS' sticks out past a hull (see dev\own_overlay.ps1 for the colours).
#   .\dev\own_overlay_all.ps1 [-Only Base.Trailer87Scamp13,...] [-Headings N,E,S,W] [-Out build\rv\dbg\own]
# Needs the running test game (scripts\testgame.ps1 + dev\fresh_world.ps1 or dev\restart.ps1).
param([string[]]$Only, [string[]]$Headings = @('N', 'E', 'S', 'W'), [string]$Out)

$root = Split-Path $PSScriptRoot -Parent
if (-not $Out) { $Out = Join-Path $root 'build\rv\dbg\own' }
$lua = Join-Path $root 'scripts\lua.ps1'
$vehicles = @('Base.Trailer54FlyingCloud22', 'Base.Trailer61Bambi16', 'Base.Trailer61Airflyte', 'Base.Trailer87Scamp13',
              'Base.Trailer87Scamp16', 'Base.87fordB700school', 'Base.87fordF700box')
[void](& $lua -Code @'
local climate = getClimateManager()
climate:stopWeatherAndThunder()
local rain = climate:getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY)
rain:setEnableAdmin(true); rain:setAdminValue(0)
getGameTime():setTimeOfDay(12)
return 1
'@)
foreach ($name in $vehicles) {
    if ($Only -and ($Only -notcontains $name)) { continue }
    foreach ($heading in $Headings) {
        Write-Host "== $name facing $heading"
        & (Join-Path $PSScriptRoot 'own_overlay.ps1') -Name $name -Heading $heading -Out $Out 2>&1 | Where-Object { $_ -like 'OWN *' }
    }
}
[void](& $lua -Code 'ISUIHandler.setVisibleAllUI(true); return 1')
Write-Host "overlays in $Out"

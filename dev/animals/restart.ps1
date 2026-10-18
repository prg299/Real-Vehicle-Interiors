# Developer helper: rebuild the add-on and restart the add-on's own test game (an instance of Real Vehicle
# Interiors' test game with its own profile and Lua port, so it never meets another agent's test games), then
# continue its latest world. Real Vehicle Interiors' package is taken as built (..\me-lens\build\rv\package).
#   .\dev\restart.ps1 [-Instance 4] [-NoBuild] [-Merged]
# -Merged: the animals are in Real Vehicle Interiors itself (since 2026-10-18): Companion Dogs only, no add-on, and
#          the main mod is built (..\me-lens\scripts\build.ps1) unless -NoBuild.
param([int]$Instance = 4, [switch]$NoBuild, [switch]$Merged = $true)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$lens = $root
$port = 18470 + 2 * ($Instance - 1)
$env:MELENS_LUA_PORT = "$port"
$env:MELENS_TEST_EXTRA = "3740052292:CompanionDogs"
$lua = Join-Path $lens 'scripts\lua.ps1'
function Lua([string]$code) { try { return ((& $lua -Code $code 2>$null) | ConvertFrom-Json).result } catch { return $null } }
function WaitFor([string]$code, [string]$match, [int]$seconds) {
    for ($i = 0; $i -lt $seconds; $i += 2) { if ((Lua $code) -match $match) { return $true }; Start-Sleep -Seconds 2 }
    return $false
}
if (-not $NoBuild) {
    $build = Join-Path $lens 'scripts\build.ps1'
    & $build | Select-Object -Last 2
}
if ((Lua 'return getPlayer() and "ingame" or "menu"') -eq 'ingame') {
    Write-Host 'Saving the test world...'
    [void](Lua 'setGameSpeed(1) getCore():quit() return 1')
    [void](WaitFor 'return (MainScreen and MainScreen.instance and not getPlayer()) and "menu" or "no"' '^menu$' 90)
}
& (Join-Path $lens 'scripts\testgame.ps1') -Instance $Instance -Mode Stop
$null = & (Join-Path $lens 'scripts\testgame.ps1') -Instance $Instance -AllowOtherGames 2>&1
if (-not (WaitFor 'return MainScreen and MainScreen.instance and "menu" or "no"' '^menu$' 180)) { throw 'Main menu did not come up' }
$saves = Join-Path $lens "build\rv\testhome$Instance\Zomboid\Saves\Sandbox"
$world = (Get-ChildItem $saves -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1).Name
[void](Lua ((Get-Content (Join-Path $lens 'dev\lua\load_world.lua') -Raw).Replace('WORLD', $world)))
if (-not (WaitFor 'local p = getPlayer() return p and "ingame" or "loading"' '^ingame$' 240)) { throw 'World did not load' }
Start-Sleep -Seconds 3
[void](Lua (Get-Content (Join-Path $lens 'dev\lua\setup.lua') -Raw))
Write-Host "Test game $Instance running world $world (Lua on $port)"

# Developer helper: restart the test game on a fresh build without losing the test save.
# Saves and quits to the main menu through the game (like its Exit button), stops the
# process, builds, launches, continues the same world and runs dev/lua/setup.lua.
#   .\dev\restart.ps1                 build and restart
#   .\dev\restart.ps1 -World name     continue another test world
#   .\dev\restart.ps1 -AllowOtherGames   launch although another project's isolated test game runs
param([string]$World = '', [switch]$NoBuild, [switch]$AllowOtherGames)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$lua = Join-Path $root 'scripts\lua.ps1'

function Lua([string]$code) {
    try { return & $lua -Code $code 2>$null } catch { return $null }
}

function WaitFor([string]$code, [string]$match, [int]$seconds) {
    for ($i = 0; $i -lt $seconds; $i += 2) {
        $r = Lua $code
        if ($r -match $match) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

$saves = Join-Path $root 'build\rv\testhome\Zomboid\Saves\Sandbox'
if (-not $World) {
    $World = (Get-ChildItem $saves -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1).Name
}

# Save and quit to the main menu, if a game is running.
$state = Lua 'return getPlayer() and "ingame" or "menu"'
if ($state -match 'ingame') {
    Write-Host 'Saving the test world...'
    Lua 'setGameSpeed(1) getCore():quit() return "quitting"' | Out-Null
    if (-not (WaitFor 'return (MainScreen and MainScreen.instance and not getPlayer()) and "menu" or "no"' '"menu"' 90)) {
        Write-Host 'Did not reach the main menu; stopping anyway.'
    }
}
& (Join-Path $root 'scripts\testgame.ps1') -Mode Stop
if (-not $NoBuild) {
    & (Join-Path $root 'scripts\build.ps1') | Select-Object -Last 3
}
$null = & (Join-Path $root 'scripts\testgame.ps1') -AllowOtherGames:$AllowOtherGames 2>&1
if (-not (WaitFor 'return MainScreen and MainScreen.instance and "menu" or "no"' '"menu"' 180)) { throw 'Main menu did not come up' }
$load = (Get-Content (Join-Path $root 'dev\lua\load_world.lua') -Raw).Replace('WORLD', $World)
Lua $load | Out-Null
if (-not (WaitFor 'local p = getPlayer() return p and "ingame" or "loading"' 'ingame' 240)) { throw 'World did not load' }
Start-Sleep -Seconds 3
Lua (Get-Content (Join-Path $root 'dev\lua\setup.lua') -Raw) | Out-Null
Write-Host "Test game running world $World"

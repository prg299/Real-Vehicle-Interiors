# Developer helper: save the test world and close the test game (like its Exit button), so no
# idle game window is left lying around between rounds.
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$lua = Join-Path $root 'scripts\lua.ps1'

function Lua([string]$code) {
    try { return & $lua -Code $code 2>$null } catch { return $null }
}

if ((Lua 'return getPlayer() and "ingame" or "menu"') -match 'ingame') {
    Lua 'setGameSpeed(1) getCore():quit() return "quitting"' | Out-Null
    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 2
        if ((Lua 'return (MainScreen and MainScreen.instance and not getPlayer()) and "menu" or "no"') -match '"menu"') { break }
    }
}
& (Join-Path $root 'scripts\testgame.ps1') -Mode Stop

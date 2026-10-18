# Developer helper: from a just-launched test game (scripts\testgame.ps1), start a fresh
# sandbox world and get it ready for vehicle tests: noon, no debug console, camera
# zoomed in (0.5) and the player on open ground (dev\lua\find_open.lua, 16 x 10).
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'

function Wait-Lua([string]$check, [int]$seconds = 360) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $result = & $lua -Code $check 2>$null
            if ($result -match 'READY') { return }
        } catch { }
        Start-Sleep -Seconds 3
    }
    throw "timeout waiting for: $check"
}

Wait-Lua 'return MainScreen and MainScreen.instance and MainScreen.instance:isVisible() and "READY" or "wait"'
& $lua -File (Join-Path $root 'dev\lua\newgame.lua')
Start-Sleep -Seconds 5
Wait-Lua 'local p = getPlayer(); return p and p:getCurrentSquare() and MainScreen.instance and not MainScreen.instance:isVisible() and "READY" or "wait"'
Start-Sleep -Seconds 3
& $lua -File (Join-Path $root 'dev\lua\setup.lua')
# the debug console off; two zoom steps in from the default 1.0 give 0.5
& $lua -Code 'local c = UIManager.getDebugConsole and UIManager.getDebugConsole(); if c then c:setVisible(false) end; getCore():doZoomScroll(0, -1); getCore():doZoomScroll(0, -1); return "console hidden, zooming in"'
$find = (Get-Content -LiteralPath (Join-Path $root 'dev\lua\find_open.lua') -Raw).Replace('tonumber("W")', 'tonumber("16")').Replace('tonumber("H")', 'tonumber("10")').Replace('local R = 70', 'local R = 40')
& $lua -Code $find

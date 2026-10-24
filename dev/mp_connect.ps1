# Developer helper: connect the running test game (scripts\testgame.ps1) to the local test server
# (dev\mp_server.ps1) as its admin account, clicking through spawn and character screens for a new
# character, and return once in the game. Leaves a single-player world first.
#   .\dev\mp_connect.ps1 [-Port 17361]
# -User and -Password connect as another player (the server makes the account on the first login);
# -LuaPort drives another game than the first one (dev\second_client.ps1 does both for the second player).
param([int]$Port = 17361, [string]$User = 'MELensAdmin', [string]$Password = '', [int]$LuaPort = 0,
    [int]$OwnedClientPid = 0, [long]$OwnedClientStartTicks = 0,
    [int]$OwnedServerPid = 0, [long]$OwnedServerStartTicks = 0, [string]$OwnedServerConsole,
    [int]$ConnectSeconds = 180)
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
if ($LuaPort) { $env:MELENS_LUA_PORT = "$LuaPort" }
function Assert-OwnedConnectionProcesses {
    foreach ($identity in @(@($OwnedClientPid, $OwnedClientStartTicks, 'client'), @($OwnedServerPid, $OwnedServerStartTicks, 'server'))) {
        if (-not $identity[0]) { continue }
        $process = Get-Process -Id $identity[0] -ErrorAction SilentlyContinue
        if (-not $process -or $process.StartTime.ToUniversalTime().Ticks -ne $identity[1] -or $process.HasExited) { throw "Owned $($identity[2]) exited during connection; no unrelated PID will be touched" }
    }
    if ($OwnedServerConsole -and (Test-Path -LiteralPath $OwnedServerConsole)) {
        if (Select-String -LiteralPath $OwnedServerConsole -Pattern 'OutOfMemoryError|Exception in thread "main"' -Quiet) { throw 'Owned server has a fatal heap/main-thread error; connection aborted' }
    }
}
function Lua([string]$code, [string]$label = 'connection probe') {
    Assert-OwnedConnectionProcesses
    $targetPort = if ($LuaPort) { $LuaPort } elseif ($env:MELENS_LUA_PORT) { [int]$env:MELENS_LUA_PORT } else { 18470 }
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$targetPort/lua?depth=8&sandbox=false" -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($code)) -ContentType 'text/plain' -TimeoutSec 5
        $decoded = $response.Content | ConvertFrom-Json
    } catch { Assert-OwnedConnectionProcesses; return $null }
    if (-not $decoded.ok) { throw "MP setup Lua failed during ${label}: $($decoded.error)" }
    return $decoded.result
}

if ((Lua 'return isIngameState() and getPlayer() and "ingame" or "menu"') -eq 'ingame') {
    if ((Lua 'return tostring(isClient())') -eq 'true') { Write-Host 'already connected'; return }
    Lua 'setGameSpeed(1) getCore():quit() return 1' | Out-Null
    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 2
        if ((Lua 'return (MainScreen and MainScreen.instance and not getPlayer()) and "menu" or "no"') -eq 'menu') { break }
    }
}
if (-not $Password) {
    $Password = (Get-Content (Join-Path $root 'build\rv\mphome\server\admin-password.txt') -Raw).Trim()
}
Lua ("serverConnect('$User', '" + $Password + "', '127.0.0.1', '127.0.0.1', '$Port', '', 'melens', false, true, 1, '') return 1") 'server connection' | Out-Null
$connectDeadline = [DateTime]::UtcNow.AddSeconds($ConnectSeconds)
for ($i = 0; $i -lt 90 -and [DateTime]::UtcNow -lt $connectDeadline; $i++) {
    Assert-OwnedConnectionProcesses
    Start-Sleep -Seconds 2
    $state = Lua -label 'connection screens' -code @'
if isIngameState() and getPlayer() then return "ingame" end
-- The engine creates a placeholder player before world streaming completes.
-- It cannot establish readiness or safely receive the world setup fixture.
if getPlayer() then return "loading" end
if MapSpawnSelect and MapSpawnSelect.instance and MapSpawnSelect.instance:isReallyVisible() then MapSpawnSelect.instance:clickNext() return "spawn" end
if CharacterCreationProfession and CharacterCreationProfession.instance and CharacterCreationProfession.instance:isReallyVisible() then
    CharacterCreationProfession.instance:onOptionMouseDown({ internal = "NEXT" }, 0, 0) return "profession" end
if CharacterCreationMain and CharacterCreationMain.instance and CharacterCreationMain.instance:isReallyVisible() then
    CharacterCreationMain.instance:onOptionMouseDown({ internal = "NEXT" }, 0, 0) return "character" end
return "waiting"
'@
    if ($state -eq 'ingame') { break }
}
if ($state -ne 'ingame') { throw 'Owned MP client never reached IngameState before its connection deadline' }
Start-Sleep -Seconds 3
Lua (Get-Content (Join-Path $root 'dev\lua\setup.lua') -Raw) 'world setup' | Out-Null
Write-Host ("connected: " + (Lua 'local p = getPlayer() return p and (p:getUsername() .. " client=" .. tostring(isClient()) .. " " .. p:getAccessLevel()) or "not in game"'))

# Developer helper: a second test game, a second player, on the local test server. Starts it beside the first one
# (scripts\testgame.ps1 -Instance 2: its own profile build\rv\testhome2, Lua endpoint 18472) and connects it as
# MELensGuest through the character screens (dev\mp_connect.ps1). The server (dev\mp_server.ps1) runs and the first
# game is connected already; dev\mp_two.ps1 then tests the two players in one camper.
#   .\dev\second_client.ps1            start and connect
#   .\dev\second_client.ps1 -Stop      close it
param([switch]$Stop, [int]$Port = 17361)
$root = Split-Path $PSScriptRoot -Parent
if ($Stop) {
    & (Join-Path $root 'scripts\testgame.ps1') -Mode Stop -Instance 2
    return
}
# The dependencies are the first game's copies (not the Workshop's newer ones): a player who is not an admin is kicked
# when the Lua and script checksums of the server and of the client differ.
$mods2 = Join-Path $root 'build\rv\testhome2\Zomboid\mods'
New-Item -ItemType Directory -Force -Path $mods2 | Out-Null
foreach ($dep in 'ZombieBuddy', 'damnlib', 'KI5campers', '87fordB700', 'KI5trailers') {
    $from = Join-Path $root "build\rv\testhome\Zomboid\mods\$dep"
    $to = Join-Path $mods2 $dep
    if ((Test-Path -LiteralPath $from) -and -not (Test-Path -LiteralPath $to)) { Copy-Item -LiteralPath $from -Destination $mods2 -Recurse }
}
# (without -debug: a server only lets a debug-mode game in if the player's role may connect with debug, the
# admin's does and a normal player's does not)
& (Join-Path $root 'scripts\testgame.ps1') -Instance 2 -AllowOtherGames -NoDebug
# the endpoint answers once the game has loaded its mods; the connect screen needs the main menu
$lua = Join-Path $root 'scripts\lua.ps1'
$menu = $false
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = (& $lua -Code 'return (MainScreen and MainScreen.instance and not getPlayer()) and "menu" or "loading"' -Port 18472 2>$null | ConvertFrom-Json).result
        if ($r -eq 'menu') { $menu = $true; break }
    } catch { }
}
if (-not $menu) { throw 'The second game did not reach its main menu.' }
Start-Sleep -Seconds 3
& (Join-Path $PSScriptRoot 'mp_connect.ps1') -Port $Port -User 'MELensGuest' -Password 'guest-pass-1' -LuaPort 18472

# Developer helper: a disposable local dedicated server for multiplayer tests (non-Steam, 127.0.0.1 only),
# in build\rv\mphome\server with its own cache folder, save and mods (copied from the test profile, so run
# scripts\testgame.ps1 or dev\restart.ps1 once after a build first). ME: LENS' Java part only draws on clients;
# the server needs its Lua and scripts (the multiplayer checksum covers them). By default the server still runs
# ZombieBuddy for the developer spawn helper; -NoJava (below) is the server players actually run.
#   .\dev\mp_server.ps1               start (returns when the server reports SERVER STARTED)
#   .\dev\mp_server.ps1 -Stop         stop it (quit command, then the process)
#   .\dev\mp_server.ps1 -Fresh        start with a new world (the old one is deleted)
#   .\dev\mp_server.ps1 -NoJava       start without ZombieBuddy's Java agent, like a hosted (coop) or ordinary dedicated
#                                     server: MELensRV is nil there. The developer 'spawn' command needs the agent, so
#                                     tests spawn with the game's /addvehicle command instead (dev\mp_spawn.ps1).
#   .\dev\mp_server.ps1 -NoLensJar    ZombieBuddy stays (for the developer spawn helper, which can place a camper in
#                                     town where /addvehicle cannot), but the server's copy of ME: LENS has no Java
#                                     part, so MELensRV is nil there as on players' servers.
# The admin account MELensAdmin gets a random password kept in build\rv\mphome\server\admin-password.txt.
param([switch]$Stop, [switch]$Fresh, [switch]$NoJava, [switch]$NoLensJar, [int]$Port = 17361)

. (Join-Path $PSScriptRoot '..\scripts\common.ps1')
$home_ = Join-Path $Lens.Out 'mphome\server'
$zomboid = Join-Path $home_ 'Zomboid'
$pidFile = Join-Path $home_ 'server.pid'
$name = 'melens'

if ($Stop) {
    if (Test-Path -LiteralPath $pidFile) {
        $id = [int](Get-Content -LiteralPath $pidFile)
        $p = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($p) { Stop-Process -Id $id -Force; Write-Host "Stopped server $id" }
        Remove-Item -LiteralPath $pidFile
    } else { Write-Host 'No server recorded.' }
    return
}

# mods: the test profile's copies (dependencies, the built package, the developer endpoint)
$clientMods = Join-Path $Lens.TestHome 'Zomboid\mods'
if (-not (Test-Path -LiteralPath (Join-Path $clientMods 'RealVehicleInteriors'))) { throw 'Run the test game once first (it copies the mods).' }
$mods = Join-Path $zomboid 'mods'
if (Test-Path -LiteralPath $mods) { Remove-Item -LiteralPath $mods -Recurse -Force }
New-Item -ItemType Directory -Force -Path $mods, (Join-Path $zomboid 'Server') | Out-Null
# (the same set as the test game's, KI5 Trailers included: a player who is not an admin is kicked when the Lua and script
# checksums of the server and of the client differ)
foreach ($m in 'ZombieBuddy', 'damnlib', 'KI5campers', '87fordB700', 'KI5trailers', 'RealVehicleInteriors', 'RealVehicleInteriors_Dev') {
    Copy-Item -LiteralPath (Join-Path $clientMods $m) -Destination $mods -Recurse
}
if ($NoLensJar) {
    Get-ChildItem -LiteralPath (Join-Path $mods 'RealVehicleInteriors') -Recurse -Filter 'RealVehicleInteriors.jar' | Remove-Item
    Write-Host 'Server copy of ME: LENS without its Java part (MELensRV is nil on the server)'
}

# settings: written only the first time (the server fills in the rest of its options itself)
$ini = Join-Path $zomboid "Server\$name.ini"
if (-not (Test-Path -LiteralPath $ini)) {
    $text = @"
Open=true
Public=false
PVP=false
PauseEmpty=true
DefaultPort=$Port
UDPPort=$($Port + 1)
Mods=ZombieBuddy;damnlib;KI5campers;87fordB700;KI5trailers;RealVehicleInteriors;RealVehicleInteriors_Dev
WorkshopItems=
Map=Muldraugh, KY
SteamVAC=false
"@
    [IO.File]::WriteAllText($ini, $text, [Text.UTF8Encoding]::new($false))
}
# the mod list is kept up to date every start (a server made before the rename to RealVehicleInteriors still listed
# ME_LENS and ran without the mod)
$wantedMods = 'ZombieBuddy;damnlib;KI5campers;87fordB700;KI5trailers;RealVehicleInteriors;RealVehicleInteriors_Dev'
$iniText = Get-Content -LiteralPath $ini -Raw
if ($iniText -match '(?m)^Mods=(.*)$' -and $Matches[1].Trim() -ne $wantedMods) {
    $iniText = [regex]::Replace($iniText, '(?m)^Mods=.*$', "Mods=$wantedMods")
    [IO.File]::WriteAllText($ini, $iniText, [Text.UTF8Encoding]::new($false))
    Write-Host 'Server ini: mod list updated'
}
# The checksum kick is off for this disposable test server: a second game that is not an admin was refused although its
# mod files are byte for byte the server's (the game's checksum covers more than the mods, and the test games run with
# the optimization agent and developer endpoint). The admin is never checked, which is why one game worked all along.
$iniNow = Get-Content -LiteralPath $ini -Raw
$iniNew = [regex]::Replace($iniNow, '(?m)^DoLuaChecksum=.*$', 'DoLuaChecksum=false')
$iniNew = [regex]::Replace($iniNew, '(?m)^AntiCheatChecksum=.*$', 'AntiCheatChecksum=4')       # 4: disabled (1 ban, 2 kick, 3 record)
if ($iniNew -ne $iniNow) {
    [IO.File]::WriteAllText($ini, $iniNew, [Text.UTF8Encoding]::new($false))
    Write-Host 'Server ini: Lua checksum check off'
}
# no zombies: they mob the test character at the spawn (a hit reaction stops a walk-in, and the client cannot
# remove a server's zombies as the single-player test setup does)
$sandbox = Join-Path $zomboid "Server\${name}_SandboxVars.lua"
if (-not (Test-Path -LiteralPath $sandbox)) {
    [IO.File]::WriteAllText($sandbox, "SandboxVars = {`n    VERSION = 6,`n    Zombies = 6,`n}`n", [Text.UTF8Encoding]::new($false))
} else {
    $sandboxText = Get-Content -LiteralPath $sandbox -Raw
    if ($sandboxText -match '(?m)^    Zombies = (\d+),') {
        if ($Matches[1] -ne '6') {
            [IO.File]::WriteAllText($sandbox, [regex]::Replace($sandboxText, '(?m)^    Zombies = \d+,', '    Zombies = 6,'), [Text.UTF8Encoding]::new($false))
            Write-Host 'Server sandbox: no zombies'
        }
    }
}
# -Fresh: a new world (the saved one remembers the items of the mods it was made with)
if ($Fresh) {
    $world = Join-Path $zomboid "Saves\Multiplayer\$name"
    if (Test-Path -LiteralPath $world) { Remove-Item -LiteralPath $world -Recurse -Force; Write-Host 'Server world deleted' }
}
$passwordPath = Join-Path $home_ 'admin-password.txt'
if (-not (Test-Path -LiteralPath $passwordPath)) {
    [IO.File]::WriteAllText($passwordPath, [guid]::NewGuid().ToString('N'), [Text.UTF8Encoding]::new($false))
}

$game = $Lens.GameRoot
# ZombieBuddy on the server too, for the developer endpoint's spawn helper (dev\java\me\lens\dev\Spawn.java).
# ME: LENS' own Java draws nothing on a server, but it defines MELensRV there, which a hosted or ordinary dedicated
# server does not have (2.0.2: the parts declared with MELensRV differed, see MELens_Parts.lua extendScript); -NoJava
# runs the server as those do. The endpoint itself listens on another port than the client's.
$zbConfig = Join-Path $home_ 'zombie_buddy'
New-Item -ItemType Directory -Force -Path $zbConfig | Out-Null
$agent = if ($NoJava) { @() } else { @("-agentlib:zbNative=policy=allow-all,verbosity=1,config_dir=$zbConfig", '-Dmelens.dev.port=18471') }
$args_ = @('-Xms2g', '-Xmx4g') + $agent + @("-Djava.library.path=$game\natives;$game\natives\win64;$game", '-Dzomboid.steam=0',
    "-Duser.home=$home_", "-Ddeployment.user.cachedir=$zomboid",
    '-Dpzopt.aotCache=false', '-Dpzopt.gcMode=stock', '-Dpzopt.jitSteady=false', '-Dpzopt.updateCheck=false', '-Dpzopt.updatePrefetch=false',
    '-cp', "$game\projectzomboid.jar;$game", 'zombie.network.GameServer', "-cachedir=$zomboid", '-nosteam',
    '-servername', $name, '-ip', '127.0.0.1', '-port', "$Port", '-udpport', "$($Port + 1)",
    '-adminusername', 'MELensAdmin', '-adminpassword', (Get-Content -LiteralPath $passwordPath -Raw).Trim())
$psi = [Diagnostics.ProcessStartInfo]::new((Join-Path $game 'jre64\bin\java.exe'))
$psi.WorkingDirectory = $game
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
foreach ($a in $args_) { [void]$psi.ArgumentList.Add($a) }
foreach ($key in 'JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS') { [void]$psi.Environment.Remove($key) }
$psi.Environment['PATH'] = "$game;$game\jre64\bin;$env:PATH"
$console = Join-Path $zomboid 'server-console.txt'
if (Test-Path -LiteralPath $console) { Remove-Item -LiteralPath $console }
$process = [Diagnostics.Process]::Start($psi)
# drain the redirected output so the server never blocks on a full pipe
$null = $process.StandardOutput.ReadToEndAsync()
$null = $process.StandardError.ReadToEndAsync()
Set-Content -LiteralPath $pidFile -Value $process.Id
Write-Host "Server starting, PID $($process.Id), port $Port"
for ($i = 0; $i -lt 300; $i += 2) {
    Start-Sleep -Seconds 2
    if ($process.HasExited) { throw "Server exited (code $($process.ExitCode)); see $console" }
    if ((Test-Path -LiteralPath $console) -and (Select-String -LiteralPath $console -Pattern 'SERVER STARTED' -Quiet)) {
        Write-Host 'SERVER STARTED'
        return
    }
}
throw "Server did not start in time; see $console"

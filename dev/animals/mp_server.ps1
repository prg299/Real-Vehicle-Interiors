# Developer helper: the add-on's own disposable local dedicated server (non-Steam, 127.0.0.1 only), the same as
# Real Vehicle Interiors' dev\mp_server.ps1 but in this project's build\mp\server, on its own ports (game 17391/17392,
# server Lua endpoint 18479), so it never meets another agent's test server; its mods are copied from the add-on's
# test game profile (testhome4, run dev\restart.ps1 once after a build first): Real Vehicle Interiors, Companion Dogs
# and this add-on. The add-on's Java part only draws on clients.
#   .\dev\mp_server.ps1               start (returns when the server reports SERVER STARTED)
#   .\dev\mp_server.ps1 -Stop         stop it
#   .\dev\mp_server.ps1 -Fresh        start with a new world
#   .\dev\mp_server.ps1 -NoJava       start without ZombieBuddy, as a hosted or ordinary dedicated server
# The admin account MELensAdmin gets a random password kept in build\mp\server\admin-password.txt.
param([switch]$Stop, [switch]$Fresh, [switch]$NoJava, [int]$Port = 17391, [int]$DevPort = 18479, [int]$Instance = 4)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
. (Join-Path $root 'scripts\common.ps1')
$home_ = Join-Path $root 'build\animals\mp\server'
$zomboid = Join-Path $home_ 'Zomboid'
$pidFile = Join-Path $home_ 'server.pid'
$name = 'melensanimals'

if ($Stop) {
    if (Test-Path -LiteralPath $pidFile) {
        $id = [int](Get-Content -LiteralPath $pidFile)
        $p = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($p) { Stop-Process -Id $id -Force; Write-Host "Stopped server $id" }
        Remove-Item -LiteralPath $pidFile
    } else { Write-Host 'No server recorded.' }
    return
}

$clientMods = Join-Path $root "build\rv\testhome$Instance\Zomboid\mods"
if (-not (Test-Path -LiteralPath (Join-Path $clientMods 'RealVehicleInteriors'))) { throw 'Run dev\restart.ps1 once first (it copies the mods).' }
$mods = Join-Path $zomboid 'mods'
if (Test-Path -LiteralPath $mods) { Remove-Item -LiteralPath $mods -Recurse -Force }
New-Item -ItemType Directory -Force -Path $mods, (Join-Path $zomboid 'Server') | Out-Null
$modIds = 'ZombieBuddy', 'damnlib', 'KI5campers', '87fordB700', 'KI5trailers', 'RealVehicleInteriors', 'CompanionDogs', 'RealVehicleInteriors_Dev'
foreach ($m in $modIds) {
    Copy-Item -LiteralPath (Join-Path $clientMods $m) -Destination $mods -Recurse
}
$wantedMods = $modIds -join ';'

$ini = Join-Path $zomboid "Server\$name.ini"
if (-not (Test-Path -LiteralPath $ini)) {
    $text = @"
Open=true
Public=false
PVP=false
PauseEmpty=true
DefaultPort=$Port
UDPPort=$($Port + 1)
Mods=$wantedMods
WorkshopItems=
Map=Muldraugh, KY
SteamVAC=false
"@
    [IO.File]::WriteAllText($ini, $text, [Text.UTF8Encoding]::new($false))
}
$iniText = Get-Content -LiteralPath $ini -Raw
$iniNew = [regex]::Replace($iniText, '(?m)^Mods=.*$', "Mods=$wantedMods")
# a disposable test server: the checksum kick off (see Real Vehicle Interiors' dev\mp_server.ps1)
$iniNew = [regex]::Replace($iniNew, '(?m)^DoLuaChecksum=.*$', 'DoLuaChecksum=false')
$iniNew = [regex]::Replace($iniNew, '(?m)^AntiCheatChecksum=.*$', 'AntiCheatChecksum=4')
if ($iniNew -ne $iniText) { [IO.File]::WriteAllText($ini, $iniNew, [Text.UTF8Encoding]::new($false)) }
# no zombies at the test spawn
$sandbox = Join-Path $zomboid "Server\${name}_SandboxVars.lua"
if (-not (Test-Path -LiteralPath $sandbox)) {
    [IO.File]::WriteAllText($sandbox, "SandboxVars = {`n    VERSION = 6,`n    Zombies = 6,`n}`n", [Text.UTF8Encoding]::new($false))
}
if ($Fresh) {
    $world = Join-Path $zomboid "Saves\Multiplayer\$name"
    if (Test-Path -LiteralPath $world) { Remove-Item -LiteralPath $world -Recurse -Force; Write-Host 'Server world deleted' }
}
$passwordPath = Join-Path $home_ 'admin-password.txt'
if (-not (Test-Path -LiteralPath $passwordPath)) {
    [IO.File]::WriteAllText($passwordPath, [guid]::NewGuid().ToString('N'), [Text.UTF8Encoding]::new($false))
}

$game = $Lens.GameRoot
$zbConfig = Join-Path $home_ 'zombie_buddy'
New-Item -ItemType Directory -Force -Path $zbConfig | Out-Null
$agent = if ($NoJava) { @() } else { @("-agentlib:zbNative=policy=allow-all,verbosity=1,config_dir=$zbConfig", "-Dmelens.dev.port=$DevPort") }
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

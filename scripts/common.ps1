# Shared build and isolated-test configuration. No game or JDK is distributed.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Lens = [ordered]@{
    Root = $root
    GameRoot = if ($env:PZ_GAME_DIR) { $env:PZ_GAME_DIR } else { 'C:\SteamLibrary\steamapps\common\ProjectZomboid' }
    Workshop = if ($env:PZ_WORKSHOP_DIR) { $env:PZ_WORKSHOP_DIR } else { 'C:\SteamLibrary\steamapps\workshop\content\108600' }
    UserMods = Join-Path $env:USERPROFILE 'Zomboid\mods'
    Archive = Join-Path $env:USERPROFILE 'Zomboid\RealVehicleInteriors-archive'
    LuaPort = 18470
    Jdk = $null
}
if ($env:RVI_JAVA_HOME) { $Lens.Jdk = Join-Path $env:RVI_JAVA_HOME 'bin' }
elseif ($env:JAVA_HOME) { $Lens.Jdk = Join-Path $env:JAVA_HOME 'bin' }
else {
    $javacCommand = Get-Command javac -ErrorAction SilentlyContinue
    if ($javacCommand) { $Lens.Jdk = Split-Path $javacCommand.Source }
}
$localSettings = Join-Path $root '.local\settings.ps1'
if (Test-Path -LiteralPath $localSettings) { . $localSettings }
if (-not $Lens.Jdk) { throw 'Install JDK 25 and set RVI_JAVA_HOME or JAVA_HOME (the JDK root, without bin).' }
$Lens.Out = Join-Path $root 'build\rv'
$Lens.Package = Join-Path $Lens.Out 'package\RealVehicleInteriors'
$Lens.TestHome = Join-Path $Lens.Out 'testhome'
$Lens.Dependencies = @(
    @{ Id = 'ZombieBuddy'; Item = '3619862853'; Folder = 'ZombieBuddy' },
    @{ Id = 'damnlib'; Item = '3171167894'; Folder = 'damnlib' },
    @{ Id = 'KI5campers'; Item = '3670064951'; Folder = 'KI5campers' },
    @{ Id = '87fordB700'; Item = '3110911330'; Folder = '87fordB700' },
    # Test-only: unsupported small trailers must keep their original behavior.
    @{ Id = 'KI5trailers'; Item = '3330403100'; Folder = 'KI5trailers' }
)
function Get-LensGameProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'ProjectZomboid64.exe' -or
        ($_.Name -eq 'java.exe' -and $_.CommandLine -match 'zombie\.gameStates\.MainScreenState')
    }
}
function Get-LensPython {
    if ($env:RVI_PYTHON) { return (Get-Command $env:RVI_PYTHON -ErrorAction Stop).Source }
    # WindowsApps aliases can broker a process outside the caller's resource job.
    # Resolve the real interpreter before starting a long-lived native keeper.
    $command = (Get-Command python -ErrorAction Stop).Source
    $resolved = (& $command -c 'import sys; print(sys.executable)').Trim()
    if ($LASTEXITCODE -or -not (Test-Path -LiteralPath $resolved -PathType Leaf)) { throw 'Cannot resolve Python interpreter' }
    return $resolved
}

# Developer test run in a disposable profile under build\rv\testhome.
#   .\scripts\testgame.ps1 -Mode Prepare   refresh the test profile only
#   .\scripts\testgame.ps1                 prepare and launch (windowed, -debug)
#   .\scripts\testgame.ps1 -Mode Stop      close the test game
#   .\scripts\testgame.ps1 -Instance 2 -AllowOtherGames    a second game (build\rv\testhome2, Lua on 18472), for two
#                                           players on the test server (dev\second_client.ps1)
#
# The profile has its own Zomboid folder (-cachedir) and ZombieBuddy config. In
# RVI_TEST_CORE_ONLY=1 mode it enables only ZombieBuddy, Real Vehicle Interiors and
# the developer-only RealVehicleInteriors_Dev endpoint (Lua on 127.0.0.1). The
# default fleet profile also enables damnlib, KI5 Campers, the B700 bus and KI5 Trailers, whose
# cargo trailers Real Vehicle Interiors leaves as KI5 made them (too small to walk into): loaded to check that. Your real
# saves, mod list and ZombieBuddy approvals are never read or written. Because the
# profile is isolated, ZombieBuddy runs with policy=allow-all here.
param(
    [ValidateSet('Prepare', 'Launch', 'Stop')][string]$Mode = 'Launch',
    [switch]$Stock,        # run with the stock game classes first (no optimization overrides)
    [switch]$NoDebug,
    [switch]$AllowOtherGames,   # launch although another project's isolated test game runs (never next to the real game)
    [int]$Instance = 1,          # 2: a second game beside the first, with its own profile folder and Lua endpoint
    [string]$ProfilePath        # optional run-owned profile inside build/rv
)

. (Join-Path $PSScriptRoot 'common.ps1')
if ($ProfilePath) {
    $profile = [IO.Path]::GetFullPath($ProfilePath)
    if (-not $profile.StartsWith($Lens.Out + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Test profiles must stay inside build/rv'
    }
    $Lens.TestHome = $profile
}
if ($Instance -gt 1) {
    $Lens.TestHome = $Lens.TestHome + $Instance
    $Lens.LuaPort = $Lens.LuaPort + 2 * ($Instance - 1)
}

$testHome = $Lens.TestHome
$zomboid = Join-Path $testHome 'Zomboid'
$mods = Join-Path $zomboid 'mods'
$zbConfig = Join-Path $testHome 'zombie_buddy'
$pidFile = Join-Path $testHome 'game.pid'

function Set-IniValue([string[]]$lines, [string]$key, [string]$value) {
    $found = $false
    $result = foreach ($line in $lines) {
        if ($line -match ('^' + [regex]::Escape($key) + '=')) { $found = $true; "$key=$value" } else { $line }
    }
    if (-not $found) { $result = @($result) + "$key=$value" }
    return $result
}

function Initialize-TestHome {
    if (-not (Test-Path -LiteralPath (Join-Path $Lens.Package '42.21\media\java\RealVehicleInteriors.jar'))) {
        throw 'Build first: .\scripts\build.ps1'
    }
    New-Item -ItemType Directory -Force -Path $mods, $zbConfig | Out-Null
    foreach ($dep in $Lens.Dependencies) {
        $target = Join-Path $mods $dep.Folder
        if (-not (Test-Path -LiteralPath $target)) {
            $source = Join-Path $Lens.Workshop (Join-Path $dep.Item (Join-Path 'mods' $dep.Folder))
            if (-not (Test-Path -LiteralPath $source)) { throw "Dependency $($dep.Id) is not downloaded: $source" }
            Copy-Item -LiteralPath $source -Destination $target -Recurse
        }
    }
    # Extra mods for a test, opt-in: MELENS_TEST_EXTRA = "item:folder;...;@C:\path\to\ModFolder" (a folder's name is
    # its mod id), e.g. "3740052292:CompanionDogs". Workshop ones are copied from the download (read-only) like the
    # dependencies; a local folder (@...) is copied fresh every launch (an add-on in development).
    $extraMods = @()
    foreach ($pair in @(($env:MELENS_TEST_EXTRA -split ';') | Where-Object { $_ })) {
        if ($pair.StartsWith('@')) {
            $local = $pair.Substring(1)
            if (-not (Test-Path -LiteralPath $local)) { throw "Extra mod folder not found: $local" }
            $folder = Split-Path $local -Leaf
            $target = Join-Path $mods $folder
            if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
            Copy-Item -LiteralPath $local -Destination $target -Recurse
            $extraMods += $folder
            continue
        }
        $item, $folder = $pair -split ':'
        $target = Join-Path $mods $folder
        if (-not (Test-Path -LiteralPath $target)) {
            $source = Join-Path $Lens.Workshop (Join-Path $item (Join-Path 'mods' $folder))
            if (-not (Test-Path -LiteralPath $source)) { throw "Extra mod $folder is not downloaded: $source" }
            Copy-Item -LiteralPath $source -Destination $target -Recurse
        }
        $extraMods += $folder
    }
    $installed = Join-Path $mods 'RealVehicleInteriors'
    if (Test-Path -LiteralPath $installed) { Remove-Item -LiteralPath $installed -Recurse -Force }
    Copy-Item -LiteralPath $Lens.Package -Destination $mods -Recurse

    # Developer-only endpoint mod: compiled here, installed only into this profile.
    $devSource = Join-Path $Lens.Root 'dev\RealVehicleInteriors_Dev'
    $devTarget = Join-Path $mods 'RealVehicleInteriors_Dev'
    $devClasses = Join-Path $Lens.Out 'dev-classes'
    if (Test-Path -LiteralPath $devClasses) { Remove-Item -LiteralPath $devClasses -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $devClasses | Out-Null
    $gameJar = Join-Path $Lens.GameRoot 'projectzomboid.jar'
    $buddyJar = Join-Path $Lens.GameRoot 'ZombieBuddy.jar'
    $devSources = @(Get-ChildItem -LiteralPath (Join-Path $Lens.Root 'dev\java') -Recurse -Filter *.java | ForEach-Object FullName)
    & (Join-Path $Lens.Jdk 'javac.exe') --release 25 -Xlint:-options -d $devClasses -cp "$gameJar;$buddyJar" @devSources
    if ($LASTEXITCODE) { throw 'dev endpoint compile failed' }
    if (Test-Path -LiteralPath $devTarget) { Remove-Item -LiteralPath $devTarget -Recurse -Force }
    Copy-Item -LiteralPath $devSource -Destination $mods -Recurse
    $devJarDir = Join-Path $devTarget '42.21\media\java'
    New-Item -ItemType Directory -Force -Path $devJarDir | Out-Null
    & (Join-Path $Lens.Jdk 'jar.exe') --create --file (Join-Path $devJarDir 'RealVehicleInteriors_Dev.jar') -C $devClasses .
    if ($LASTEXITCODE) { throw 'dev endpoint jar failed' }

    # (a profile the game has not started in yet resets its mod list to empty unless this marker file exists)
    $resetMarker = Join-Path $mods 'reset-mods-42_00.txt'
    if (-not (Test-Path -LiteralPath $resetMarker)) {
        [IO.File]::WriteAllText($resetMarker, 'If this file does not exist, default.txt will be reset to empty (no mods active).', [Text.UTF8Encoding]::new($false))
    }
    $extraLines = ($extraMods | ForEach-Object { "    mod = $_,`n" }) -join ''
    $dependencyLines = ($Lens.Dependencies | ForEach-Object { "    mod = $($_.Id),`n" }) -join ''
    $modList = "VERSION = 1,`nmods`n{`n${dependencyLines}    mod = RealVehicleInteriors,`n$extraLines    mod = RealVehicleInteriors_Dev,`n}`nmaps`n{`n}`n"
    [IO.File]::WriteAllText((Join-Path $mods 'default.txt'), $modList, [Text.UTF8Encoding]::new($false))

    # Start from the user's graphics options (read-only copy), but windowed.
    $userOptions = Join-Path $env:USERPROFILE 'Zomboid\options.ini'
    $lines = if (Test-Path -LiteralPath $userOptions) { Get-Content -LiteralPath $userOptions } else { @('version=8') }
    $lines = Set-IniValue $lines 'fullScreen' 'false'
    $lines = Set-IniValue $lines 'borderless' 'false'
    $lines = Set-IniValue $lines 'width' '1280'
    $lines = Set-IniValue $lines 'height' '720'
    $lines = Set-IniValue $lines 'focusloss' 'false'   # keep running while scripts drive it
    [IO.File]::WriteAllLines((Join-Path $zomboid 'options.ini'), [string[]]$lines, [Text.UTF8Encoding]::new($false))

    $userOpt = Join-Path $env:USERPROFILE 'Zomboid\pzopt\options.ini'
    if (Test-Path -LiteralPath $userOpt) {
        New-Item -ItemType Directory -Force -Path (Join-Path $zomboid 'pzopt') | Out-Null
        Copy-Item -LiteralPath $userOpt -Destination (Join-Path $zomboid 'pzopt\options.ini') -Force
    }
    Write-Host "Test profile ready: $testHome"
}

function Start-TestGame {
    $running = @(Get-LensGameProcesses)
    if ($running.Count -gt 0) {
        # -AllowOtherGames (when the project owner says not to wait): only games whose own -cachedir is inside this
        # workspace (another project's isolated test profile) may run alongside; the real game never.
        $workspace = (Resolve-Path (Join-Path $Lens.Root '..\..\..\..')).Path
        $foreign = @($running | Where-Object { $_.CommandLine -notlike "*-cachedir=$workspace*" })
        if (-not $AllowOtherGames -or $foreign.Count -gt 0) { throw 'Project Zomboid is already running.' }
        Write-Host "Another project's test game runs (PID $($running.ProcessId -join ', ')); starting beside it (RAM is shared)."
    }
    Initialize-TestHome
    $config = Get-Content -LiteralPath (Join-Path $Lens.GameRoot 'ProjectZomboid64.json') -Raw | ConvertFrom-Json
    $vmArgs = [Collections.Generic.List[string]]::new()
    foreach ($arg in $config.vmArgs) {
        if ($arg -notmatch '^-javaagent:|^-agentlib:|^-Duser\.home=|^-Dzomboid\.steam=') { $vmArgs.Add($arg) }
    }
    if ($config.windows.'10.0.17134') { foreach ($arg in $config.windows.'10.0.17134'.vmArgs) { $vmArgs.Add($arg) } }
    $vmArgs.Add('-Dzomboid.steam=0')
    $vmArgs.Add("-Duser.home=$testHome")
    # Keep the optimization mod from rewriting launcher files or updating during tests.
    foreach ($arg in @('-Dpzopt.aotCache=false', '-Dpzopt.gcMode=stock', '-Dpzopt.jitSteady=false', '-Dpzopt.updateCheck=false', '-Dpzopt.updatePrefetch=false')) { $vmArgs.Add($arg) }
    if ($Stock) { $vmArgs.Add('-Dpzopt.enabled=false') }
    $vmArgs.Add("-Dmelens.dev.port=$($Lens.LuaPort)")
    $vmArgs.Add("-agentlib:zbNative=policy=allow-all,verbosity=1,config_dir=$zbConfig")
    $vmArgs.Add('-cp')
    $vmArgs.Add($(if ($Stock) { 'projectzomboid.jar;.' } else { '.;projectzomboid.jar' }))
    $vmArgs.Add($config.mainClass.Replace('/', '.'))
    $vmArgs.Add('-nosteam')
    $vmArgs.Add("-cachedir=$zomboid")
    if (-not $NoDebug) { $vmArgs.Add('-debug') }

    # The game's own stdout/stderr go to files (console.txt has the same), so a caller's
    # console is not flooded. The last run's console.txt is kept as console.prev.txt: the test
    # game has closed by itself now and then, and a new launch overwrote the reason.
    $console = Join-Path $zomboid 'console.txt'
    if (Test-Path -LiteralPath $console) { Copy-Item -LiteralPath $console -Destination (Join-Path $zomboid 'console.prev.txt') -Force }
    $env:PATH = "$($Lens.GameRoot)\win64;$($Lens.GameRoot);$env:PATH"
    $argLine = ($vmArgs | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
    $process = Start-Process -FilePath (Join-Path $Lens.GameRoot 'jre64\bin\java.exe') -ArgumentList $argLine `
        -WorkingDirectory $Lens.GameRoot -NoNewWindow -PassThru `
        -RedirectStandardOutput (Join-Path $testHome 'stdout.log') -RedirectStandardError (Join-Path $testHome 'stderr.log')
    Set-Content -LiteralPath $pidFile -Value $process.Id
    Write-Host "Test game started, PID $($process.Id). Lua endpoint: http://127.0.0.1:$($Lens.LuaPort)/lua"
    Write-Host "Console log: $(Join-Path $zomboid 'console.txt')"
}

function Stop-TestGame {
    if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host 'No test game recorded.'; return }
    $id = [int](Get-Content -LiteralPath $pidFile)
    $process = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($process -and $process.Path -like "$($Lens.GameRoot)*") {
        Stop-Process -Id $id -Force
        Write-Host "Stopped test game $id"
    } else {
        Write-Host 'Test game is not running.'
    }
    Remove-Item -LiteralPath $pidFile -ErrorAction SilentlyContinue
}

switch ($Mode) {
    'Prepare' { Initialize-TestHome }
    'Launch' { Start-TestGame }
    'Stop' { Stop-TestGame }
}

# Owned two-client MP lab. By default the server runs without Java, matching ordinary hosts.
# Add -ServerJava to launch the isolated server with ZombieBuddy and ME: LENS' shipping Java only.
# Launch the COMPLETE lifetime through:
# node C:/Users/erika/.codex/tools/run-heavy.mjs -- pwsh -NoProfile -File dev/final-mp-session.ps1
# No existing testhome, server world, player profile or installed mod is changed.
# -Run final-mp-206-reconnect -ResumeFrom final-mp-206 copies a STOPPED owned
# prior lifetime, preserves its saves/accounts/config, and refreshes only new mods.
# During MP_REVIEW_READY, request.json accepts {"action":"driver","id":"interiors",
# "script":"dev/final-mp-interior-tests.py","args":[],"timeoutSeconds":900}.
# It runs asynchronously inside this parent's verified resource job. Output defaults
# to this run's drivers/<id>/output; stdout/stderr and receipt live beside it.
param(
    [string]$Run = 'final-mp-206',
    [string]$ResumeFrom,
    [switch]$ServerJava,
    [switch]$CompanionDogs,
    [switch]$ChevyStepVan,
    [string]$PackagePath,
    [switch]$AllowOtherGames,
    [ValidateRange(1024, 65534)][int]$ServerPort = 17361,
    [ValidateRange(1024, 65535)][int]$ClientLuaPortA = 18470,
    [ValidateRange(1024, 65535)][int]$ClientLuaPortB = 18472,
    [ValidateRange(1, 60)][int]$ReviewMinutes = 30,
    [ValidateRange(768, 4096)][int]$ClientHeapMiB = 3072,
    [ValidateRange(512, 6144)][int]$ServerHeapMiB = 4096
)
$explicitServerPort = $PSBoundParameters.ContainsKey('ServerPort')
. (Join-Path $PSScriptRoot '..\scripts\common.ps1')
. (Join-Path $PSScriptRoot 'existing-test-acknowledgements.ps1')
$ErrorActionPreference = 'Stop'
if ($CompanionDogs) {
    $Lens.Dependencies += @{ Id = 'CompanionDogs'; Item = '3740052292'; Folder = 'CompanionDogs' }
}
if ($ChevyStepVan) {
    $Lens.Dependencies += @{ Id = '85chevyStepVan'; Item = '3614034284'; Folder = '85chevyStepVan' }
}
$testModIds = @($Lens.Dependencies | ForEach-Object { $_.Id }) + @('RealVehicleInteriors', 'RealVehicleInteriors_Dev')
if ($PackagePath) {
    $resolvedPackage = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $PackagePath -ErrorAction Stop).Path)
    $packageRoot = [IO.Path]::GetFullPath($Lens.Out)
    if (-not $resolvedPackage.StartsWith($packageRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or
        -not (Test-Path -LiteralPath $resolvedPackage -PathType Container) -or
        ((Get-Item -LiteralPath $resolvedPackage -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'PackagePath must be an existing ordinary directory inside build/rv'
    }
    $Lens.Package = $resolvedPackage
}
if ($Run -notmatch '^[a-z0-9-]+$') { throw 'Run must be a simple owned folder name' }
$runPath = [IO.Path]::GetFullPath((Join-Path $Lens.Out $Run))
if (-not $runPath.StartsWith($Lens.Out + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Run must remain inside build/rv' }
if (Test-Path -LiteralPath $runPath) { throw 'Run already exists; choose a new name to preserve previous evidence' }
$resumePath = $null; $resumeSession = $null; $resumeCredentials = $null
$resumeHomes = @{}; $preservedHashes = [ordered]@{}
$serverName = 'melens-final206'
if ($ResumeFrom) {
    $candidate = if ($ResumeFrom -match '^[a-z0-9-]+$') { Join-Path $Lens.Out $ResumeFrom }
        elseif ([IO.Path]::IsPathRooted($ResumeFrom)) { $ResumeFrom }
        else { Join-Path $Lens.Root $ResumeFrom }
    $resumePath = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path)
    if (-not $resumePath.StartsWith($Lens.Out + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Resume source must be an owned run inside build/rv' }
    if ($runPath.StartsWith($resumePath + '\', [StringComparison]::OrdinalIgnoreCase) -or $resumePath.StartsWith($runPath + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Resume source and destination cannot contain each other' }
    $ancestor = $resumePath
    while ($ancestor -and $ancestor.StartsWith($Lens.Out, [StringComparison]::OrdinalIgnoreCase)) {
        if ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Resume source ancestry contains a reparse point' }
        if ($ancestor.Equals($Lens.Out, [StringComparison]::OrdinalIgnoreCase)) { break }
        $ancestor = [IO.Path]::GetDirectoryName($ancestor)
    }
    $resumeSession = Get-Content -LiteralPath (Join-Path $resumePath 'session.json') -Raw | ConvertFrom-Json
    if ([bool]$CompanionDogs -ne ($resumeSession.companionDogs -eq $true)) { throw 'Resume must use the original CompanionDogs flag' }
    $resumeCredentials = Get-Content -LiteralPath (Join-Path $resumePath 'credentials.json') -Raw | ConvertFrom-Json
    $priorNoJava = $resumeSession.serverNoJava -eq $true -and $resumeSession.serverJava -ne $true
    $priorServerJava = $resumeSession.serverJava -eq $true -and $resumeSession.serverNoJava -ne $true
    if (($priorNoJava -eq $priorServerJava) -or -not $resumeSession.stockClientClasses -or -not $resumeSession.inactiveDesktops) { throw 'Resume source is not a valid owned MP harness lifetime (no-Java or server-Java)' }
    if (-not $resumeSession.finishedUtc -or $null -eq $resumeSession.serverExitCode -or $resumeSession.serverExitCode -ne 0) { throw 'Prior owned lifetime must finish and the server must exit successfully before resume' }
    if ($resumeCredentials.admin -ne 'MELensAdmin' -or $resumeCredentials.guest -ne 'MELensGuest' -or -not $resumeCredentials.adminSecret -or -not $resumeCredentials.guestSecret) { throw 'Prior owned account credentials are missing or unexpected' }
    if ($resumeSession.serverName) { $serverName = [string]$resumeSession.serverName }
    elseif ($resumeCredentials.serverName) { $serverName = [string]$resumeCredentials.serverName }
    if ($serverName -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Invalid prior server name' }
    $priorIniPath = Join-Path $resumePath "server\home\Zomboid\Server\$serverName.ini"
    $priorIni = [IO.File]::ReadAllText($priorIniPath)
    $priorPort = if ($resumeSession.serverPort) { [int]$resumeSession.serverPort }
        else { [int]([regex]::Match($priorIni, '(?m)^DefaultPort=(\d+)\s*$').Groups[1].Value) }
    if ($priorPort -lt 1024 -or $priorPort -gt 65534) { throw 'Prior owned server port is invalid' }
    if ($explicitServerPort -and $ServerPort -ne $priorPort) { throw 'Resume must use the prior server port; omit ServerPort or use its original value' }
    $ServerPort = $priorPort
    foreach ($name in @('server', 'client-a', 'client-b')) {
        $sourceHome = [IO.Path]::GetFullPath((Join-Path $resumePath "$name\home"))
        if (-not $sourceHome.StartsWith($resumePath + '\', [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $sourceHome -PathType Container)) { throw "Missing owned prior home: $name" }
        # Refuse links before copying or recursively replacing any copied mod:
        # no path beneath a staged home may redirect outside the owned trees.
        $nodes = @(Get-Item -LiteralPath $sourceHome -Force) + @(Get-ChildItem -LiteralPath $sourceHome -Force -Recurse)
        $links = @($nodes | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
        if (@($links).Count) { throw "Resume home contains a reparse point: $name" }
        $resumeHomes[$name] = $sourceHome
    }
    $recordedServerCache = [IO.Path]::GetFullPath([string]$resumeSession.serverCache)
    if (-not $recordedServerCache.Equals((Join-Path $resumeHomes.server 'Zomboid'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Prior server cache identity does not match the owned run' }
}
$otherGamePids = @(Get-LensGameProcesses | ForEach-Object { [int]$_.ProcessId })
if ($otherGamePids.Count -and -not $AllowOtherGames) { throw 'A Project Zomboid client is running; use -AllowOtherGames only for an approved guarded concurrent run' }
if ($otherGamePids.Count) { Write-Host "ALLOW_OTHER_GAMES existingPids=$($otherGamePids -join ',') untouched=true" }
$configuredPorts = @($ServerPort, ($ServerPort + 1), $ClientLuaPortA, $ClientLuaPortB)
if (@($configuredPorts | Select-Object -Unique).Count -ne $configuredPorts.Count) { throw 'Server and client ports must all be distinct' }
$network = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
$busyPorts = @($network.GetActiveTcpListeners() | ForEach-Object Port) + @($network.GetActiveUdpListeners() | ForEach-Object Port)
foreach ($port in @($ServerPort, ($ServerPort + 1), $ClientLuaPortA, $ClientLuaPortB)) {
    if ($busyPorts -contains $port) { throw "Port $port is occupied; no process will be stopped" }
}
if (-not (Test-Path -LiteralPath (Join-Path $Lens.Package '42.21\media\java\RealVehicleInteriors.jar'))) { throw 'Build the package first' }
New-Item -ItemType Directory -Path $runPath | Out-Null
$python = Get-LensPython
$keeperScript = [IO.Path]::GetFullPath((Join-Path $Lens.Root 'dev\windows-test-session.py'))
$server = $null
$clients = [Collections.Generic.List[object]]::new()
$driver = $null
$serverStdout = $null; $serverStderr = $null
$session = [ordered]@{
    serverNoJava = (-not [bool]$ServerJava); serverJava = [bool]$ServerJava
    companionDogs = [bool]$CompanionDogs; chevyStepVan = [bool]$ChevyStepVan
    packagePath = $Lens.Package; allowOtherGames = [bool]$AllowOtherGames
    unmanagedGamePids = $otherGamePids; clientLuaPortA = $ClientLuaPortA; clientLuaPortB = $ClientLuaPortB
    stockClientClasses = $true; inactiveDesktops = $true
    clientHeapMiB = $ClientHeapMiB; serverHeapMiB = $ServerHeapMiB
    combinedHeapMiB = (2 * $ClientHeapMiB + $ServerHeapMiB)
    directMemoryPerClientMiB = 128; texture2x = $false; textureCompression = $true
    memoryLimitChanged = $false; luaChecksumEnabled = $true; checksumMismatchAction = 'kick'; antiCheatChecksum = 2
    scope = 'Disposable non-Steam local dedicated server, two real clients; connection screens are setup automation'
    resumed = [bool]$ResumeFrom; resumeFrom = $resumePath; serverName = $serverName; serverPort = $ServerPort
    startedUtc = [DateTime]::UtcNow.ToString('o'); clients = @(); status = 'preparing'
    driverDispatcher = $true; driverHistory = @()
}
if ($resumeSession) { $session.priorFinishedUtc = $resumeSession.finishedUtc }

function Write-Json([string]$path, $value) {
    [IO.File]::WriteAllText($path, ($value | ConvertTo-Json -Depth 15), [Text.UTF8Encoding]::new($false))
}
$script:ownedIdentities = @{}
function Record-OwnedTree {
    # Capture exact early UTC creation identities without command lines/secrets.
    # Short native lifetimes may finish between the coordinator's audit pulses.
    $rows = @(Get-CimInstance Win32_Process)
    $owned = @{}; $owned[[int]$PID] = $true
    do {
        $added = $false
        foreach ($row in $rows) {
            if ($owned.ContainsKey([int]$row.ParentProcessId) -and -not $owned.ContainsKey([int]$row.ProcessId)) {
                $owned[[int]$row.ProcessId] = $true; $added = $true
            }
        }
    } while ($added)
    foreach ($row in $rows) {
        if (-not $owned.ContainsKey([int]$row.ProcessId)) { continue }
        $created = $row.CreationDate.ToUniversalTime()
        $key = "$($row.ProcessId):$($created.Ticks)"
        $script:ownedIdentities[$key] = @{ pid = [int]$row.ProcessId; parentPid = [int]$row.ParentProcessId
            name = $row.Name; createdUtc = $created.ToString('o'); cimStartTicks = $created.Ticks }
    }
    Write-Json (Join-Path $runPath 'owned-process-identities.json') @{ recordedUtc = [DateTime]::UtcNow.ToString('o')
        rootPid = $PID; processes = @($script:ownedIdentities.Values) }
}
function File-Sha256([string]$path) {
    $stream = [IO.File]::OpenRead($path)
    try { return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream)).ToLowerInvariant() }
    finally { $stream.Dispose() }
}
function Set-Ini([string]$text, [string]$key, [string]$value) {
    $pattern = '(?m)^' + [regex]::Escape($key) + '=.*$'
    if ([regex]::IsMatch($text, $pattern)) { return [regex]::Replace($text, $pattern, ($key + '=' + $value)) }
    return $text.TrimEnd() + "`n$key=$value`n"
}
function Replace-OwnedMod([string]$source, [string]$mods, [string]$folder) {
    if ($folder -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Invalid staged mod folder' }
    $target = [IO.Path]::GetFullPath((Join-Path $mods $folder))
    $ownedMods = [IO.Path]::GetFullPath($mods)
    if (-not $target.StartsWith($runPath + '\', [StringComparison]::OrdinalIgnoreCase) -or -not ([IO.Path]::GetDirectoryName($target)).Equals($ownedMods, [StringComparison]::OrdinalIgnoreCase)) { throw 'Replacement target is outside the new owned mods directory' }
    if (Test-Path -LiteralPath $target) {
        if ((Get-Item -LiteralPath $target -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing linked staged mod replacement' }
        Remove-Item -LiteralPath $target -Recurse -Force
    }
    Copy-Item -LiteralPath $source -Destination $target -Recurse
}
function Lua([int]$port, [string]$code, [int]$timeout = 10) {
    $reply = Invoke-WebRequest -Uri "http://127.0.0.1:$port/lua?depth=8&sandbox=false" -Method Post -Body $code -ContentType 'text/plain' -TimeoutSec $timeout
    $decoded = $reply.Content | ConvertFrom-Json
    if (-not $decoded.ok) { throw "Lab Lua failed on port ${port}: $($decoded.error)" }
    return $decoded.result
}
function Alive($record) {
    if (-not $record -or -not $record.gameId) { return $false }
    $process = Get-Process -Id $record.gameId -ErrorAction SilentlyContinue
    return $process -and $process.StartTime.ToUniversalTime().Ticks -eq $record.startTicks
}
function Wait-Lua($record, [string]$code, [string]$match, [int]$seconds = 180) {
    $deadline = [DateTime]::UtcNow.AddSeconds($seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (-not (Alive $record)) { throw "Owned client $($record.name) exited while waiting" }
        try { $value = Lua $record.port $code; if ([string]$value -match $match) { return $value } } catch { }
        Start-Sleep -Milliseconds 300
    }
    throw "Client $($record.name) timed out waiting for $match"
}
function Stage-Profile([string]$name, [bool]$includeDeveloperJava = $true) {
    $profileHome = Join-Path $runPath "$name\home"
    if ($resumePath) {
        if (Test-Path -LiteralPath $profileHome) { throw 'Resume destination home must be new' }
        New-Item -ItemType Directory -Path (Split-Path $profileHome -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $resumeHomes[$name] -Destination $profileHome -Recurse
        foreach ($file in Get-ChildItem -LiteralPath $resumeHomes[$name] -Force -Recurse -File) {
            $relative = [IO.Path]::GetRelativePath($resumeHomes[$name], $file.FullName)
            $expected = File-Sha256 $file.FullName
            if ((File-Sha256 (Join-Path $profileHome $relative)) -ne $expected) { throw "Copied prior home differs: $name/$relative" }
            $preservedHashes["$name/$relative"] = $expected
        }
    }
    $cache = Join-Path $profileHome 'Zomboid'
    $mods = Join-Path $cache 'mods'
    New-Item -ItemType Directory -Path $mods, (Join-Path $profileHome 'zombie_buddy') -Force | Out-Null
    foreach ($dep in $Lens.Dependencies) {
        $source = Join-Path $Lens.TestHome "Zomboid\mods\$($dep.Folder)"
        if (-not (Test-Path -LiteralPath $source)) {
            $source = Join-Path $Lens.Workshop "$($dep.Item)\mods\$($dep.Folder)"
        }
        if (-not (Test-Path -LiteralPath $source)) { throw "Missing read-only dependency input $($dep.Id)" }
        Replace-OwnedMod $source $mods $dep.Folder
    }
    Replace-OwnedMod $Lens.Package $mods 'RealVehicleInteriors'
    Replace-OwnedMod (Join-Path $Lens.Root 'dev\RealVehicleInteriors_Dev') $mods 'RealVehicleInteriors_Dev'
    if ($includeDeveloperJava) {
        $javaDir = Join-Path $mods 'RealVehicleInteriors_Dev\42.21\media\java'
        New-Item -ItemType Directory -Path $javaDir -Force | Out-Null
        Copy-Item -LiteralPath $script:devJar -Destination (Join-Path $javaDir 'RealVehicleInteriors_Dev.jar') -Force
    }
    $modLines = ($testModIds | ForEach-Object { "    mod = $_,`n" }) -join ''
    $modList = "VERSION = 1,`nmods`n{`n${modLines}}`nmaps`n{`n}`n"
    [IO.File]::WriteAllText((Join-Path $mods 'default.txt'), $modList)
    [IO.File]::WriteAllText((Join-Path $mods 'reset-mods-42_00.txt'), 'Owned isolated MP test profile.')
    $options = @'
version=8
fullScreen=false
borderless=false
width=1280
height=720
focusloss=false
textureCompression=true
texture2x=false
uncappedFPS=false
frameRate=30
soundVolume=0
musicVolume=0
'@
    $optionsPath = Join-Path $cache 'options.ini'
    if ($resumePath -and (Test-Path -LiteralPath $optionsPath)) {
        # Keep the prior client's preferences and key bindings byte-for-byte.
        # This harness originally staged the same bounded rendering settings.
    } else {
        $acknowledgements = Join-Path $Lens.TestHome 'Zomboid\options.ini'
        if (-not (Test-Path -LiteralPath $acknowledgements -PathType Leaf)) {
            # A new worktree has no established testhome yet. Match SP Prepare:
            # copy only values the user already acknowledged, read-only.
            $acknowledgements = Join-Path $env:USERPROFILE 'Zomboid\options.ini'
        }
        $options = Add-ExistingTestAcknowledgements $options $acknowledgements
        [IO.File]::WriteAllText($optionsPath, $options)
    }
    return [pscustomobject]@{ name = $name; home = $profileHome; cache = $cache; mods = $mods }
}
function Start-NativeClient($profile, [int]$port) {
    $path = Join-Path $runPath $profile.name
    $arguments = @((Join-Path $Lens.GameRoot 'jre64\bin\java.exe'), '-Xms128m', "-Xmx${ClientHeapMiB}m", '-XX:MaxDirectMemorySize=128m', '-XX:ReservedCodeCacheSize=96m',
        '--enable-native-access=ALL-UNNAMED', '--add-exports=java.base/jdk.internal.misc=ALL-UNNAMED',
        '-Djava.awt.headless=true', '-Djava.library.path=win64/;.', '-XX:-OmitStackTraceInFastThrow', '-Dzomboid.steam=0',
        "-Duser.home=$($profile.home)", '-Dpzopt.enabled=false', '-Dpzopt.gcMode=stock', '-Dpzopt.jitSteady=false',
        '-Dpzopt.aotCache=false', '-Dpzopt.updateCheck=false', "-Dmelens.dev.port=$port",
        "-agentlib:zbNative=policy=allow-all,verbosity=1,config_dir=$($profile.home)\zombie_buddy", '-cp', 'projectzomboid.jar;.',
        'zombie.gameStates.MainScreenState', '-nosteam', "-cachedir=$($profile.cache)")
    $config = Join-Path $path 'native-session.json'
    Write-Json $config @{ command = $arguments; cwd = $Lens.GameRoot }
    $psi = [Diagnostics.ProcessStartInfo]::new($python)
    $psi.ArgumentList.Add($keeperScript); $psi.ArgumentList.Add($config)
    $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    $psi.Environment['PATH'] = "$($Lens.GameRoot)\win64;$($Lens.GameRoot);$env:PATH"
    foreach ($key in @('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS')) { [void]$psi.Environment.Remove($key) }
    $keeper = [Diagnostics.Process]::Start($psi)
    Record-OwnedTree
    $record = [pscustomobject]@{ name = $profile.name; port = $port; profile = $profile; keeper = $keeper
        stdout = $keeper.StandardOutput.ReadToEndAsync(); stderr = $keeper.StandardError.ReadToEndAsync()
        gameId = 0; startTicks = 0; path = $path }
    $clients.Add($record)
    $started = Join-Path $path 'native-session-started.json'
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    while (-not (Test-Path -LiteralPath $started)) {
        if ($keeper.HasExited -or [DateTime]::UtcNow -ge $deadline) { throw "Inactive-desktop keeper did not launch $($profile.name)" }
        Start-Sleep -Milliseconds 200
    }
    $native = Get-Content -LiteralPath $started -Raw | ConvertFrom-Json
    $record.gameId = [int]$native.pid
    $record.startTicks = (Get-Process -Id $record.gameId).StartTime.ToUniversalTime().Ticks
    Record-OwnedTree
    Write-Host "CLIENT_PROCESS_READY $($record.name) pid=$($record.gameId) lua=$port inactiveDesktop=true"
    [void](Wait-Lua $record 'return MainScreen and MainScreen.instance and "menu" or "waiting"' '^menu$' 240)
    [void](Lua $port 'UIManager.setShowLuaDebuggerOnError(false); pcall(function() doLuaDebuggerAction("Resume") end); return 1')
    if ((Lua $port 'return tostring(ActiveMods.requiresResetLua(ActiveMods.getById("default")))') -eq 'true') {
        try { [void](Lua $port 'getCore():ResetLua("default","Force"); return 1') }
        catch {
            # ResetLua invalidates its current Lua call before a result can be
            # serialized. Readiness below must still prove the new runtime loaded.
            if ($_.Exception.Message -notmatch 'lua was reset') { throw }
        }
        Start-Sleep -Seconds 3
        [void](Wait-Lua $record 'return MainScreen and MainScreen.instance and MELens and MEMCNativeLab and "menu" or "waiting"' '^menu$' 120)
    }
    [void](Wait-Lua $record 'return MainScreen and MainScreen.instance and MELens and MEMCNativeLab and MELensMedia and MELensNativeText and "adapters" or "waiting"' '^adapters$' 120)
    [void](Lua $port 'UIManager.setShowLuaDebuggerOnError(false); pcall(function() doLuaDebuggerAction("Resume") end); return 1')
    Write-Host "CLIENT_MENU_READY $($record.name)"
    return $record
}
function Finish-Connection($record) {
    # getPlayer() can exist while GameLoadingState is still preparing the world.
    # Match the native ready marker before releasing its final loading screen.
    $log = Join-Path $record.path 'stdout.log'
    $deadline = [DateTime]::UtcNow.AddSeconds(180)
    while (-not ((Test-Path -LiteralPath $log) -and (Select-String -LiteralPath $log -Pattern 'game loading took' -Quiet))) {
        if (-not (Alive $record)) { throw "Owned client $($record.name) exited during connection loading" }
        if ([DateTime]::UtcNow -ge $deadline) { throw "Client $($record.name) did not finish native world loading; see $log" }
        Start-Sleep -Milliseconds 300
    }
    [void](Lua $record.port 'MELensMedia.start(); GameWindow.doRenderEvent(true); return 1')
    [void](Wait-Lua $record 'local p=getPlayer(); return p and isClient() and isIngameState() and p:getOnlineID()>=0 and MELens and MEMCNativeLab and MELensNativeText and "connected" or "waiting"' '^connected$' 120)
    [void](Lua $record.port ([IO.File]::ReadAllText((Join-Path $PSScriptRoot 'lua\setup.lua'))))
    Write-Host "CLIENT_WORLD_READY $($record.name)"
}
function Capture($record, [string]$name) {
    if ($name -notmatch '^[a-z0-9-]+$') { throw 'Invalid owned screenshot name' }
    $source = Join-Path $record.profile.cache "Screenshots\$name.png"
    if (Test-Path -LiteralPath $source) { Remove-Item -LiteralPath $source }
    [void](Lua $record.port "MEMCNativeLab.capture('$name.png'); return 1")
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $source) {
            try {
                $data = [IO.File]::ReadAllBytes($source)
                if ($data.Length -ge 12 -and [Text.Encoding]::ASCII.GetString($data, $data.Length - 8, 4) -eq 'IEND') {
                    Copy-Item -LiteralPath $source -Destination (Join-Path $record.path "$name.png") -Force
                    return
                }
            } catch { }
        }
        Start-Sleep -Milliseconds 100
    }
    throw "Missing complete native screenshot $($record.name)/$name"
}

function Resolve-DriverPath([string]$value, [string]$kind) {
    if (-not $value -or $value.IndexOf([char]0) -ge 0) { throw 'Driver paths must be nonempty and contain no NUL' }
    $absolute = [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($value)) { $value } else { Join-Path $Lens.Root $value }))
    $boundary = if ($kind -eq 'input') { $Lens.Out } else { $runPath }
    $inside = $absolute.StartsWith($boundary + '\', [StringComparison]::OrdinalIgnoreCase)
    if ($kind -eq 'session') {
        if (-not $absolute.Equals($runPath, [StringComparison]::OrdinalIgnoreCase)) { throw 'Driver session/run must be the current owned run' }
    } elseif (-not $inside) { throw "Driver $kind path must stay inside $boundary" }
    # Future output directories are allowed, but existing ancestors must not link
    # outside the verified owned run.
    $ancestor = $absolute
    while ($ancestor -and ($ancestor.Equals($boundary, [StringComparison]::OrdinalIgnoreCase) -or $ancestor.StartsWith($boundary + '\', [StringComparison]::OrdinalIgnoreCase))) {
        if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Driver path contains a reparse point' }
        if ($ancestor.Equals($boundary, [StringComparison]::OrdinalIgnoreCase)) { break }
        $ancestor = [IO.Path]::GetDirectoryName($ancestor)
    }
    return $absolute
}

function Resolve-DriverRequest($q) {
    $requested = [string]$q.script
    if (-not $requested) { throw 'Driver request needs script=dev/final-*.py' }
    $scriptPath = [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($requested)) { $requested } else { Join-Path $Lens.Root $requested }))
    $name = [IO.Path]::GetFileName($scriptPath)
    $dev = [IO.Path]::GetFullPath((Join-Path $Lens.Root 'dev'))
    if ($name -notmatch '^final-[a-z0-9-]+\.py$' -or -not ([IO.Path]::GetDirectoryName($scriptPath)).Equals($dev, [StringComparison]::OrdinalIgnoreCase)) { throw 'Only project dev/final-*.py driver files are allowed' }
    if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf) -or ((Get-Item -LiteralPath $scriptPath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Driver must be an existing ordinary project file' }
    if ($q.args -is [string]) { throw 'Driver args must be a JSON array of strings' }
    $raw = @($q.args)
    if ($raw.Count -gt 64) { throw 'Driver has too many arguments' }
    $tokens = [Collections.Generic.List[string]]::new()
    $seen = @{}
    for ($index = 0; $index -lt $raw.Count; $index++) {
        if ($raw[$index] -isnot [string] -or $raw[$index].Length -gt 8192 -or $raw[$index].IndexOf([char]0) -ge 0) { throw 'Driver arguments must be bounded strings without NUL' }
        $argument = [string]$raw[$index]
        $flag = $argument; $inline = $false; $value = $null
        if ($argument -match '^(--[^=]+)=(.*)$') { $flag = $Matches[1]; $value = $Matches[2]; $inline = $true }
        $kind = switch -Regex ($flag) {
            '^--output$' { 'output'; break }
            '^--(session|run)$' { 'session'; break }
            '^--screens-a$' { 'source'; break }
            '^--(baseline|f700-report|camper-report|bus-report)$' { 'input'; break }
            default { $null }
        }
        if ($kind) {
            if ($seen.ContainsKey($flag)) { throw "Duplicate driver path option $flag" }
            $seen[$flag] = $true
            if (-not $inline) {
                $index++
                if ($index -ge $raw.Count -or $raw[$index] -isnot [string]) { throw "Missing driver path value for $flag" }
                $value = [string]$raw[$index]
            }
            $tokens.Add($flag); $tokens.Add((Resolve-DriverPath $value $kind))
        } else { $tokens.Add($argument) }
    }
    $id = if ($q.id) { [string]$q.id } else { [Guid]::NewGuid().ToString('N') }
    if ($id -notmatch '^[a-z0-9][a-z0-9-]{0,63}$') { throw 'Driver id must be a lowercase simple name up to 64 characters' }
    $path = Resolve-DriverPath (Join-Path $runPath "drivers\$id") 'output'
    if (Test-Path -LiteralPath $path) { throw 'Driver id already exists; preserve prior receipts with a new id' }
    if (-not $seen.ContainsKey('--output')) { $tokens.Add('--output'); $tokens.Add((Join-Path $path 'output')) }
    $sessionScripts = @('final-mp-interior-tests.py', 'final-mp-loot-ui-tests.py', 'final-mp-camper-setup.py',
        'final-mp-furniture-tests.py', 'final-mp-water-tests.py', 'final-mp-personalization.py',
        'final-mp-bus-tests.py', 'final-mp-persistence.py', 'final-mp-motion-tests.py', 'final-mp-phobia-tests.py')
    if ($name -in $sessionScripts -and -not $seen.ContainsKey('--session')) { $tokens.Add('--session'); $tokens.Add($runPath) }
    if ($name -eq 'final-mp-features.py' -and -not $seen.ContainsKey('--screens-a')) {
        $tokens.Add('--screens-a'); $tokens.Add((Join-Path $runPath 'client-a\home\Zomboid\Screenshots'))
    }
    if (($tokens -join '').Length -gt 24000) { throw 'Driver command line is too long' }
    $seconds = if ($null -ne $q.timeoutSeconds) { [int]$q.timeoutSeconds } else { 900 }
    if ($seconds -lt 10 -or $seconds -gt 1800) { throw 'Driver timeoutSeconds must be between 10 and 1800' }
    return [pscustomobject]@{ id = $id; script = $scriptPath; args = $tokens.ToArray(); path = $path; seconds = $seconds }
}

function Start-ReviewDriver($q, [DateTime]$reviewDeadline) {
    if ($script:driver) { throw 'Only one native driver may run at a time' }
    $spec = Resolve-DriverRequest $q
    $remaining = [int][Math]::Floor(($reviewDeadline - [DateTime]::UtcNow).TotalSeconds)
    if ($remaining -lt 10) { throw 'Not enough bounded review time remains for a driver' }
    $seconds = [Math]::Min($spec.seconds, $remaining)
    New-Item -ItemType Directory -Path $spec.path | Out-Null
    $receipt = [ordered]@{ id = $spec.id; action = 'driver'; script = $spec.script; args = $spec.args
        status = 'starting'; startedUtc = [DateTime]::UtcNow.ToString('o'); timeoutSeconds = $seconds
        guarded = $true; guard = 'C:/Users/erika/.codex/tools/run-heavy.mjs'; inheritsParentWindowsJob = $true
        stdout = Join-Path $spec.path 'stdout.log'; stderr = Join-Path $spec.path 'stderr.log'
        receipt = Join-Path $spec.path 'receipt.json'; outputWithinOwnedRun = $true }
    $psi = [Diagnostics.ProcessStartInfo]::new((Get-Command node -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source)
    $psi.WorkingDirectory = $Lens.Root; $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    foreach ($argument in @($receipt.guard, '--', $python, $spec.script) + $spec.args) { $psi.ArgumentList.Add($argument) }
    # The environment is inherited unchanged. run-heavy verifies actual Windows
    # job membership and keeps the complete parent/client/server/driver tree cap.
    $process = [Diagnostics.Process]::Start($psi)
    Record-OwnedTree
    $receipt.pid = $process.Id; $receipt.startTicks = $process.StartTime.ToUniversalTime().Ticks
    $receipt.status = 'running'; $receipt.deadlineUtc = [DateTime]::UtcNow.AddSeconds($seconds).ToString('o')
    $script:driver = [pscustomobject]@{ process = $process; stdout = $process.StandardOutput.ReadToEndAsync()
        stderr = $process.StandardError.ReadToEndAsync(); receipt = $receipt; deadline = [DateTime]::UtcNow.AddSeconds($seconds) }
    $session.driverHistory += $receipt
    Write-Json $receipt.receipt $receipt
    Write-Json (Join-Path $runPath 'session.json') $session
    Write-Json (Join-Path $runPath 'response.json') $receipt
    Write-Host "MP_DRIVER_STARTED id=$($receipt.id) pid=$($receipt.pid) boundedSeconds=$seconds"
}

function Complete-ReviewDriver([string]$reason = '') {
    if (-not $script:driver) { return }
    $active = $script:driver; $process = $active.process
    if (-not $process.HasExited) {
        if (-not $reason -and [DateTime]::UtcNow -lt $active.deadline) { return }
        if (-not $reason) { $reason = 'timed-out' }
        # This pinned Process object is the exact child created above. Its tree
        # contains only the nested guard and this one driver, never the games.
        $process.Kill($true)
        if (-not $process.WaitForExit(5000)) { throw 'Owned driver did not stop after bounded termination' }
        foreach ($client in $clients) { if (Alive $client) { try { [void](Lua $client.port 'MEMCNativeLab.releaseKeys(); return 1' 3) } catch { } } }
    }
    [void]$process.WaitForExit(1000)
    $receipt = $active.receipt
    $receipt.exitCode = $process.ExitCode
    $receipt.finishedUtc = [DateTime]::UtcNow.ToString('o')
    $receipt.status = if ($reason) { $reason } elseif ($process.ExitCode -eq 0) { 'passed' } else { 'failed' }
    [void]$active.stdout.Wait(2000); [void]$active.stderr.Wait(2000)
    if ($active.stdout.IsCompleted) { [IO.File]::WriteAllText($receipt.stdout, $active.stdout.Result) }
    if ($active.stderr.IsCompleted) { [IO.File]::WriteAllText($receipt.stderr, $active.stderr.Result) }
    Write-Json $receipt.receipt $receipt
    Write-Json (Join-Path $runPath 'driver-response.json') $receipt
    Write-Json (Join-Path $runPath 'session.json') $session
    Write-Host "MP_DRIVER_FINISHED id=$($receipt.id) status=$($receipt.status) exit=$($receipt.exitCode)"
    $process.Dispose(); $script:driver = $null
}

try {
    Record-OwnedTree
    # Compile once into the new run, then stage all three profiles sequentially.
    $classes = Join-Path $runPath 'dev-classes'
    New-Item -ItemType Directory -Path $classes | Out-Null
    $sources = @(Get-ChildItem -LiteralPath (Join-Path $Lens.Root 'dev\java') -Recurse -Filter '*.java' | ForEach-Object FullName)
    $cp = "$(Join-Path $Lens.GameRoot 'projectzomboid.jar');$(Join-Path $Lens.GameRoot 'ZombieBuddy.jar')"
    & (Join-Path $Lens.Jdk 'javac.exe') -J-Xmx256m --release 25 -d $classes -cp $cp @sources
    if ($LASTEXITCODE) { throw 'Owned MP developer adapter compilation failed' }
    $script:devJar = Join-Path $runPath 'RealVehicleInteriors_Dev.jar'
    & (Join-Path $Lens.Jdk 'jar.exe') -J-Xmx128m --create --file $script:devJar -C $classes .
    if ($LASTEXITCODE) { throw 'Owned MP developer adapter packaging failed' }
    # Keep the developer adapter on clients for its local HTTP/Lua driver. A Java server
    # loads only the shipping RVI JAR; the developer mod's Lua remains available server-side.
    $serverProfile = Stage-Profile 'server' (-not [bool]$ServerJava)
    $profileA = Stage-Profile 'client-a'
    $profileB = Stage-Profile 'client-b'
    if ($resumePath) {
        Write-Json (Join-Path $runPath 'resume-preserved-files.json') @{ source = $resumePath; comparedBeforeModRefresh = $true; files = $preservedHashes }
        $session.resumeCopiedFilesVerified = $preservedHashes.Count
        Write-Host "RESUME_PROFILES_COPIED exactFiles=$($preservedHashes.Count)"
    }
    $payloadHashes = [ordered]@{}
    foreach ($file in Get-ChildItem -LiteralPath $Lens.Package -Recurse -File) {
        $relative = [IO.Path]::GetRelativePath($Lens.Package, $file.FullName)
        $expected = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([IO.File]::ReadAllBytes($file.FullName))).ToLowerInvariant()
        foreach ($profile in @($serverProfile, $profileA, $profileB)) {
            $copy = Join-Path $profile.mods "RealVehicleInteriors\$relative"
            $actual = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([IO.File]::ReadAllBytes($copy))).ToLowerInvariant()
            if ($actual -ne $expected) { throw "Staged package differs in $($profile.name)/$relative" }
        }
        $payloadHashes[$relative] = $expected
    }
    Write-Json (Join-Path $runPath 'payload-hashes.json') $payloadHashes
    $session.payloadFiles = $payloadHashes.Count
    $modHashes = [ordered]@{}
    foreach ($folder in @($Lens.Dependencies | ForEach-Object { $_.Folder }) + @('RealVehicleInteriors', 'RealVehicleInteriors_Dev')) {
        $controlRoot = Join-Path $serverProfile.mods $folder
        $controlFiles = @(Get-ChildItem -LiteralPath $controlRoot -Recurse -File)
        # ServerJava intentionally omits the developer adapter JAR from the
        # server while clients retain it for their local HTTP/Lua driver.
        $intentionalClientOnlyJar = $ServerJava -and $folder -eq 'RealVehicleInteriors_Dev'
        foreach ($profile in @($profileA, $profileB)) {
            $profileFiles = @(Get-ChildItem -LiteralPath (Join-Path $profile.mods $folder) -Recurse -File)
            if (-not $intentionalClientOnlyJar -and $profileFiles.Count -ne $controlFiles.Count) { throw "Mod file count differs in $($profile.name)/$folder" }
        }
        foreach ($file in $controlFiles) {
            $relative = [IO.Path]::GetRelativePath($controlRoot, $file.FullName)
            $expected = File-Sha256 $file.FullName
            foreach ($profile in @($profileA, $profileB)) {
                if ((File-Sha256 (Join-Path $profile.mods "$folder\$relative")) -ne $expected) { throw "Mod hash differs in $($profile.name)/$folder/$relative" }
            }
            $modHashes["$folder/$relative"] = $expected
        }
    }
    Write-Json (Join-Path $runPath 'all-mod-hashes.json') $modHashes
    $session.allModFiles = $modHashes.Count
    $adminSecret = if ($resumeCredentials) { [string]$resumeCredentials.adminSecret } else { [Guid]::NewGuid().ToString('N') }
    $guestSecret = if ($resumeCredentials) { [string]$resumeCredentials.guestSecret } else { [Guid]::NewGuid().ToString('N') }
    Write-Json (Join-Path $runPath 'credentials.json') @{ admin = 'MELensAdmin'; adminSecret = $adminSecret; guest = 'MELensGuest'; guestSecret = $guestSecret; serverName = $serverName; serverPort = $ServerPort }
    $serverIni = "Open=true`nPublic=false`nPVP=false`nPauseEmpty=true`nUPnP=false`nDefaultPort=$ServerPort`nUDPPort=$($ServerPort+1)`nMods=$($testModIds -join ';')`nWorkshopItems=`nMap=Muldraugh, KY`nSteamVAC=false`nDoLuaChecksum=true`nAntiCheatChecksum=2`n"
    New-Item -ItemType Directory -Path (Join-Path $serverProfile.cache 'Server') -Force | Out-Null
    $serverIniPath = Join-Path $serverProfile.cache "Server\$serverName.ini"
    $sandboxPath = Join-Path $serverProfile.cache "Server\${serverName}_SandboxVars.lua"
    if ($resumePath) {
        $serverIni = [IO.File]::ReadAllText($serverIniPath)
        foreach ($pair in @(@('DefaultPort', "$ServerPort"), @('UDPPort', "$($ServerPort+1)"),
            @('Mods', ($testModIds -join ';')),
            @('DoLuaChecksum', 'true'), @('AntiCheatChecksum', '2'), @('UPnP', 'false'))) {
            $serverIni = Set-Ini $serverIni $pair[0] $pair[1]
        }
        if (-not (Test-Path -LiteralPath $sandboxPath)) { throw 'Prior server sandbox settings are missing; refusing defaults' }
        $oldConsole = Join-Path $serverProfile.cache 'server-console.txt'
        if (Test-Path -LiteralPath $oldConsole) {
            Copy-Item -LiteralPath $oldConsole -Destination (Join-Path $runPath 'server\prior-server-console.txt')
            Remove-Item -LiteralPath $oldConsole
        }
    } else { [IO.File]::WriteAllText($sandboxPath, "SandboxVars = { VERSION = 6, Zombies = 6, }`n") }
    [IO.File]::WriteAllText($serverIniPath, $serverIni)
    $serverAgentArgs = @()
    if ($ServerJava) {
        $agentDll = Join-Path $Lens.GameRoot 'zbNative.dll'
        if (-not (Test-Path -LiteralPath $agentDll -PathType Leaf)) { throw "ServerJava requested, but the existing ZombieBuddy native agent is missing: $agentDll" }
        $serverAgentArgs = @("-agentlib:zbNative=policy=allow-all,verbosity=1,config_dir=$($serverProfile.home)\zombie_buddy")
        $session.zombieBuddyAgent = @{ dll = $agentDll; sha256 = (File-Sha256 $agentDll); policy = 'allow-all'; configDir = (Join-Path $serverProfile.home 'zombie_buddy') }
    }
    $serverArgs = @('-Xms256m', "-Xmx${ServerHeapMiB}m", '-XX:MaxDirectMemorySize=128m', '-XX:ReservedCodeCacheSize=64m',
        '--enable-native-access=ALL-UNNAMED', "-Djava.library.path=$($Lens.GameRoot)\win64;$($Lens.GameRoot)\natives;$($Lens.GameRoot)\natives\win64;$($Lens.GameRoot)",
        '-Dzomboid.steam=0') + $serverAgentArgs + @("-Duser.home=$($serverProfile.home)", "-Ddeployment.user.cachedir=$($serverProfile.cache)",
        '-Dpzopt.enabled=false', '-Dpzopt.aotCache=false', '-Dpzopt.gcMode=stock', '-Dpzopt.updateCheck=false',
        '-cp', "$($Lens.GameRoot)\projectzomboid.jar;$($Lens.GameRoot)", 'zombie.network.GameServer', "-cachedir=$($serverProfile.cache)", '-nosteam',
        '-servername', $serverName, '-ip', '127.0.0.1', '-port', "$ServerPort", '-udpport', "$($ServerPort+1)",
        '-adminusername', 'MELensAdmin', '-adminpassword', $adminSecret)
    $psi = [Diagnostics.ProcessStartInfo]::new((Join-Path $Lens.GameRoot 'jre64\bin\java.exe'))
    $psi.WorkingDirectory = $Lens.GameRoot; $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true; $psi.RedirectStandardInput = $true
    foreach ($argument in $serverArgs) { $psi.ArgumentList.Add($argument) }
    $psi.Environment['PATH'] = "$($Lens.GameRoot)\win64;$($Lens.GameRoot);$env:PATH"
    foreach ($key in @('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS')) { [void]$psi.Environment.Remove($key) }
    $server = [Diagnostics.Process]::Start($psi)
    Record-OwnedTree
    $serverStdout = $server.StandardOutput.ReadToEndAsync(); $serverStderr = $server.StandardError.ReadToEndAsync()
    $session.serverPid = $server.Id; $session.serverStartTicks = $server.StartTime.ToUniversalTime().Ticks; $session.serverCache = $serverProfile.cache
    Write-Host "SERVER_PROCESS_READY pid=$($server.Id) port=$ServerPort noJava=$(-not [bool]$ServerJava) serverJava=$([bool]$ServerJava)"
    $serverConsole = Join-Path $serverProfile.cache 'server-console.txt'
    $session.serverConsole = $serverConsole
    $deadline = [DateTime]::UtcNow.AddSeconds(300)
    while (-not ((Test-Path -LiteralPath $serverConsole) -and (Select-String -LiteralPath $serverConsole -Pattern 'SERVER STARTED' -Quiet))) {
        if ($server.HasExited) { throw "Owned server exited with code $($server.ExitCode)" }
        if ([DateTime]::UtcNow -ge $deadline) { throw 'Owned server did not reach SERVER STARTED' }
        Start-Sleep -Milliseconds 500
    }
    Write-Host "SERVER_READY noJava=$(-not [bool]$ServerJava) serverJava=$([bool]$ServerJava)"
    $a = Start-NativeClient $profileA $ClientLuaPortA
    # Reuse connection-screen setup only. Restore its environment override.
    $previousPort = $env:MELENS_LUA_PORT
    try { & (Join-Path $PSScriptRoot 'mp_connect.ps1') -Port $ServerPort -User 'MELensAdmin' -Password $adminSecret -LuaPort $ClientLuaPortA -OwnedClientPid $a.gameId -OwnedClientStartTicks $a.startTicks -OwnedServerPid $server.Id -OwnedServerStartTicks $session.serverStartTicks -OwnedServerConsole $serverConsole -DeferWorldSetup }
    finally { $env:MELENS_LUA_PORT = $previousPort }
    Finish-Connection $a
    $serverProbe = @'
MELensDevResult=nil; sendClientCommand(getPlayer(),"MELensDev","eval",{id=20601,code=[=[return tostring(isServer()) .. "/" .. tostring(MELensRV == nil)]=]}); return 1
'@
    [void](Lua $ClientLuaPortA $serverProbe)
    $expectedRuntimeProbe = if ($ServerJava) { '^true/false$' } else { '^true/true$' }
    $session.serverRuntimeProbeExpected = $expectedRuntimeProbe
    $session.serverRuntimeProbe = Wait-Lua $a 'return MELensDevResult and MELensDevResult.id==20601 and MELensDevResult.text or "waiting"' $expectedRuntimeProbe 30
    Capture $a 'first-frame'
    Write-Host 'FIRST_FRAME_READY client-a'
    $b = Start-NativeClient $profileB $ClientLuaPortB
    $previousPort = $env:MELENS_LUA_PORT
    try { & (Join-Path $PSScriptRoot 'mp_connect.ps1') -Port $ServerPort -User 'MELensGuest' -Password $guestSecret -LuaPort $ClientLuaPortB -OwnedClientPid $b.gameId -OwnedClientStartTicks $b.startTicks -OwnedServerPid $server.Id -OwnedServerStartTicks $session.serverStartTicks -OwnedServerConsole $serverConsole -DeferWorldSetup }
    finally { $env:MELENS_LUA_PORT = $previousPort }
    Finish-Connection $b
    Capture $b 'first-frame'
    Write-Host 'FIRST_FRAME_READY client-b'
    $session.clients = @($clients | ForEach-Object { @{ name = $_.name; pid = $_.gameId; port = $_.port; home = $_.profile.home; cache = $_.profile.cache; path = $_.path } })
    $session.status = 'review-ready'; Write-Json (Join-Path $runPath 'session.json') $session
    Write-Host "MP_REVIEW_READY $runPath"
    $deadline = [DateTime]::UtcNow.AddMinutes($ReviewMinutes)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($server.HasExited -or -not (Alive $a) -or -not (Alive $b)) { throw 'An owned MP process exited during review' }
        Complete-ReviewDriver
        $request = Join-Path $runPath 'request.json'
        if (Test-Path -LiteralPath $request) {
            try {
                $q = Get-Content -LiteralPath $request -Raw | ConvertFrom-Json
                Remove-Item -LiteralPath $request
                if ($q.action -eq 'stop') { $session.status = 'stopped-by-request'; break }
                if ($q.action -eq 'driver') { Start-ReviewDriver $q $deadline }
                elseif ($script:driver) { throw 'A native driver is active; concurrent Lua/screenshots are rejected to preserve its authority/input sequence' }
                else {
                    $target = if ($q.client -eq 'B') { $b } else { $a }
                    if ($q.lua) { Write-Json (Join-Path $runPath 'response.json') (Lua $target.port $q.lua) }
                    if ($q.shot) { Capture $target $q.shot }
                }
            } catch {
                Write-Json (Join-Path $runPath 'response.json') @{ status = 'rejected'; error = $_.Exception.Message; utc = [DateTime]::UtcNow.ToString('o') }
                Write-Host "MP_REQUEST_REJECTED $($_.Exception.Message)"
            }
        }
        Start-Sleep -Milliseconds 200
    }
    if ($session.status -eq 'review-ready') { $session.status = 'bounded-review-expired' }
} catch {
    $session.status = 'failed'; $session.error = $_.Exception.Message
    throw
} finally {
    try { Complete-ReviewDriver 'stopped-with-parent' }
    catch { $session.driverCleanupError = $_.Exception.Message; Write-Host "MP_DRIVER_CLEANUP_ERROR $($_.Exception.Message)" }
    # Process objects/creation-time identities only: never terminate by name.
    if ($server -and -not $server.HasExited) {
        try { $server.StandardInput.WriteLine('save'); $server.StandardInput.Flush(); $server.StandardInput.WriteLine('quit'); $server.StandardInput.Flush() } catch { }
    }
    foreach ($client in $clients) {
        if (Alive $client) { try { [void](Lua $client.port 'getCore():quitToDesktop(); return 1' 3) } catch { } }
    }
    foreach ($client in $clients) {
        if (Alive $client) {
            $process = Get-Process -Id $client.gameId -ErrorAction SilentlyContinue
            if ($process -and -not $process.WaitForExit(10000) -and (Alive $client)) { Stop-Process -Id $client.gameId -Force -ErrorAction SilentlyContinue }
        }
        if ($client.keeper -and -not $client.keeper.WaitForExit(5000)) { $client.keeper.Kill($true) }
        if ($client.stdout.IsCompleted) { [IO.File]::WriteAllText((Join-Path $client.path 'keeper-stdout.log'), $client.stdout.Result) }
        if ($client.stderr.IsCompleted) { [IO.File]::WriteAllText((Join-Path $client.path 'keeper-stderr.log'), $client.stderr.Result) }
    }
    if ($server) {
        if (-not $server.WaitForExit(15000)) { $server.Kill($true); [void]$server.WaitForExit(5000) }
        if ($server.HasExited) { $session.serverExitCode = $server.ExitCode }
        if ($serverStdout -and $serverStdout.IsCompleted) { [IO.File]::WriteAllText((Join-Path $runPath 'server\stdout.log'), $serverStdout.Result) }
        if ($serverStderr -and $serverStderr.IsCompleted) { [IO.File]::WriteAllText((Join-Path $runPath 'server\stderr.log'), $serverStderr.Result) }
    }
    $session.finishedUtc = [DateTime]::UtcNow.ToString('o')
    Write-Json (Join-Path $runPath 'session.json') $session
    Write-Host 'OWNED_MP_PROCESSES_STOPPED'
}

# Isolated fresh-process lifecycle phases. Root launches each complete lifetime through run-heavy.
# Baseline -> Enabled (normal cleanup, Clean checkpoint) -> Disabled -> Reenabled.
param(
    [ValidateSet('Baseline', 'Control', 'Enabled', 'Clean', 'Disabled', 'Reenabled')][string]$Phase = 'Baseline',
    [string]$Run = 'final-lifecycle-206',
    [ValidateRange(1, 60)][int]$ReviewMinutes = 20
)
. (Join-Path $PSScriptRoot '..\scripts\common.ps1')
. (Join-Path $PSScriptRoot 'existing-test-acknowledgements.ps1')
$ErrorActionPreference = 'Stop'
if ($Run -notmatch '^[a-z0-9-]+$') { throw 'Run must be a simple owned folder name' }
$runPath = [IO.Path]::GetFullPath((Join-Path $Lens.Out $Run))
if (-not $runPath.StartsWith($Lens.Out + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid owned lifecycle run' }
if (@(Get-LensGameProcesses).Count) { throw 'A PZ client is already running; lifecycle phase deferred' }
if (@([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object Port -eq 18470).Count) { throw 'Lua port is occupied' }
$manifestPath = Join-Path $runPath 'lifecycle.json'
if ($Phase -eq 'Baseline') {
    if (Test-Path -LiteralPath $runPath) { throw 'Baseline requires a new owned run folder' }
    New-Item -ItemType Directory -Path $runPath | Out-Null
    $manifest = [ordered]@{ world = $null; phase = 'preparing'; receipts = @(); profile = (Join-Path $runPath 'home'); scope = 'Disposable KI5 save; only RVI toggled between fresh processes' }
} else {
    if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Run the Baseline phase first' }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -AsHashtable
    if (-not $manifest.world -or $manifest.world -notmatch '^melens-test-[0-9]+$') { throw 'Owned baseline save identity missing' }
    if ($Phase -eq 'Disabled' -and $manifest.phase -ne 'Clean') { throw 'A passed Clean checkpoint is required before disabling' }
    if ($Phase -eq 'Reenabled' -and $manifest.phase -ne 'Disabled') { throw 'A passed Disabled checkpoint is required before re-enabling' }
}
$phasePath = Join-Path $runPath ($Phase.ToLowerInvariant() + '-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))
if (Test-Path -LiteralPath $phasePath) { throw 'Phase artifact folder already exists' }
New-Item -ItemType Directory -Path $phasePath | Out-Null
$homeDir = Join-Path $runPath 'home'
$cache = Join-Path $homeDir 'Zomboid'
$mods = Join-Path $cache 'mods'
$screens = Join-Path $cache 'Screenshots'
$zbConfig = Join-Path $homeDir 'zombie_buddy'
$rviOn = $Phase -in @('Enabled', 'Clean', 'Reenabled')
$python = Get-LensPython
$java = Join-Path $Lens.GameRoot 'jre64\bin\java.exe'
$keeper = $null; $gameId = 0; $gameStartTicks = 0; $stdout = $null; $stderr = $null
$session = [ordered]@{ phase = $Phase; rviEnabled = $rviOn; status = 'preparing'; startedUtc = [DateTime]::UtcNow.ToString('o'); inactiveDesktop = $true; stockClasses = $true; profile = $homeDir }

function Write-Json([string]$path, $value) { [IO.File]::WriteAllText($path, ($value | ConvertTo-Json -Depth 18), [Text.UTF8Encoding]::new($false)) }
function Lua([string]$code, [int]$timeout = 15) {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:18470/lua?depth=10&sandbox=false' -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($code)) -ContentType 'text/plain' -TimeoutSec $timeout
    $reply = $r.Content | ConvertFrom-Json
    if (-not $reply.ok) { throw "Lifecycle Lua: $($reply.error) $($reply.stack)" }
    return $reply.result
}
function Alive {
    if (-not $gameId) { return $false }
    $process = Get-Process -Id $gameId -ErrorAction SilentlyContinue
    return $process -and $process.Path -eq $java -and $process.StartTime.ToUniversalTime().Ticks -eq $gameStartTicks
}
function Wait-Lua([string]$code, [string]$match, [int]$seconds = 180) {
    $deadline = [DateTime]::UtcNow.AddSeconds($seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (-not (Alive)) { throw 'Owned lifecycle client exited while waiting' }
        try { $result = Lua $code; if ([string]$result -match $match) { return $result } } catch { }
        Start-Sleep -Milliseconds 300
    }
    throw "Lifecycle readiness timeout: $code"
}
function Shot([string]$name) {
    if ($name -notmatch '^[a-z0-9-]+$') { throw 'Invalid capture name' }
    $source = Join-Path $screens "$name.png"
    if (Test-Path -LiteralPath $source) { Remove-Item -LiteralPath $source }
    [void](Lua "MEMCNativeLab.capture('$name.png'); return true")
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $source) {
            try {
                $bytes = [IO.File]::ReadAllBytes($source)
                if ($bytes.Length -ge 12 -and [Convert]::ToHexString($bytes[($bytes.Length - 12)..($bytes.Length - 1)]) -eq '0000000049454E44AE426082') {
                    Copy-Item -LiteralPath $source -Destination (Join-Path $phasePath "$name.png")
                    return
                }
            } catch { }
        }
        Start-Sleep -Milliseconds 100
    }
    throw 'Native lifecycle screenshot not complete'
}
function Checkpoint([string]$which, [switch]$Save) {
    if ($which -notin @('Baseline', 'Control', 'Enabled', 'Clean', 'Disabled', 'Reenabled')) { throw 'Unknown lifecycle checkpoint' }
    if ($which -eq 'Clean' -and -not $rviOn) { throw 'Clean checkpoint requires enabled RVI' }
    $code = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'lua\lifecycle-phase.lua')).Replace('"PHASE"', ('"' + $which + '"'))
    $receipt = Lua $code
    if ($which -eq 'Baseline' -and $receipt.preparing) {
        Write-Json (Join-Path $phasePath 'baseline-spawn-preparation.json') $receipt
        # addVehicleDebug/repair precedes stock KI5 part initialization. Capture
        # committed native IDs only after ordinary simulation has settled it.
        Start-Sleep -Milliseconds 2500
        [void](Wait-Lua 'return MELensLifecycleTest and MELensLifecycleTest.vehicle:isStopped() and "settled" or "waiting"' '^settled$' 30)
        $receipt = Lua $code
        $receipt | Add-Member -NotePropertyName baselineSettledBeforeCargo -NotePropertyValue $true
    }
    Write-Json (Join-Path $phasePath ("checkpoint-" + $which.ToLowerInvariant() + '.json')) $receipt
    if ($Save) {
        [void](Lua 'GameWindow.save(true); return true' 60)
        $manifest.world = $receipt.world; $manifest.phase = $which
        $manifest.receipts = @($manifest.receipts) + @(@{ phase = $which; path = $phasePath; savedUtc = [DateTime]::UtcNow.ToString('o') })
        Write-Json $manifestPath $manifest
    }
    Write-Host "LIFECYCLE_CHECKPOINT $which saved=$([bool]$Save)"
    return $receipt
}

try {
    if ($Phase -eq 'Baseline') {
        New-Item -ItemType Directory -Path $mods, $zbConfig, $screens | Out-Null
        foreach ($dep in $Lens.Dependencies) {
            $source = Join-Path $Lens.Workshop "$($dep.Item)\mods\$($dep.Folder)"
            if (-not (Test-Path -LiteralPath $source)) { throw "Missing read-only dependency $($dep.Id)" }
            Copy-Item -LiteralPath $source -Destination $mods -Recurse
        }
        Copy-Item -LiteralPath (Join-Path $Lens.Root 'dev\RealVehicleInteriors_Dev') -Destination $mods -Recurse
        $classes = Join-Path $runPath 'dev-classes'; New-Item -ItemType Directory -Path $classes | Out-Null
        $sources = @(Get-ChildItem -LiteralPath (Join-Path $Lens.Root 'dev\java') -Filter *.java -Recurse | ForEach-Object FullName)
        & (Join-Path $Lens.Jdk 'javac.exe') --release 25 -d $classes -cp "$(Join-Path $Lens.GameRoot 'projectzomboid.jar');$(Join-Path $Lens.GameRoot 'ZombieBuddy.jar')" @sources
        if ($LASTEXITCODE) { throw 'Lifecycle adapter compile failed' }
        $jarDir = Join-Path $mods 'RealVehicleInteriors_Dev\42.21\media\java'; New-Item -ItemType Directory -Path $jarDir -Force | Out-Null
        & (Join-Path $Lens.Jdk 'jar.exe') --create --file (Join-Path $jarDir 'RealVehicleInteriors_Dev.jar') -C $classes .
        if ($LASTEXITCODE) { throw 'Lifecycle adapter packaging failed' }
        [IO.File]::WriteAllText((Join-Path $mods 'reset-mods-42_00.txt'), 'Owned isolated lifecycle profile.')
        $baselineOptions = "version=8`nfullScreen=false`nborderless=false`nwidth=1280`nheight=720`nfocusloss=false`ntextureCompression=true`ntexture2x=false`nuncappedFPS=false`nframeRate=30`nsoundVolume=0`n"
        $baselineOptions = Add-ExistingTestAcknowledgements $baselineOptions (Join-Path $Lens.TestHome 'Zomboid\options.ini')
        [IO.File]::WriteAllText((Join-Path $cache 'options.ini'), $baselineOptions)
        Write-Json $manifestPath $manifest
    } else {
        $savePath = [IO.Path]::GetFullPath((Join-Path $cache "Saves\Sandbox\$($manifest.world)"))
        if (-not $savePath.StartsWith($cache + '\', [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $savePath)) { throw 'Owned lifecycle save not found' }
        Copy-Item -LiteralPath $savePath -Destination (Join-Path $phasePath 'save-before') -Recurse
    }
    if ($rviOn -and -not (Test-Path -LiteralPath (Join-Path $mods 'RealVehicleInteriors'))) {
        if (-not (Test-Path -LiteralPath (Join-Path $Lens.Package '42.21\media\java\RealVehicleInteriors.jar'))) { throw 'Build the final RVI package first' }
        Copy-Item -LiteralPath $Lens.Package -Destination $mods -Recurse
    }
    $active = @('ZombieBuddy', 'damnlib', 'KI5campers', '87fordB700', 'KI5trailers')
    if ($rviOn) { $active += 'RealVehicleInteriors' }
    $active += 'RealVehicleInteriors_Dev'
    $modList = "VERSION = 1,`nmods`n{`n" + (($active | ForEach-Object { "    mod = $_," }) -join "`n") + "`n}`nmaps`n{`n}`n"
    [IO.File]::WriteAllText((Join-Path $mods 'default.txt'), $modList)
    if ($manifest.world) {
        # The stock Continue path reads the save's own mods.txt. Changing just
        # default.txt would silently reload the prior RVI state.
        [IO.File]::WriteAllText((Join-Path $cache "Saves\Sandbox\$($manifest.world)\mods.txt"), $modList)
    }
    $session.activeMods = $active
    $command = @($java, '-Xms256m', '-Xmx3072m', '-XX:MaxDirectMemorySize=128m', '-XX:ReservedCodeCacheSize=128m',
        '--enable-native-access=ALL-UNNAMED', '--add-exports=java.base/jdk.internal.misc=ALL-UNNAMED', '-Djava.awt.headless=true',
        '-Djava.library.path=win64/;.', '-XX:-OmitStackTraceInFastThrow', '-Dzomboid.steam=0', "-Duser.home=$homeDir",
        '-Dpzopt.enabled=false', '-Dpzopt.gcMode=stock', '-Dpzopt.jitSteady=false', '-Dpzopt.aotCache=false', '-Dpzopt.updateCheck=false',
        '-Dmelens.dev.port=18470', "-agentlib:zbNative=policy=allow-all,verbosity=1,config_dir=$zbConfig",
        '-cp', 'projectzomboid.jar;.', 'zombie.gameStates.MainScreenState', '-nosteam', "-cachedir=$cache")
    $config = Join-Path $phasePath 'native-session.json'; Write-Json $config @{ command = $command; cwd = $Lens.GameRoot }
    $psi = [Diagnostics.ProcessStartInfo]::new(); $psi.FileName = $python
    $psi.ArgumentList.Add([IO.Path]::GetFullPath((Join-Path $Lens.Root 'dev\windows-test-session.py'))); $psi.ArgumentList.Add($config)
    $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    $psi.Environment['PATH'] = "$($Lens.GameRoot)\win64;$($Lens.GameRoot);$env:PATH"
    foreach ($key in @('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS')) { [void]$psi.Environment.Remove($key) }
    $keeper = [Diagnostics.Process]::Start($psi); $stdout = $keeper.StandardOutput.ReadToEndAsync(); $stderr = $keeper.StandardError.ReadToEndAsync()
    $started = Join-Path $phasePath 'native-session-started.json'
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    while (-not (Test-Path -LiteralPath $started)) {
        if ($keeper.HasExited -or [DateTime]::UtcNow -ge $deadline) { throw 'Inactive lifecycle launch did not return owned PID' }
        Start-Sleep -Milliseconds 200
    }
    $gameId = (Get-Content -LiteralPath $started -Raw | ConvertFrom-Json).pid
    $gameStartTicks = (Get-Process -Id $gameId -ErrorAction Stop).StartTime.ToUniversalTime().Ticks
    $session.pid = $gameId
    [void](Wait-Lua 'return MainScreen and MainScreen.instance and MEMCNativeLab and "menu" or "waiting"' '^menu$')
    Write-Host 'MAIN_MENU_READY'
    [void](Lua 'UIManager.setShowLuaDebuggerOnError(false); return true')
    if ((Lua 'return tostring(ActiveMods.requiresResetLua(ActiveMods.getById("default")))') -eq 'true') {
        [void](Lua 'getCore():ResetLua("default","Force"); return true')
        [void](Wait-Lua 'return MainScreen and MainScreen.instance and MEMCNativeLab and "menu" or "waiting"' '^menu$')
    }
    $expected = if ($rviOn) { 'true/true' } else { 'false/false' }
    [void](Wait-Lua 'return tostring(MELens~=nil and MELens.VERSION~=nil).."/"..tostring(MELensRV~=nil)' ('^' + $expected + '$') 30)
    if ($manifest.world) { [void](Lua "MainScreen.continueLatestSave('Sandbox','$($manifest.world)'); return true") }
    else { [void](Lua ([IO.File]::ReadAllText((Join-Path $PSScriptRoot 'lua\newgame.lua')))) }
    $loadDeadline = [DateTime]::UtcNow.AddSeconds(240)
    $gameLog = Join-Path $phasePath 'stdout.log'
    while (-not ((Test-Path -LiteralPath $gameLog) -and (Select-String -LiteralPath $gameLog -Pattern 'game loading took' -Quiet))) {
        if (-not (Alive) -or [DateTime]::UtcNow -ge $loadDeadline) { throw 'Owned lifecycle world did not finish loading' }
        Start-Sleep -Milliseconds 300
    }
    # GameLoadingState is deliberately parked before its click, as in the
    # existing workshop harness. Release only after its finished-load marker.
    [void](Wait-Lua 'if MELensMedia then MELensMedia.start() end; GameWindow.doRenderEvent(true); return isIngameState() and getPlayer() and getPlayer():getCurrentSquare() and "world" or "waiting"' '^world$' 240)
    [void](Lua ([IO.File]::ReadAllText((Join-Path $PSScriptRoot 'lua\setup.lua'))))
    [void](Lua 'MEMCNativeLab.releaseKeys(); ISUIHandler.setVisibleAllUI(false); return true')
    Write-Host 'WORLD_READY'
    if ($Phase -ne 'Clean') { $session.initialReceipt = Checkpoint $Phase -Save }
    Shot ('lifecycle-' + $Phase.ToLowerInvariant())
    Write-Host 'FIRST_FRAME_READY'
    $session.status = 'review-ready'; Write-Json (Join-Path $phasePath 'session.json') $session
    Write-Host "LIFECYCLE_REVIEW_READY $phasePath"
    $deadline = [DateTime]::UtcNow.AddMinutes($ReviewMinutes)
    while ([DateTime]::UtcNow -lt $deadline -and (Alive)) {
        $request = Join-Path $phasePath 'request.json'
        if (Test-Path -LiteralPath $request) {
            $q = Get-Content -LiteralPath $request -Raw | ConvertFrom-Json; Remove-Item -LiteralPath $request
            if ($q.action -eq 'stop') { $session.status = 'stopped-by-request'; break }
            try {
                if ($q.action -eq 'checkpoint') { Write-Json (Join-Path $phasePath 'response.json') (Checkpoint ([string]$q.phase) -Save) }
                if ($q.lua) { Write-Json (Join-Path $phasePath 'response.json') (Lua $q.lua) }
                if ($q.shot) { Shot $q.shot }
            } catch { Write-Json (Join-Path $phasePath 'response.json') @{ ok = $false; error = $_.Exception.Message }; Write-Warning $_.Exception.Message }
        }
        Start-Sleep -Milliseconds 200
    }
    if ($session.status -eq 'review-ready') { $session.status = 'bounded-review-expired' }
} catch { $session.status = 'failed'; $session.error = $_.Exception.Message; throw }
finally {
    if (Alive) {
        try { [void](Lua 'MEMCNativeLab.releaseKeys(); getCore():quitToDesktop(); return true' 3) } catch { }
        $process = Get-Process -Id $gameId -ErrorAction SilentlyContinue
        if ($process -and -not $process.WaitForExit(10000) -and (Alive)) { Stop-Process -Id $gameId -Force -ErrorAction SilentlyContinue }
        if ($process -and $process.HasExited) { $session.gameExitCode = $process.ExitCode }
    }
    if ($keeper -and -not $keeper.WaitForExit(5000)) { $keeper.Kill($true); [void]$keeper.WaitForExit(5000) }
    if ($stdout -and $stdout.IsCompleted) { [IO.File]::WriteAllText((Join-Path $phasePath 'keeper-stdout.log'), $stdout.Result) }
    if ($stderr -and $stderr.IsCompleted) { [IO.File]::WriteAllText((Join-Path $phasePath 'keeper-stderr.log'), $stderr.Result) }
    $session.finishedUtc = [DateTime]::UtcNow.ToString('o'); Write-Json (Join-Path $phasePath 'session.json') $session
    Write-Host 'OWNED_LIFECYCLE_PROCESSES_STOPPED'
}

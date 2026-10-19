# Owned gameplay-media capture on an inactive desktop. Run the entire lifetime through run-heavy.mjs.
param([string]$Run = 'workshop-20261017', [switch]$GroundOnly, [string]$Scenario, [string]$LoadWorld,
    [switch]$FreshProfile, [ValidateRange(1,60)][int]$ReviewMinutes = 30,
    [switch]$LowMemory,
    [string]$Driver, [string[]]$DriverArguments = @(),
    [switch]$AllowOtherGames) # this game/input/capture stay on a separate inactive desktop
. (Join-Path $PSScriptRoot '..\scripts\common.ps1')
$runPath = [IO.Path]::GetFullPath((Join-Path $Lens.Out $Run))
if (-not $runPath.StartsWith($Lens.Out + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid media output' }
New-Item -ItemType Directory -Path $runPath -Force | Out-Null
# All recursive replacements in Prepare are confined to these prevalidated owned build paths.
foreach ($path in @('testhome\Zomboid\mods\RealVehicleInteriors', 'dev-classes', 'testhome\Zomboid\mods\RealVehicleInteriors_Dev')) {
    $absolute = [IO.Path]::GetFullPath((Join-Path $Lens.Out $path))
    if (-not $absolute.StartsWith($Lens.Out + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid prepare path' }
}
$otherGames = @(Get-LensGameProcesses)
if ($otherGames.Count -and -not $AllowOtherGames) { throw 'Another Project Zomboid game is running; capture deferred' }
if ($otherGames.Count) { Write-Host "Other game PIDs left untouched: $($otherGames.ProcessId -join ', ')" }
if ($FreshProfile) {
    $Lens.TestHome = Join-Path $runPath 'home'
    if (Test-Path -LiteralPath $Lens.TestHome) { throw 'Fresh profile already exists; choose a new Run' }
}
& (Join-Path $Lens.Root 'scripts\testgame.ps1') -Mode Prepare -ProfilePath $Lens.TestHome
$homeDir = $Lens.TestHome
$cache = Join-Path $homeDir 'Zomboid'
$screens = Join-Path $cache 'Screenshots'
New-Item -ItemType Directory -Path $screens -Force | Out-Null
$options = Join-Path $cache 'options.ini'
$text = [IO.File]::ReadAllText($options)
$text = [regex]::Replace($text, '(?m)^width=.*$', 'width=1280')
$text = [regex]::Replace($text, '(?m)^height=.*$', 'height=720')
$text = [regex]::Replace($text, '(?m)^textureCompression=.*$', 'textureCompression=true')
$texture2x = if ($LowMemory) { 'false' } else { 'true' }
$text = [regex]::Replace($text, '(?m)^texture2x=.*$', "texture2x=$texture2x")
[IO.File]::WriteAllText($options, $text)
$zbConfig = Join-Path $homeDir 'zombie_buddy'
$java = Join-Path $Lens.GameRoot 'jre64\bin\java.exe'
$heap = if ($LowMemory) { '-Xmx2048m' } else { '-Xmx3072m' }
$command = @($java, '-Xms256m', $heap, '-XX:MaxDirectMemorySize=256m', '-XX:ReservedCodeCacheSize=192m',
    '--enable-native-access=ALL-UNNAMED', '--add-exports=java.base/jdk.internal.misc=ALL-UNNAMED',
    '-Djava.awt.headless=true', '-Djava.library.path=win64/;.', '-XX:-OmitStackTraceInFastThrow',
    '-Dzomboid.steam=0', "-Duser.home=$homeDir", '-Dpzopt.enabled=false', '-Dpzopt.gcMode=stock', '-Dpzopt.jitSteady=false', '-Dpzopt.aotCache=false',
    '-Dpzopt.updateCheck=false', '-Dmelens.dev.port=18470',
    "-agentlib:zbNative=policy=allow-all,verbosity=1,config_dir=$zbConfig", '-cp', 'projectzomboid.jar;.',
    'zombie.gameStates.MainScreenState', '-nosteam', "-cachedir=$cache")
$configPath = Join-Path $runPath 'native-session.json'
@{ command = $command; cwd = $Lens.GameRoot } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $configPath -Encoding utf8
$psi = [Diagnostics.ProcessStartInfo]::new()
$psi.FileName = Get-LensPython
$psi.ArgumentList.Add((Join-Path $Lens.Root 'dev\windows-test-session.py'))
$psi.ArgumentList.Add($configPath)
$psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
$psi.Environment['PATH'] = "$($Lens.GameRoot)\win64;$($Lens.GameRoot);$env:PATH"
foreach ($key in @('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS')) { [void]$psi.Environment.Remove($key) }
$keeper = $null; $gameId = 0; $gameStartedAt = $null
$driverExitCode = 0

function OwnedGameAlive {
    if (-not $gameId -or -not $gameStartedAt) { return $false }
    $candidate = Get-Process -Id $gameId -ErrorAction SilentlyContinue
    return $candidate -and $candidate.Path -eq $java -and $candidate.StartTime -eq $gameStartedAt
}

function Lua([string]$code) {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:18470/lua?depth=3&sandbox=false' -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($code)) -TimeoutSec 60
    $result = $r.Content | ConvertFrom-Json
    if (-not $result.ok) { throw "Capture Lua: $($result.error) $($result.stack)" }
    return $result.result
}
function Wait-Lua([string]$code, [string]$match, [int]$seconds = 240) {
    $deadline = [DateTime]::UtcNow.AddSeconds($seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($gameId -and -not (OwnedGameAlive)) { throw 'Owned game exited during startup' }
        try { $value = Lua $code; if ([string]$value -match $match) { return $value } } catch { }
        Start-Sleep -Milliseconds 1000
    }
    throw "Timed out: $code"
}
function Shot([string]$name) {
    $path = Join-Path $screens "$name.png"
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
    [void](Lua "MEMCNativeLab.capture('$name.png'); return 1")
    for ($i = 0; $i -lt 40; $i++) { if (Test-Path -LiteralPath $path) { break }; Start-Sleep -Milliseconds 100 }
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing screenshot: $name" }
    Start-Sleep -Milliseconds 150
    Copy-Item -LiteralPath $path -Destination (Join-Path $runPath "$name.png") -Force
}
try {
    $keeper = [Diagnostics.Process]::Start($psi)
    $stdout = $keeper.StandardOutput.ReadToEndAsync(); $stderr = $keeper.StandardError.ReadToEndAsync()
    $started = Join-Path $runPath 'native-session-started.json'
    for ($i = 0; $i -lt 30; $i++) { if (Test-Path -LiteralPath $started) { break }; Start-Sleep -Milliseconds 500 }
    if (-not (Test-Path -LiteralPath $started)) { throw "No inactive desktop launch: $($stderr.Result)" }
    $gameId = (Get-Content -LiteralPath $started -Raw | ConvertFrom-Json).pid
    $gameStartedAt = (Get-Process -Id $gameId -ErrorAction Stop).StartTime
    Write-Host "Owned game $gameId started on an inactive desktop"
    [void](Wait-Lua 'return MainScreen and MainScreen.instance and "menu" or "waiting"' 'menu')
    Write-Host 'MAIN_MENU_READY'
    [void](Lua 'UIManager.setShowLuaDebuggerOnError(false); pcall(function() doLuaDebuggerAction("Resume") end); return 1')
    if ((Lua 'return tostring(ActiveMods.requiresResetLua(ActiveMods.getById("default")))') -eq 'true') {
        [void](Lua 'getCore():ResetLua("default", "Force"); return 1')
        Start-Sleep -Seconds 3
        [void](Wait-Lua 'return MainScreen and MainScreen.instance and MELens and "ready" or "waiting"' 'ready')
    }
    if ($LoadWorld) {
        if ($LoadWorld -notmatch '^melens-test-[0-9]+$') { throw 'Only owned media saves may be loaded' }
        Write-Host (Lua "MainScreen.continueLatestSave('Sandbox','$LoadWorld'); return 'loading $LoadWorld'")
    } else {
        Write-Host (Lua (Get-Content -LiteralPath (Join-Path $Lens.Root 'dev\lua\newgame.lua') -Raw))
    }
    $loadDeadline = [DateTime]::UtcNow.AddSeconds(180)
    $gameLog = Join-Path $runPath 'stdout.log'
    while (-not (Select-String -LiteralPath $gameLog -Pattern 'game loading took' -Quiet)) {
        if ([DateTime]::UtcNow -ge $loadDeadline) { throw 'World did not finish loading' }
        if (-not (OwnedGameAlive)) { throw 'Owned game exited while loading' }
        Start-Sleep -Milliseconds 500
    }
    [void](Lua 'MELensMedia.start(); GameWindow.doRenderEvent(true); return 1')
    [void](Wait-Lua 'return isIngameState() and "world" or "waiting"' '^world$' 60)
    Write-Host 'WORLD_READY'
    Start-Sleep -Seconds 3
    [void](Lua (Get-Content -LiteralPath (Join-Path $Lens.Root 'dev\lua\setup.lua') -Raw))
    [void](Lua 'local p = getPlayer(); p:setX(10813.5); p:setY(10140.5); p:setLastX(10813.5); p:setLastY(10140.5); return 1')
    Start-Sleep -Seconds 2
    if ($GroundOnly) {
        [void](Lua 'getCore():setAutoZoom(0,false); getCore():doZoomScroll(0,-1); ISUIHandler.setVisibleAllUI(false); return 1')
        Start-Sleep -Seconds 2
        Shot 'ground-ready'
        Write-Host 'FIRST_FRAME_READY'
    } else {
    $spawn = (Get-Content -LiteralPath (Join-Path $Lens.Root 'dev\lua\spawn_one.lua') -Raw).Replace('NAME', 'Base.Trailer54FlyingCloud22').Replace('tonumber("7")', 'tonumber("-4")')
    Write-Host (Lua $spawn)
    [void](Lua 'local p = getPlayer(); p:setPrimaryHandItem(nil); p:setSecondaryHandItem(nil); getCore():doZoomScroll(0,-1); getCore():doZoomScroll(0,-1); local c=UIManager.getDebugConsole(); if c then c:setVisible(false) end; ISUIHandler.setVisibleAllUI(false); return 1')
    Start-Sleep -Seconds 3
    Shot 'outside'
    Write-Host 'FIRST_FRAME_READY'
    $record = [Diagnostics.Stopwatch]::StartNew(); $frames = [Collections.Generic.List[object]]::new()
    $entered = $false; $walked = $false; $index = 0
    while ($record.Elapsed.TotalSeconds -lt 13) {
        $t = $record.Elapsed.TotalSeconds
        if (-not $entered -and $t -ge 1.5) {
            Write-Host (Lua (Get-Content -LiteralPath (Join-Path $Lens.Root 'dev\lua\walkin.lua') -Raw)); $entered = $true
        }
        if (-not $walked -and $t -ge 7) {
            [void](Lua 'local p=getPlayer(); if MELens.isStanding(p) then local v=p:getVehicle(); local q=MELens.profileFor(v); local g=MELens.WalkGrids[q.walkGrid]; MELens.walkTo(p,q.aisleX or 0,g.z0 + #g.rows*g.cell/2); return "walking" end; return "waiting"')
            $walked = $true
        }
        $name = 'enter-{0:D4}' -f $index
        Shot $name
        $frames.Add(@{ file = "$name.png"; seconds = $t })
        $index++
        Start-Sleep -Milliseconds 65
    }
    $frames | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runPath 'frames.json') -Encoding utf8
    Write-Host "ENTRY_RECORDED $index frames"
    [void](Lua 'local p=getPlayer(); return MELens.isStanding(p) and "inside" or error("entry did not finish")')
    Shot 'interior'
    [void](Lua 'ISUIHandler.setVisibleAllUI(true); local p=getPlayer(); MELens.Dashboard.open(p,p:getVehicle()); local w=MELens.Dashboard.instance; w:setX(45); w:setY(45); return {x=w:getX(),y=w:getY(),width=w:getWidth(),height=w:getHeight()}')
    Start-Sleep -Seconds 2
    Shot 'interior-manager'
    Write-Host 'DASHBOARD_CAPTURED'
    }
    if ($Scenario) {
        $scenarioPath = [IO.Path]::GetFullPath((Join-Path $Lens.Root $Scenario))
        if (-not $scenarioPath.StartsWith((Join-Path $Lens.Root 'dev') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Scenario must be an owned dev script' }
        & $scenarioPath
    }
    if ($Driver) {
        $driverPath = [IO.Path]::GetFullPath((Join-Path $Lens.Root $Driver))
        if (-not $driverPath.StartsWith((Join-Path $Lens.Root 'dev') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Driver must be an owned dev script' }
        $env:RVI_CAPTURE_RUN = $Run
        & $psi.FileName $driverPath @DriverArguments
        $driverExitCode = $LASTEXITCODE
        if ($driverExitCode) { Write-Warning "Native driver failed: $driverExitCode; keeping owned review window for diagnosis" }
    }
    # Bounded review window. Only commands written by this task are evaluated in this owned profile.
    $deadline = [DateTime]::UtcNow.AddMinutes($ReviewMinutes)
    Write-Host "REVIEW_READY $runPath"
    while ([DateTime]::UtcNow -lt $deadline) {
        if (-not (OwnedGameAlive)) { break }
        $request = Join-Path $runPath 'request.json'
        if (Test-Path -LiteralPath $request) {
            $q = Get-Content -LiteralPath $request -Raw | ConvertFrom-Json
            Remove-Item -LiteralPath $request
            if ($q.action -eq 'stop') { break }
            if ($q.driver) {
                $driverPath = [IO.Path]::GetFullPath((Join-Path $Lens.Root $q.driver))
                if (-not $driverPath.StartsWith((Join-Path $Lens.Root 'dev') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Driver must be an owned dev script' }
                $env:RVI_CAPTURE_RUN = $Run
                & $psi.FileName $driverPath @($q.arguments)
                $driverExitCode = $LASTEXITCODE
                @{exitCode=$LASTEXITCODE} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runPath 'driver-result.json') -Encoding utf8
            }
            if ($q.lua) {
                try { $result = Lua $q.lua }
                catch { $result = @{ok=$false;error=$_.Exception.Message} }
                $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runPath 'response.json') -Encoding utf8
            }
            if ($q.shot) { Shot $q.shot }
        }
        Start-Sleep -Milliseconds 300
    }
    if ($driverExitCode) { throw "Native driver failed: $driverExitCode" }
} finally {
    if (OwnedGameAlive) {
        try { [void](Lua 'getCore():quitToDesktop(); return "quitting"') } catch { }
        $ownedShutdownDeadline = [DateTime]::UtcNow.AddSeconds(12)
        while ((OwnedGameAlive) -and [DateTime]::UtcNow -lt $ownedShutdownDeadline) { Start-Sleep -Milliseconds 200 }
        if (OwnedGameAlive) { Stop-Process -Id $gameId -Force -ErrorAction SilentlyContinue }
    }
    if ($keeper) {
        [void]$keeper.WaitForExit(10000)
        if (-not $keeper.HasExited) { $keeper.Kill() }
        if ($stdout.IsCompleted) { $stdout.Result | Set-Content -LiteralPath (Join-Path $runPath 'keeper-stdout.log') }
        if ($stderr.IsCompleted) { $stderr.Result | Set-Content -LiteralPath (Join-Path $runPath 'keeper-stderr.log') }
    }
    Write-Host 'OWNED_CAPTURE_PROCESSES_STOPPED'
}

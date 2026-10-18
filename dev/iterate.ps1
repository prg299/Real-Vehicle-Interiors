# Developer helper: one look/layout iteration in one command, ending in ONE image to check.
# Regenerates the profiles and shell configs, bakes the models only when something the bake reads
# changed since the last good bake (retrying Blender's intermittent Cycles crash), builds, restarts
# the isolated test game on the new build, captures only the named vehicles from the preview camera
# and puts them on one sheet. Prints how long each step took. Check every heading
# (dev\review_interiors.ps1) once before calling a change done, not every round.
#   .\dev\iterate.ps1 -Only FlyingCloud22,F700box     a few vehicles (keys or script names, see preview_interiors.ps1)
#   .\dev\iterate.ps1 -All                            all eight
#   .\dev\iterate.ps1 -Only Scamp13 -ShellsOnly       furniture unchanged: rebuild only the shells (seconds)
#   .\dev\iterate.ps1 -Only Scamp13 -NoRestart        capture again, nothing rebuilt (launches the game if closed)
#   .\dev\iterate.ps1 -Only Bambi16 -ForceBake        bake every piece again, although nothing seems changed
#   .\dev\iterate.ps1 -Only Bambi16 -Lua dev\lua\x.lua   run test drivers in the game before the capture
# (rv_kit.py itself re-bakes only the pieces whose mesh, materials or baking code changed: build\rv\bake-cache.json)
# The test game is saved and closed at the end (the project owner does not want an idle game window
# lying around); -KeepOpen leaves it running.
param([string[]]$Only, [switch]$All, [switch]$ShellsOnly, [switch]$ForceBake, [switch]$NoRestart,
      [switch]$AllowOtherGames, [switch]$KeepOpen, [string[]]$Lua, [string]$OutDir)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$blender = 'D:\Programs\Blender Foundation\Blender 3.6\blender.exe'
$keys = @('FlyingCloud22', 'Bambi16', 'Airflyte', 'Astrodome', 'Scamp13', 'Scamp16', 'B700bus', 'F700box')
if ($All) { $Only = $keys }
if (-not $Only) { throw 'Name the vehicles: -Only FlyingCloud22,F700box (or -All)' }
$Only = @($Only | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
if (-not $OutDir) { $OutDir = Join-Path $root ('build\rv\dbg\iter\' + (Get-Date -Format 'MMdd-HHmmss')) }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$times = [ordered]@{}
function Step([string]$name, [scriptblock]$body) {
    $t = [Diagnostics.Stopwatch]::StartNew()
    Write-Host "== $name"
    & $body
    $times[$name] = [math]::Round($t.Elapsed.TotalSeconds)
}

# What the bake reads: the kit, the rings, the shell configs (from the specs), the painted textures
# and the vehicle measurements.
function BakeInputsHash {
    $files = @(
        (Join-Path $root 'tools-src\blender\rv_kit.py'),
        (Join-Path $root 'tools-src\vehicles\shell_rings.py')
    )
    $files += Get-ChildItem (Join-Path $root 'tools-src\blender\cfg') -Filter 'shell_*.json' | ForEach-Object FullName
    $files += Get-ChildItem (Join-Path $root 'tools-src\art\textures') -Filter '*.png' | ForEach-Object FullName
    $files += Get-ChildItem (Join-Path $root 'build\rv\floorplans') -Filter 'measure_*.json' | ForEach-Object FullName
    $lines = $files | Sort-Object | ForEach-Object {
        $_.Substring($root.Length) + ':' + (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash
    }
    $bytes = [Text.Encoding]::UTF8.GetBytes(($lines -join "`n"))
    return [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($bytes)).Replace('-', '')
}

Push-Location $root
try {
    if (-not $NoRestart) {
        Step 'profiles and shell configs' {
            python tools-src\vehicles\make_vehicles.py | Select-Object -Last 2
            if ($LASTEXITCODE) { throw 'make_vehicles.py failed' }
        }
        $stamp = Join-Path $root 'build\rv\bake-inputs.sha256'
        $hash = BakeInputsHash
        $last = if (Test-Path -LiteralPath $stamp) { (Get-Content -LiteralPath $stamp -Raw).Trim() } else { '' }
        if ($ShellsOnly -or $ForceBake -or $hash -ne $last) {
            Step 'bake' {
                # Blender's argument list breaks on spaces in paths: relative paths from the project folder
                $cfgs = Get-ChildItem tools-src\blender\cfg -Filter 'shell_*.json' | ForEach-Object { 'tools-src\blender\cfg\' + $_.Name }
                $bakeArgs = @('-b', '--factory-startup', '--python', 'tools-src\blender\rv_kit.py', '--', 'mod\RealVehicleInteriors\common\media')
                if ($ShellsOnly) { $bakeArgs += '--shells-only' }
                if ($ForceBake) { $bakeArgs += '--no-cache' }          # every piece again (rv_kit.py bake cache)
                $bakeArgs += $cfgs
                $log = Join-Path $root 'build\rv\bake.log'
                $ok = $false
                for ($try = 1; $try -le 5 -and -not $ok; $try++) {
                    & $blender @bakeArgs *> $log
                    $done = Select-String -LiteralPath $log -Pattern '^RVKIT pieces=' -Quiet
                    $failed = Select-String -LiteralPath $log -Pattern 'RVKIT ERROR' | Select-Object -First 1
                    if ($failed) { throw $failed.Line }                         # a real problem: no retry
                    if ($LASTEXITCODE -eq 0 -and $done) { $ok = $true }
                    else { Write-Host "  Blender stopped (exit $LASTEXITCODE; Cycles crashes now and then; the pieces baked so far are cached), try $($try + 1)..." }
                }
                if (-not $ok) { Get-Content -LiteralPath $log -Tail 15 | Write-Host; throw 'bake failed 5 times, see build\rv\bake.log' }
                Select-String -LiteralPath $log -Pattern '^RVKIT pieces=' | ForEach-Object { Write-Host "  $($_.Line)" }
                if (-not $ShellsOnly) { Set-Content -LiteralPath $stamp -Value $hash }
            }
        } else {
            Write-Host '== bake: inputs unchanged since the last bake, skipped'
        }
        # (restart.ps1 builds between stopping and launching: the running game holds the packaged jar)
        Step 'build and restart test game' {
            $jar = Join-Path $root 'build\rv\RealVehicleInteriors.jar'
            $before = if (Test-Path -LiteralPath $jar) { (Get-FileHash -LiteralPath $jar).Hash } else { '' }
            & (Join-Path $root 'dev\restart.ps1') -AllowOtherGames:$AllowOtherGames | Select-Object -Last 1
            if ((Get-FileHash -LiteralPath $jar).Hash -ne $before) {
                Write-Host '  Java changed: ZombieBuddy asks once to approve the new jar on the next real install'
            }
        }
    } else {
        $state = try { & (Join-Path $root 'scripts\lua.ps1') -Code 'return getPlayer() and "ingame" or "menu"' 2>$null } catch { $null }
        if ($state -notmatch 'ingame') {
            Step 'launch test game' {
                & (Join-Path $root 'dev\restart.ps1') -NoBuild -AllowOtherGames:$AllowOtherGames | Select-Object -Last 1
            }
        }
    }
    foreach ($file in $Lua) {
        $r = & (Join-Path $root 'scripts\lua.ps1') -File (Resolve-Path $file)
        Write-Host "  $file -> $r"
    }
    $raw = Join-Path $OutDir 'raw'
    Step 'capture' {
        & (Join-Path $root 'dev\preview_interiors.ps1') -Only $Only -OutDir $raw | Out-Null
    }
    Step 'sheet' {
        $taken = @($keys | Where-Object { Test-Path -LiteralPath (Join-Path $raw "$_.png") })
        if (-not $taken) { throw "no captures in $raw" }
        python dev\preview_crop.py $raw (Join-Path $OutDir 'crops') ($taken | ForEach-Object { "$_|$_|" }) | Out-Null
        $crops = @($taken | ForEach-Object { Join-Path $OutDir "crops\$_.png" })
        $cols = if ($taken.Count -eq 1) { 1 } else { 2 }
        python dev\contact_sheet.py (Join-Path $OutDir 'sheet.png') --cols $cols --width 640 @crops | Out-Null
    }
} finally {
    if (-not $KeepOpen) {
        $t = [Diagnostics.Stopwatch]::StartNew()
        & (Join-Path $root 'dev\close.ps1') | Out-Null
        $times['close'] = [math]::Round($t.Elapsed.TotalSeconds)
    }
    Pop-Location
}
Write-Host ('times (s): ' + (($times.GetEnumerator() | ForEach-Object { "$($_.Key) $($_.Value)" }) -join ', '))
Write-Host "SHEET $(Join-Path $OutDir 'sheet.png')"

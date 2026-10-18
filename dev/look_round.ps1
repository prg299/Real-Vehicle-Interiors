# Developer helper: one round of the furniture look against the game's own furniture: closes the test game, bakes the
# pieces that changed (retrying Blender's crash), builds, and captures the comparison shot (dev\vanilla_compare.ps1).
#   .\dev\look_round.ps1 [-Vehicle Base.Trailer61Airflyte] [-Zoom 0.75] [-AllowOtherGames]
param([string]$Vehicle = 'Base.Trailer61Airflyte', [double]$Zoom = 0.75, [switch]$AllowOtherGames)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    & (Join-Path $PSScriptRoot 'close.ps1') | Out-Null
    $blender = 'D:\Programs\Blender Foundation\Blender 3.6\blender.exe'
    $cfgs = Get-ChildItem tools-src\blender\cfg -Filter 'shell_*.json' | ForEach-Object { 'tools-src\blender\cfg\' + $_.Name }
    $t = Get-Date
    for ($try = 1; $try -le 5; $try++) {
        & $blender -b --factory-startup --python tools-src\blender\rv_kit.py -- mod\RealVehicleInteriors\common\media @cfgs *> build\rv\bake.log
        $err = Select-String build\rv\bake.log -Pattern 'RVKIT ERROR|Traceback' | Select-Object -First 2
        if ($err) { throw ($err | ForEach-Object Line) -join '; ' }
        if ($LASTEXITCODE -eq 0 -and (Select-String build\rv\bake.log -Pattern '^RVKIT pieces=' -Quiet)) { break }
        Write-Host "Blender stopped (exit $LASTEXITCODE), retry"
    }
    Write-Host ("bake {0:N0}s" -f ((Get-Date) - $t).TotalSeconds)
    & (Join-Path $root 'scripts\build.ps1') | Select-Object -Last 1
    $out = Join-Path $root ('build\rv\dbg\compare\' + (Get-Date -Format 'MMdd-HHmmss'))
    & (Join-Path $PSScriptRoot 'vanilla_compare.ps1') -Vehicle $Vehicle -Zoom $Zoom -OutDir $out -AllowOtherGames:$AllowOtherGames | Select-Object -Last 2
    Write-Host "SHOT $out\compare.png"
} finally { Pop-Location }

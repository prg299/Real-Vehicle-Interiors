param([Parameter(Mandatory)][string]$Run)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'workshop-capture.ps1') -Run $Run -FreshProfile -GroundOnly -LowMemory -ReviewMinutes 15 -Driver 'dev/movement-release-tests.py'
if ($LASTEXITCODE) { exit $LASTEXITCODE }

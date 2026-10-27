param([Parameter(Mandatory)][string]$Run,[switch]$Review)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'workshop-capture.ps1') -Run $Run -FreshProfile -GroundOnly -LowMemory -ReviewMinutes 15 -StopAfterDriver:(!$Review) -Driver 'dev/movement-release-tests.py'
if ($LASTEXITCODE) { exit $LASTEXITCODE }

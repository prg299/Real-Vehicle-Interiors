param([Parameter(Mandatory)][string]$Run)
$ErrorActionPreference = 'Stop'
$env:RVI_TEST_CORE_ONLY = '1'
& (Join-Path $PSScriptRoot 'workshop-capture.ps1') -Run $Run -FreshProfile -GroundOnly -LowMemory -StopAfterDriver -Driver 'dev/turning-tests.py'
if ($LASTEXITCODE) { exit $LASTEXITCODE }

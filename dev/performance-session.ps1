# One complete, bounded, inactive-desktop benchmark. Use run-mod-test --kind performance.
param([Parameter(Mandatory)][string]$Run, [string]$BaselineRef, [switch]$WithDogs)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../scripts/common.ps1')
$env:RVI_TEST_CORE_ONLY = '1'
$env:MELENS_TEST_EXTRA = if ($WithDogs) { '3740052292:CompanionDogs' } else { '' }
$env:RVI_PYTHON = Get-LensPython
$env:RVI_JCMD = Join-Path $Lens.Jdk 'jcmd.exe'
$arguments = if ($BaselineRef) { @('--baseline-ref', $BaselineRef) } else { @() }
if ($WithDogs) { $arguments += @('--animal-types', 'hen,dogmale') }
& (Join-Path $PSScriptRoot 'workshop-capture.ps1') -Run $Run -FreshProfile -GroundOnly -LowMemory -Uncapped -StopAfterDriver -Driver 'dev/performance-tests.py' -DriverArguments $arguments
if ($LASTEXITCODE) { exit $LASTEXITCODE }

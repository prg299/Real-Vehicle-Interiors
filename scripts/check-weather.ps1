# Focused precipitation geometry regressions; build the mod first and use run-heavy.mjs.
. (Join-Path $PSScriptRoot 'common.ps1')
$classes = Join-Path $Lens.Out 'classes'
if (-not (Test-Path -LiteralPath (Join-Path $classes 'me/lens/rv/Weather.class'))) { throw 'Build first: scripts/build.ps1' }
$out = Join-Path $Lens.Out 'weather-checks'
New-Item -ItemType Directory -Force -Path $out | Out-Null
& (Join-Path $Lens.Jdk 'javac.exe') -d $out (Join-Path $Lens.Root 'tools-src/WeatherGeometryCheck.java')
if ($LASTEXITCODE) { throw 'Weather geometry check compilation failed' }
& (Join-Path $Lens.Jdk 'java.exe') -Xmx256m -cp "$out;$classes;$(Join-Path $Lens.GameRoot 'projectzomboid.jar')" WeatherGeometryCheck
if ($LASTEXITCODE) { throw 'Weather geometry regression failed' }

# Focused production-Lua regressions with engine doubles; launch through run-heavy.mjs.
. (Join-Path $PSScriptRoot 'common.ps1')
$out = Join-Path $Lens.Out 'release-checks'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$gameJar = Join-Path $Lens.GameRoot 'projectzomboid.jar'
& (Join-Path $Lens.Jdk 'javac.exe') -d $out -cp $gameJar (Join-Path $Lens.Root 'tools-src\LuaRegression.java')
if ($LASTEXITCODE) { throw 'Lua regression runner compilation failed' }
& (Join-Path $Lens.Jdk 'java.exe') -Xmx256m -cp "$out;$gameJar" LuaRegression $Lens.Root $Lens.GameRoot
if ($LASTEXITCODE) { throw 'Lua release regressions failed' }

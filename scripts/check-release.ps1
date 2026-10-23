# Focused production-Lua regressions with engine doubles; launch through run-heavy.mjs.
. (Join-Path $PSScriptRoot 'common.ps1')
$out = Join-Path $Lens.Out 'release-checks'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$gameJar = Join-Path $Lens.GameRoot 'projectzomboid.jar'
& (Join-Path $Lens.Jdk 'javac.exe') -d $out -cp $gameJar (Join-Path $Lens.Root 'tools-src\LuaRegression.java')
if ($LASTEXITCODE) { throw 'Lua regression runner compilation failed' }
& (Join-Path $Lens.Jdk 'java.exe') -Xmx256m -cp "$out;$gameJar" LuaRegression $Lens.Root $Lens.GameRoot
if ($LASTEXITCODE) { throw 'Lua release regressions failed' }

$buddyJar = Join-Path $Lens.GameRoot 'ZombieBuddy.jar'
$sources = @(Get-ChildItem -LiteralPath (Join-Path $Lens.Root 'src') -Recurse -Filter *.java | ForEach-Object FullName)
& (Join-Path $Lens.Jdk 'javac.exe') --release 25 -d $out -cp "$gameJar;$buddyJar" @sources (Join-Path $Lens.Root 'tools-src\CutawayStateCheck.java') (Join-Path $Lens.Root 'tools-src\VisionStateCheck.java')
if ($LASTEXITCODE) { throw 'Cutaway state check compilation failed' }
& (Join-Path $Lens.Jdk 'java.exe') -Xmx256m -cp "$out;$gameJar;$buddyJar" CutawayStateCheck
if ($LASTEXITCODE) { throw 'Cutaway state regressions failed' }
& (Join-Path $Lens.Jdk 'java.exe') -Xmx256m -cp "$out;$gameJar;$buddyJar" me.lens.rv.VisionStateCheck
if ($LASTEXITCODE) { throw 'Vision geometry regressions failed' }

# Builds Real Vehicle Interiors into build\rv\package\RealVehicleInteriors.
#   .\scripts\build.ps1            compile, check and package
#   .\scripts\build.ps1 -Install   also install into %USERPROFILE%\Zomboid\mods (game must be closed)
param([switch]$Install)

. (Join-Path $PSScriptRoot 'common.ps1')

$javac = Join-Path $Lens.Jdk 'javac.exe'
$jar = Join-Path $Lens.Jdk 'jar.exe'
$java = Join-Path $Lens.Jdk 'java.exe'
$gameJar = Join-Path $Lens.GameRoot 'projectzomboid.jar'
$buddyJar = Join-Path $Lens.GameRoot 'ZombieBuddy.jar'
foreach ($path in @($javac, $gameJar, $buddyJar)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing $path" }
}

$classes = Join-Path $Lens.Out 'classes'
$tools = Join-Path $Lens.Out 'tools'
foreach ($dir in @($classes, $tools, (Split-Path $Lens.Package))) {
    $resolved = [IO.Path]::GetFullPath($dir)
    $allowed = [IO.Path]::GetFullPath($Lens.Out).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) { throw "Build output outside $($Lens.Out): $resolved" }
    if (Test-Path -LiteralPath $dir) { Remove-Item -LiteralPath $dir -Recurse -Force }
}
New-Item -ItemType Directory -Force -Path $classes, $tools | Out-Null

Write-Host 'Compiling Java...'
$sources = @(Get-ChildItem -LiteralPath (Join-Path $Lens.Root 'src') -Recurse -Filter *.java | ForEach-Object FullName)
& $javac --release 25 -Xlint:-options -d $classes -cp "$gameJar;$buddyJar" @sources
if ($LASTEXITCODE) { throw 'javac failed' }

# Fixed entry dates: an unchanged build keeps the same SHA-256, so ZombieBuddy
# does not ask for approval again.
$jarFile = Join-Path $Lens.Out 'RealVehicleInteriors.jar'
if (Test-Path -LiteralPath $jarFile) { Remove-Item -LiteralPath $jarFile }
& $jar --create --file $jarFile --date 2026-01-01T00:00:00Z -C $classes .
if ($LASTEXITCODE) { throw 'jar failed' }

Write-Host 'Checking Lua syntax with the game''s Kahlua compiler...'
& $javac -d $tools -cp $gameJar (Join-Path $Lens.Root 'tools-src\LuaCheck.java')
if ($LASTEXITCODE) { throw 'LuaCheck compile failed' }
& $java -Xmx256m -cp "$tools;$($Lens.GameRoot)/*" LuaCheck (Join-Path $Lens.Root 'mod\RealVehicleInteriors')
if ($LASTEXITCODE) { throw 'Lua syntax check failed' }

Write-Host 'Checking JSON translations...'
Get-ChildItem -LiteralPath (Join-Path $Lens.Root 'mod\RealVehicleInteriors') -Recurse -Filter *.json | ForEach-Object {
    try { Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json | Out-Null }
    catch { throw "Invalid JSON: $($_.FullName)" }
}

Write-Host 'Packaging...'
Write-Host 'Reconstructing cutaway shaders from the local game...'
$shaderOutput = Join-Path $Lens.Out 'generated-shaders'
& python (Join-Path $PSScriptRoot 'prepare-shaders.py') --game-root $Lens.GameRoot --output $shaderOutput
if ($LASTEXITCODE) { throw 'Shader reconstruction failed' }
New-Item -ItemType Directory -Force -Path (Split-Path $Lens.Package) | Out-Null
Copy-Item -LiteralPath (Join-Path $Lens.Root 'mod\RealVehicleInteriors') -Destination (Split-Path $Lens.Package) -Recurse
$shaderPackage = Join-Path $Lens.Package 'common\media\shaders'
New-Item -ItemType Directory -Force -Path $shaderPackage | Out-Null
Get-ChildItem -LiteralPath $shaderOutput -File | Copy-Item -Destination $shaderPackage
$javaDir = Join-Path $Lens.Package '42.21\media\java'
New-Item -ItemType Directory -Force -Path $javaDir | Out-Null
Copy-Item -LiteralPath $jarFile -Destination (Join-Path $javaDir 'RealVehicleInteriors.jar')

$sha = [Security.Cryptography.SHA256]::Create()
try { $hash = [Convert]::ToHexString($sha.ComputeHash([IO.File]::ReadAllBytes($jarFile))).ToLowerInvariant() }
finally { $sha.Dispose() }
Write-Host "Built $($Lens.Package)"
Write-Host "RealVehicleInteriors.jar SHA-256 $hash"

if ($Install) {
    & (Join-Path $PSScriptRoot 'install.ps1')
}

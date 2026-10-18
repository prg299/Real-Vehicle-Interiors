# Installs the built package into %USERPROFILE%\Zomboid\mods\RealVehicleInteriors.
# The previous copy is moved to %USERPROFILE%\Zomboid\RealVehicleInteriors-archive, never deleted.
# -PackagePath selects a qualified package such as package-entry-hotfix.py's output.
param([string]$PackagePath)
. (Join-Path $PSScriptRoot 'common.ps1')

if ($PackagePath) { $Lens.Package = (Resolve-Path -LiteralPath $PackagePath).Path }

if (-not (Test-Path -LiteralPath (Join-Path $Lens.Package '42.21\media\java\RealVehicleInteriors.jar'))) {
    throw 'Build first: .\scripts\build.ps1'
}
if (@(Get-LensGameProcesses).Count -gt 0) {
    throw 'Project Zomboid is running. Close it before installing.'
}

$target = Join-Path $Lens.UserMods 'RealVehicleInteriors'
if (Test-Path -LiteralPath $target) {
    New-Item -ItemType Directory -Force -Path $Lens.Archive | Out-Null
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $archived = Join-Path $Lens.Archive "RealVehicleInteriors-$stamp"
    Move-Item -LiteralPath $target -Destination $archived
    Write-Host "Previous copy archived to $archived"
}
Copy-Item -LiteralPath $Lens.Package -Destination $Lens.UserMods -Recurse
Write-Host "Installed $target"
Write-Host 'ZombieBuddy will ask once to approve the new RealVehicleInteriors.jar on the next launch.'

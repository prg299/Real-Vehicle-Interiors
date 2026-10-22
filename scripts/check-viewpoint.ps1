# Optional camera contract with authored API doubles; launch through run-heavy.mjs.
. (Join-Path $PSScriptRoot 'common.ps1')
$out = Join-Path $Lens.Out 'viewpoint-checks'
$common = Join-Path $out 'common'
$javac = Join-Path $Lens.Jdk 'javac.exe'
$java = Join-Path $Lens.Jdk 'java.exe'
New-Item -ItemType Directory -Path $common -Force | Out-Null
& $javac --release 25 -d $common (Join-Path $Lens.Root 'src/me/lens/rv/ViewpointCompat.java') (Join-Path $Lens.Root 'tools-src/ViewpointCompatCheck.java')
if ($LASTEXITCODE) { throw 'Camera contract compilation failed' }
& $java -Xmx64m -cp $common ViewpointCompatCheck missing
if ($LASTEXITCODE) { throw 'Absent Viewpoint check failed' }

foreach ($scenario in @('toggle', 'changed-api')) {
    $fixture = Join-Path $out $scenario
    $sourceDir = Join-Path $fixture 'viewpoint/core'
    New-Item -ItemType Directory -Path $sourceDir -Force | Out-Null
    # Minimal test doubles of the public state contract, not dependency source.
    $type = if ($scenario -eq 'toggle') { 'boolean' } else { 'String' }
    $source = "package viewpoint.core; public final class View { public static volatile $type enabled; public static volatile boolean thirdPerson; }"
    $file = Join-Path $sourceDir 'View.java'
    [IO.File]::WriteAllText($file, $source)
    & $javac --release 25 -d $fixture $file
    if ($LASTEXITCODE) { throw "Camera fixture compilation failed: $scenario" }
    & $java -Xmx64m -cp "$common;$fixture" ViewpointCompatCheck $scenario
    if ($LASTEXITCODE) { throw "Camera contract check failed: $scenario" }
}

# Optional camera contract with authored API doubles; launch through run-heavy.mjs.
. (Join-Path $PSScriptRoot 'common.ps1')
$out = Join-Path $Lens.Out 'viewpoint-checks'
$common = Join-Path $out 'common'
$javac = Join-Path $Lens.Jdk 'javac.exe'
$java = Join-Path $Lens.Jdk 'java.exe'
New-Item -ItemType Directory -Path $common -Force | Out-Null
$actor = Join-Path $out 'zombie/characters/IsoGameCharacter.java'
New-Item -ItemType Directory -Path (Split-Path $actor) -Force | Out-Null
[IO.File]::WriteAllText($actor, 'package zombie.characters; public class IsoGameCharacter {}')
& $javac --release 25 -d $common $actor (Join-Path $Lens.Root 'src/me/lens/rv/ViewpointCompat.java') (Join-Path $Lens.Root 'tools-src/ViewpointCompatCheck.java')
if ($LASTEXITCODE) { throw 'Camera contract compilation failed' }
& $java -Xmx64m -cp $common ViewpointCompatCheck missing
if ($LASTEXITCODE) { throw 'Absent Viewpoint check failed' }

foreach ($scenario in @('toggle', 'changed-api', 'missing-switch')) {
    $fixture = Join-Path $out $scenario
    $sourceDir = Join-Path $fixture 'viewpoint/core'
    New-Item -ItemType Directory -Path $sourceDir -Force | Out-Null
    # Minimal test doubles of the public state contract, not dependency source.
    $type = if ($scenario -eq 'changed-api') { 'String' } else { 'boolean' }
    $source = "package viewpoint.core; public final class View { public static volatile $type enabled; public static volatile boolean thirdPerson; }"
    $file = Join-Path $sourceDir 'View.java'
    [IO.File]::WriteAllText($file, $source)
    & $javac --release 25 -d $fixture $file
    if ($LASTEXITCODE) { throw "Camera fixture compilation failed: $scenario" }
    if ($scenario -eq 'toggle') {
        $switchFile = Join-Path $fixture 'viewpoint/FP.java'
        [IO.File]::WriteAllText($switchFile, @'
package viewpoint;
import zombie.characters.IsoGameCharacter;
public final class FP {
    public static int calls;
    public static IsoGameCharacter actor;
    private static void switchView(IsoGameCharacter player, boolean enabled) {
        calls++; actor = player; viewpoint.core.View.enabled = enabled;
    }
}
'@)
        & $javac --release 25 -cp "$common;$fixture" -d $fixture $switchFile
        if ($LASTEXITCODE) { throw 'Camera transition fixture compilation failed' }
    }
    & $java -Xmx64m -cp "$common;$fixture" ViewpointCompatCheck $scenario
    if ($LASTEXITCODE) { throw "Camera contract check failed: $scenario" }
}

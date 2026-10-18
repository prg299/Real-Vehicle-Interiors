# Developer helper: wait until the spawned test vehicle can be walked into (it is not "moving": a vehicle just
# spawned can still be settling, and MELens.canWalkIn refuses until it is at rest), then return. A walk-in
# queued before that does nothing and the review captures show the character outside.
#   .\dev\wait_still.ps1 [-Seconds 40]
param([int]$Seconds = 40)
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
for ($i = 0; $i -lt $Seconds; $i += 2) {
    $r = & $lua -Code 'local v = MELensTest and MELensTest.vehicle; if not v then return "novehicle" end; local ok, why = MELens.canWalkIn(getPlayer(), v); return ok and "ready" or tostring(why)'
    if (($r | ConvertFrom-Json).result -eq 'ready') { return }
    Start-Sleep -Seconds 2
}
Write-Host 'the vehicle did not come to rest'

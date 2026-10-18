# Preserve an exact staged payload independently of concurrent build/package writers.
param([string]$FromRun = 'final-mp-208', [string]$Name = 'candidate-2.0.8')
. (Join-Path $PSScriptRoot '..\scripts\common.ps1')
if ($FromRun -notmatch '^[a-z0-9.-]+$' -or $Name -notmatch '^[a-z0-9.-]+$') { throw 'Invalid owned snapshot name' }
$from = Join-Path $Lens.Out $FromRun
$record = Get-Content -LiteralPath (Join-Path $from 'session.json') -Raw | ConvertFrom-Json
if (-not $record.finishedUtc -or $record.serverExitCode -ne 0) { throw 'Source lifetime must be stopped successfully' }
$source = Join-Path $from 'server\home\Zomboid\mods\RealVehicleInteriors'
$target = [IO.Path]::GetFullPath((Join-Path $Lens.Out $Name))
if (-not $target.StartsWith($Lens.Out + '\', [StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $target)) { throw 'Snapshot must be new and remain in build/rv' }
$files = @(Get-ChildItem -LiteralPath $source -Recurse -Force)
if (@($files | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw 'Source contains a reparse point' }
$hashes = Get-Content -LiteralPath (Join-Path $from 'payload-hashes.json') -Raw | ConvertFrom-Json -AsHashtable
if (@($files | Where-Object { -not $_.PSIsContainer }).Count -ne $hashes.Count) { throw 'Source inventory differs from recorded payload' }
New-Item -ItemType Directory -Path $target | Out-Null
Copy-Item -LiteralPath $source -Destination $target -Recurse
foreach ($entry in $hashes.GetEnumerator()) {
    foreach ($root in @($source, (Join-Path $target 'RealVehicleInteriors'))) {
        $actual = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([IO.File]::ReadAllBytes((Join-Path $root $entry.Key)))).ToLowerInvariant()
        if ($actual -ne $entry.Value) { throw "Snapshot differs: $($entry.Key)" }
    }
}
@{ sourceRun = $FromRun; files = $hashes.Count; hashes = $hashes; frozenUtc = [DateTime]::UtcNow.ToString('o') } |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $target 'frozen-payload.json') -Encoding utf8
Write-Host "FROZEN_PAYLOAD_READY files=$($hashes.Count) path=$target\RealVehicleInteriors"

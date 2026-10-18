# Parse scripts without executing builds, installation or native harnesses.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$files = foreach ($directory in @('scripts', 'dev', 'tools-src')) {
    Get-ChildItem -LiteralPath (Join-Path $root $directory) -Filter *.ps1 -File -Recurse
}
$failures = @()
foreach ($file in $files) {
    $tokens = $null
    $parseErrors = $null
    $null = [Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors)
    foreach ($parseError in $parseErrors) { $failures += "$($file.Name): $($parseError.Message)" }
}
if ($failures.Count) { throw ($failures -join "`n") }
Write-Host "PowerShell syntax passed: $(@($files).Count) scripts (not executed)."

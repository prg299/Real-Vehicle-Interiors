# Developer helper: runs dev\lua\animal_test.lua in the add-on's test game, one mode per argument, and prints each
# result (see the modes at the top of that file).
#   .\dev\animals_test.ps1 give:hen drop state      (another test game: -Instance 5 -Modes give:hen,drop)
param([Parameter(Position = 0, ValueFromRemainingArguments = $true)][string[]]$Modes, [int]$Instance = 4)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$env:MELENS_LUA_PORT = "$(18470 + 2 * ($Instance - 1))"
$lua = Join-Path $root 'scripts\lua.ps1'
$code = Get-Content (Join-Path $PSScriptRoot 'lua\animal_test.lua') -Raw
foreach ($mode in $Modes) {
    $reply = (& $lua -Code $code.Replace('"MODE"', '"' + $mode + '"') 2>&1) -join ''
    try { $result = ($reply | ConvertFrom-Json).result } catch { $result = $reply }
    Write-Host "$mode -> $result"
}

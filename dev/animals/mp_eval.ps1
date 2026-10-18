# Developer helper: runs Lua on the local test server (dev\mp_server.ps1, with ZombieBuddy) through Real Vehicle
# Interiors' developer endpoint (the client sends it as the admin, the server answers) and prints what it returns.
#   .\dev\mp_eval.ps1 'return tostring(isServer())' [-Instance 4]
param([Parameter(Mandatory, Position = 0)][string]$Code, [int]$Instance = 4, [int]$Seconds = 25)
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$env:MELENS_LUA_PORT = "$(18470 + 2 * ($Instance - 1))"
$lua = Join-Path $root 'scripts\lua.ps1'
function C([string]$c) { $r = & $lua -Code $c; return ($r | ConvertFrom-Json).result }
$id = Get-Random -Minimum 30000 -Maximum 40000
[void](C "MELensDevResult = nil; sendClientCommand(getPlayer(), 'MELensDev', 'eval', { id = $id, code = [==[$Code]==] }); return 1")
for ($i = 0; $i -lt $Seconds * 2; $i++) {
    Start-Sleep -Milliseconds 500
    $r = C 'return MELensDevResult and (tostring(MELensDevResult.id) .. "|" .. tostring(MELensDevResult.text)) or "none"'
    if ($r -like "$id|*") { Write-Output $r.Substring("$id|".Length); return }
}
Write-Output 'TIMEOUT'

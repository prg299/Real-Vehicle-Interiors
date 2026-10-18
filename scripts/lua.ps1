# Runs Lua in the test game started by testgame.ps1 and prints the JSON result.
#   .\scripts\lua.ps1 -File dev\lua\state.lua
#   .\scripts\lua.ps1 -Code 'return getPlayer():getX()'
# -Port (or the environment variable MELENS_LUA_PORT) picks another game than the first test game: a second client
# started by testgame.ps1 -Instance 2 listens on 18472.
param([string]$Code, [string]$File, [int]$Depth = 3, [int]$Port = 0)

. (Join-Path $PSScriptRoot 'common.ps1')
if ($File) { $Code = Get-Content -LiteralPath $File -Raw }
if (-not $Code) { throw 'Pass -Code or -File' }
# sandbox=false: the driver scripts intentionally set globals the game reads.
if (-not $Port) { $Port = if ($env:MELENS_LUA_PORT) { [int]$env:MELENS_LUA_PORT } else { $Lens.LuaPort } }
$uri = "http://127.0.0.1:$Port/lua?depth=$Depth&sandbox=false"
$response = Invoke-WebRequest -Uri $uri -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($Code)) -UseBasicParsing -TimeoutSec 60
$response.Content

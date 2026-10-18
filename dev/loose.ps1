# Developer helper: run dev\lua\loose_test.lua in the test game with a mode and an argument.
#   .\dev\loose.ps1 give "Base.Hammer,Base.Pot"
#   .\dev\loose.ps1 start Hammer
#   .\dev\loose.ps1 at "0,-0.14,0.5"
#   .\dev\loose.ps1 hover
#   .\dev\loose.ps1 commit
#   .\dev\loose.ps1 list
# (modes: see the top of dev\lua\loose_test.lua)
param([Parameter(Mandatory)][string]$Mode, [string]$Arg = '')
$root = Split-Path $PSScriptRoot -Parent
$code = (Get-Content -LiteralPath (Join-Path $root 'dev\lua\loose_test.lua') -Raw).Replace(
    'local mode, arg = "MODE", "ARG"', ('local mode, arg = "{0}", "{1}"' -f $Mode, $Arg.Replace('"', '\"')))
& (Join-Path $root 'scripts\lua.ps1') -Code $code

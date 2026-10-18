# Developer helper: put changed Lua files of the mod into the running test game without restarting it.
# The files are copied from mod\RealVehicleInteriors\common\media\lua into the test profile's copy and loaded
# again with the game's own reloadLuaFile. Event handlers are registered again by a reload, so this suits files
# that guard them (MELens_LooseUI.lua and MELens_LooseView.lua do); files that wrap the game's functions
# (MELens_Inside.lua, MELens_Cabin.lua) need a restart (dev\restart.ps1).
#   .\dev\reload.ps1 client\MELens_LooseUI.lua shared\MELens_Loose.lua
param([Parameter(Mandatory, ValueFromRemainingArguments)][string[]]$File)
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
foreach ($f in $File) {
    $source = Join-Path $root ('mod\RealVehicleInteriors\common\media\lua\' + $f)
    $target = Join-Path $root ('build\rv\testhome\Zomboid\mods\RealVehicleInteriors\common\media\lua\' + $f)
    if (-not (Test-Path -LiteralPath $source)) { throw "No such file: $source" }
    Copy-Item -LiteralPath $source -Destination $target -Force
    $path = $target.Replace('\', '/')
    $result = & $lua -Code ("reloadLuaFile('" + $path + "') return 'reloaded'")
    Write-Host "$f : $result"
}

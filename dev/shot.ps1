# Developer helper: a clean picture of the running test game: camera zoom set (lower is closer), the
# interface hidden, the window captured, the interface back, and optionally a crop enlarged.
#   .\dev\shot.ps1 -Out build\rv\dbg\x.png [-Zoom 0.5] [-Crop 350,150,700,450] [-Scale 1.5]
# -Crop is x,y,width,height of the window capture. A relative -Out is taken from the project folder.
param([Parameter(Mandatory)][string]$Out, [double]$Zoom = 0, [int[]]$Crop, [double]$Scale = 1.5)
$root = Split-Path $PSScriptRoot -Parent
$lua = Join-Path $root 'scripts\lua.ps1'
if (-not [IO.Path]::IsPathRooted($Out)) { $Out = Join-Path $root $Out }
New-Item -ItemType Directory -Force -Path (Split-Path $Out) | Out-Null

function Lua([string]$code) { $r = & $lua -Code $code; return ($r | ConvertFrom-Json).result }

[void](Lua 'local c = UIManager.getDebugConsole and UIManager.getDebugConsole(); if c then c:setVisible(false) end; return 1')
if ($Zoom -gt 0) {
    for ($i = 0; $i -lt 8; $i++) {
        $now = [double](Lua 'return getCore():getZoom(0)')
        if ([math]::Abs($now - $Zoom) -lt 0.01) { break }
        $step = if ($now -gt $Zoom) { -1 } else { 1 }
        [void](Lua "getCore():doZoomScroll(0, $step); return 1")
        Start-Sleep -Milliseconds 1300
    }
}
[void](Lua 'ISUIHandler.setVisibleAllUI(false); return 1')
Start-Sleep -Seconds 2
& (Join-Path $PSScriptRoot 'capture.ps1') -Out $Out | Out-Null
[void](Lua 'ISUIHandler.setVisibleAllUI(true); return 1')
if ($Crop) {
    $cropped = [IO.Path]::ChangeExtension($Out, $null).TrimEnd('.') + '_crop.png'
    python -c "
from PIL import Image
import sys
x, y, w, h = $($Crop -join ',')
im = Image.open(r'$Out').crop((x, y, x + w, y + h))
im = im.resize((int(w * $Scale), int(h * $Scale)), Image.LANCZOS)
im.save(r'$cropped')
"
    Write-Host "crop: $cropped"
}
Write-Host "shot: $Out"

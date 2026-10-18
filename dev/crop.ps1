# Developer helper: crop (and enlarge) part of a screenshot for close inspection.
#   powershell -File dev/crop.ps1 -In shot.png -Out crop.png -X 440 -Y 280 -W 440 -H 330 -Scale 2
param(
    [Parameter(Mandatory)][string]$In,
    [Parameter(Mandatory)][string]$Out,
    [int]$X = 0, [int]$Y = 0, [int]$W = 400, [int]$H = 300,
    [double]$Scale = 2.0
)
Add-Type -AssemblyName System.Drawing
$source = [System.Drawing.Bitmap]::FromFile((Resolve-Path -LiteralPath $In))
try {
    $target = New-Object System.Drawing.Bitmap ([int]($W * $Scale)), ([int]($H * $Scale))
    $g = [System.Drawing.Graphics]::FromImage($target)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
    $g.DrawImage($source, (New-Object System.Drawing.Rectangle 0, 0, $target.Width, $target.Height),
        (New-Object System.Drawing.Rectangle $X, $Y, $W, $H), [System.Drawing.GraphicsUnit]::Pixel)
    $g.Dispose()
    $target.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    $target.Dispose()
} finally {
    $source.Dispose()
}

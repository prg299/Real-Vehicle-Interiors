# Developer helper: record the test game's window as a numbered frame sequence (JPEG, client area only), for a
# video: dev\make_video.py turns the frames into an mp4 with Blender (no ffmpeg needed). Uses PrintWindow like
# capture.ps1 (never takes the focus). The frame rate is what the machine manages; the real rate is printed and
# the frames carry their time stamps in a list for the video's frame rate.
#   .\dev\record.ps1 -OutDir build\rv\dbg\video\frames -Seconds 25
param([Parameter(Mandatory)][string]$OutDir, [double]$Seconds = 20, [int]$Quality = 90)

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MELensRec {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
}
'@
$pidFile = Join-Path $PSScriptRoot '..\build\rv\testhome\game.pid'
$process = Get-Process -Id ([int](Get-Content -LiteralPath $pidFile))
$handle = $process.MainWindowHandle
if ($handle -eq [IntPtr]::Zero) { throw 'Test game has no window yet' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
# (.NET saves relative to the process's folder, not PowerShell's)
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path
$rect = New-Object MELensRec+RECT
[void][MELensRec]::GetWindowRect($handle, [ref]$rect)
$w = $rect.Right - $rect.Left
$h = $rect.Bottom - $rect.Top
$codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
$params = New-Object System.Drawing.Imaging.EncoderParameters 1
$params.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality), ([long]$Quality)
$bitmap = New-Object System.Drawing.Bitmap $w, $h
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$clock = [Diagnostics.Stopwatch]::StartNew()
$times = New-Object System.Collections.Generic.List[double]
$n = 0
while ($clock.Elapsed.TotalSeconds -lt $Seconds) {
    $hdc = $graphics.GetHdc()
    [void][MELensRec]::PrintWindow($handle, $hdc, 2)
    $graphics.ReleaseHdc($hdc)
    $times.Add($clock.Elapsed.TotalSeconds)
    $bitmap.Save((Join-Path $OutDir ('f{0:D5}.jpg' -f $n)), $codec, $params)
    $n++
}
$graphics.Dispose(); $bitmap.Dispose()
Set-Content -LiteralPath (Join-Path $OutDir 'times.txt') -Value ($times | ForEach-Object { $_.ToString('0.000', [Globalization.CultureInfo]::InvariantCulture) })
Write-Host ('{0} frames in {1:N1} s = {2:N1} fps ({3} x {4})' -f $n, $clock.Elapsed.TotalSeconds, ($n / $clock.Elapsed.TotalSeconds), $w, $h)

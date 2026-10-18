# Developer helper: capture the test game's window to a PNG.
# Uses PrintWindow with PW_RENDERFULLCONTENT, which reads the window's own composed
# content, so it works while other windows cover the game and never takes the focus.
# -Instance 2 captures the second test game (scripts\testgame.ps1 -Instance 2).
param([Parameter(Mandatory)][string]$Out, [int]$Instance = 1)

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MELensWin {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int cmd);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
}
'@

$gameHome = if ($Instance -gt 1) { "testhome$Instance" } else { 'testhome' }
$pidFile = Join-Path $PSScriptRoot "..\build\rv\$gameHome\game.pid"
$id = [int](Get-Content -LiteralPath $pidFile)
$process = Get-Process -Id $id
$handle = $process.MainWindowHandle
if ($handle -eq [IntPtr]::Zero) { throw 'Test game has no window yet' }
if ([MELensWin]::IsIconic($handle)) {
    [void][MELensWin]::ShowWindow($handle, 4)   # SW_SHOWNOACTIVATE: restore without focus
    Start-Sleep -Milliseconds 500
}
$rect = New-Object MELensWin+RECT
[void][MELensWin]::GetWindowRect($handle, [ref]$rect)
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$hdc = $graphics.GetHdc()
$ok = [MELensWin]::PrintWindow($handle, $hdc, 2)   # PW_RENDERFULLCONTENT
$graphics.ReleaseHdc($hdc)
$graphics.Dispose()
if (-not $ok) { $bitmap.Dispose(); throw 'PrintWindow failed' }
$bitmap.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bitmap.Dispose()
Write-Host "Saved $Out ($width x $height)"

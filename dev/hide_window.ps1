# Developer helper: move the test game's window off the screen (it keeps running and rendering, and
# dev\capture.ps1 / dev\record.ps1 still read it), so an idle test window is not lying around on the desktop
# while a script works. -Show brings it back to the top left of the screen.
param([switch]$Show)
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MELensPos {
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr after, int x, int y, int cx, int cy, uint flags);
}
'@
$pidFile = Join-Path $PSScriptRoot '..\build\rv\testhome\game.pid'
$process = Get-Process -Id ([int](Get-Content -LiteralPath $pidFile))
$handle = $process.MainWindowHandle
if ($handle -eq [IntPtr]::Zero) { throw 'Test game has no window yet' }
$x = if ($Show) { 60 } else { -20000 }
$y = if ($Show) { 60 } else { 0 }
# SWP_NOSIZE (1) | SWP_NOZORDER (4) | SWP_NOACTIVATE (0x10)
[void][MELensPos]::SetWindowPos($handle, [IntPtr]::Zero, $x, $y, 0, 0, 0x15)
Write-Host $(if ($Show) { 'test window shown' } else { 'test window moved off the screen' })

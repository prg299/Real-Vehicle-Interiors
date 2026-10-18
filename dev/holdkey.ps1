# Developer helper: focus the test game window and hold a key (virtual-key code) for a while.
#   dev\holdkey.ps1 -Key 0x57 -Milliseconds 1200     (W)
param([Parameter(Mandatory)][int]$Key, [int]$Milliseconds = 1000)

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MELensKeys {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint mapType);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
'@

$id = [int](Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\build\rv\testhome\game.pid'))
$handle = (Get-Process -Id $id).MainWindowHandle
[void][MELensKeys]::SetForegroundWindow($handle)
Start-Sleep -Milliseconds 300
$scan = [byte][MELensKeys]::MapVirtualKey([uint32]$Key, 0)
[MELensKeys]::keybd_event([byte]$Key, $scan, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds $Milliseconds
[MELensKeys]::keybd_event([byte]$Key, $scan, 2, [UIntPtr]::Zero)

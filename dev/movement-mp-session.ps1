# One bounded, parent-owned two-client lifetime. Launch through run-mod-test.
param([Parameter(Mandatory)][string]$Run,[switch]$KeepOnFailure)
$ErrorActionPreference='Stop'
if($Run -notmatch '^[a-z0-9-]+$'){throw 'Run must be one owned folder name'}
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runPath=Join-Path $taskRoot "build/rv/$Run"
if(Test-Path -LiteralPath $runPath){throw 'Preserve existing evidence; choose a new run'}
$env:RVI_TEST_CORE_ONLY='0'
$env:RVI_PYTHON='C:/Users/erika/AppData/Local/Python/pythoncore-3.14-64/python.exe'
$child=$null;$queued=$false;$stopping=$false;$driver=$null;$failureReported=$false
$timer=[Diagnostics.Stopwatch]::StartNew()
function Request($value){
    $pending=Join-Path $runPath 'request.movement-pending.json'
    [IO.File]::WriteAllText($pending,($value|ConvertTo-Json -Depth 8))
    [IO.File]::Move($pending,(Join-Path $runPath 'request.json'),$true)
}
try{
    $psi=[Diagnostics.ProcessStartInfo]::new((Get-Command pwsh).Source)
    $psi.WorkingDirectory=$taskRoot;$psi.UseShellExecute=$false;$psi.CreateNoWindow=$true
    foreach($arg in @('-NoProfile','-File','dev/final-mp-session.ps1','-Run',$Run,'-ServerJava',
        '-ClientHeapMiB','2048','-ServerHeapMiB','2048','-ReviewMinutes','20')){$psi.ArgumentList.Add($arg)}
    $child=[Diagnostics.Process]::Start($psi)
    $startTicks=$child.StartTime.ToUniversalTime().Ticks
    while(-not $child.WaitForExit(400)){
        $sessionFile=Join-Path $runPath 'session.json'
        if(-not $queued -and (Test-Path -LiteralPath $sessionFile)){
            $s=Get-Content -LiteralPath $sessionFile -Raw|ConvertFrom-Json
            if($s.status -eq 'review-ready'){
                Request @{action='driver';id='movement-camper';script='dev/final-mp-native-movement.py';
                    args=@('--session',$runPath);timeoutSeconds=900}
                $queued=$true
            }
        }
        $receipt=Join-Path $runPath 'driver-response.json'
        if($queued -and (Test-Path -LiteralPath $receipt)){
            $driver=Get-Content -LiteralPath $receipt -Raw|ConvertFrom-Json
            if($driver.finishedUtc -and -not $stopping){
                if($driver.exitCode -eq 0 -or -not $KeepOnFailure){Request @{action='stop'};$stopping=$true}
                elseif(-not $failureReported){Write-Output 'MOVEMENT_MP_FAILED_REVIEW_READY';$failureReported=$true}
            }
        }
        if($timer.Elapsed.TotalSeconds -gt 1140){throw 'Native movement MP lifetime exceeded its deadline'}
    }
    if($child.ExitCode -ne 0 -or -not $driver.finishedUtc -or $driver.exitCode -ne 0){throw 'Native MP parent or driver failed'}
    Write-Output 'MOVEMENT_MP_LIFETIME_PASSED'
}finally{
    if($child -and -not $child.HasExited){
        if(Test-Path -LiteralPath $runPath){Request @{action='stop'}}
        if(-not $child.WaitForExit(60000) -and $child.StartTime.ToUniversalTime().Ticks -eq $startTicks){
            $child.Kill($true);[void]$child.WaitForExit(5000)
        }
    }
    if($child){$child.Dispose()}
}

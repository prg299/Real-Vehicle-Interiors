# Matcher regression against a separately downloaded ZombieBuddy 3 framework.
param([Parameter(Mandatory)][string]$BuddyJar, [string]$CandidateJar, [switch]$ExpectMisses)
. (Join-Path $PSScriptRoot 'common.ps1')
$ErrorActionPreference='Stop'
if (-not $CandidateJar) { $CandidateJar = Join-Path $Lens.Package '42.21/media/java/RealVehicleInteriors.jar' }
$out = Join-Path $Lens.Out 'framework-checks'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$cp = "$BuddyJar;$($Lens.GameRoot)/*"
& (Join-Path $Lens.Jdk 'javac.exe') --release 25 -d $out -cp $cp (Join-Path $Lens.Root 'tools-src/FrameworkHookCheck.java')
if ($LASTEXITCODE) { throw 'Framework contract runner compilation failed' }
$checkArgs = @($CandidateJar)
if ($ExpectMisses) { $checkArgs += '--expect-misses' }
& (Join-Path $Lens.Jdk 'java.exe') -Xmx256m "-Duser.home=$out/home" -cp "$out;$cp" FrameworkHookCheck @checkArgs
if ($LASTEXITCODE) { throw 'Framework hook matching failed' }

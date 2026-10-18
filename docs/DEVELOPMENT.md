# Development setup

## Requirements

The build is supported on Windows with PowerShell 7, Python 3.10+, JDK 25 (tested with 25.0.4.1), Project Zomboid 42.21 and ZombieBuddy installed in the game directory. Subscribe to the four dependencies listed in README.md. The isolated compatibility profile additionally uses KI5 Trailers (`3330403100`) to check that unsupported trailers stay unchanged. Blender 3.6 is needed only to regenerate meshes, not for ordinary builds.

Set `PZ_GAME_DIR`, `PZ_WORKSHOP_DIR` and `RVI_JAVA_HOME` (or `JAVA_HOME`) before building. Alternatively create ignored `.local/settings.ps1` and set `$Lens.GameRoot`, `$Lens.Workshop` and `$Lens.Jdk` there; `Jdk` must be the JDK's `bin` directory. No machine-specific settings are committed.

## Build and verify

```powershell
pwsh -NoProfile -File scripts/build.ps1
pwsh -NoProfile -File scripts/check-release.ps1
python scripts/check-repository.py
pwsh -NoProfile -File scripts/check-powershell.ps1
```

The Java JAR uses a fixed entry timestamp. The build compiles Java, checks every production Lua file with Kahlua, validates JSON and reconstructs the six cutaway shaders using the installed game's original shader bytes. A changed upstream hash stops the build for review. Output: `build/rv/package/RealVehicleInteriors`; source: `mod/RealVehicleInteriors` and `src/me/lens/rv`.

On the maintainer's machine wrap **each** command above in the resource guard, for example:

```powershell
node C:/Users/erika/.codex/tools/run-heavy.mjs -- pwsh -NoProfile -File scripts/build.ps1
```

The guard also covers native sessions, captures and Blender. Exit 75 means defer the check and record it as unverified. Other contributors and hosted CI use their own resource policy.

## Native testing

`scripts/testgame.ps1` prepares a disposable profile under `build/rv/testhome`; `-Instance 2` uses a second profile and Lua port. It copies installed dependencies into that profile and loads `dev/RealVehicleInteriors_Dev`. Its loopback Lua endpoint is a developer facility, never part of the shipped mod. `scripts/lua.ps1` sends development commands to that endpoint.

`dev/final-lifecycle-session.ps1` and `dev/final-mp-session.ps1` own bounded native sessions, input drivers, outputs and process cleanup. Read their parameters and use a unique output path under `build/`. Keep clients and the server inside the same guarded process tree. Older `dev/restart.ps1` and `dev/mp_server.ps1` helpers return while games run; they are building blocks for a bounded session, not unattended commands to leave running. Start-Process background helpers should be hidden; never seize an active desktop.

Production-Lua regressions use engine doubles. They do not establish native input, visual quality, multiplayer acceptance, save safety or performance. New reports must say exactly which paths were exercised.

## Install and publish

With the game/server stopped, `scripts/install.ps1` copies the built package to `%USERPROFILE%\Zomboid\mods\RealVehicleInteriors` and archives any previous local copy under `%USERPROFILE%\Zomboid\RealVehicleInteriors-archive`. Installing is optional and separate from building. Never edit a Workshop download.

`python scripts/workshop_upload.py` prepares a project-local Workshop stage without logging in. Set `RVI_STEAMCMD` to your `steamcmd.exe` path if it is outside the default local installation. Only `--upload` logs in interactively and updates the recorded Workshop item; upload requires the owner's authorization and account. Credentials are entered through SteamCMD and are not stored in the repository. Forks must use their own Workshop identity and preview. Public CI never uploads or bundles game dependencies.

The original published GIF/video masters and private verification receipts remain in the maintainer's local historical project. This repository includes the existing small preview and public identity, not the local media-production pipeline.

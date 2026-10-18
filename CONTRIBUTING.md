# Contributing

Use an issue to describe a bug or proposed change, then open a focused pull request against `main`. Use `codex/animals-support` as the base for Animals WIP changes. Keep that feature out of release packages until its acceptance gaps are resolved.

1. Read [development setup](docs/DEVELOPMENT.md), [architecture](docs/ARCHITECTURE.md) and [compatibility](docs/COMPATIBILITY.md).
2. Keep game/Workshop installs read-only. Build in this checkout and use the disposable test profile. Never commit saves, logs, credentials, downloaded mods or game binaries.
3. Extend shared profiles and contracts before adding a special case. New vehicles should use `tools-src/vehicles/specs/` and the existing generators.
4. Preserve `RealVehicleInteriors`, `MELens*`, network commands, item/part IDs, modData keys, asset bindings and the `me.lens.rv` Java namespace. Changes to these can affect existing saves and add-ons; propose an explicit migration when required.
5. Run `python scripts/check-repository.py`, `scripts/check-powershell.ps1`, the build and `scripts/check-release.ps1`. CI covers repository checks only: the game-dependent checks require your own installation.
6. For interactive changes, exercise real mouse/keyboard input through the production UI. Report engine-double assertions, native input, visual evidence, multiplayer replication, save/reload, performance and human acceptance separately. Include relevant logs with private information removed.

On the maintainer's shared machine all builds, tests and captures use the resource guard described in `AGENTS.md`. Exit 75 means deferred; do not bypass the guard or increase its limits.

By submitting a contribution you agree to license your authored contribution under this repository's MIT license. Retain third-party notices and credit the origin of external material. Generated art must keep its prompt/master and be reviewed in its actual game context.

# Animals support — WIP

Branch: `codex/animals-support`. The feature is unreleased and remains excluded from `main` and the Workshop payload. This branch preserves Claude's integrated Java/Lua snapshot and developer drivers; it is not a declaration that animal support is complete.

## Implementation

`MELens_Animals.lua` keeps animals in the vehicle's native animal list and records their cabin placement in `MELensAnimals` modData. It handles food/water, Companion Dogs entry/exit and the server's periodic updates. `TimedActions/MELens_AnimalActions.lua` implements carry/drop/pickup, and `MELens_AnimalsUI.lua` wraps the main mod's drop and loose-item menus. These files live under `mod/RealVehicleInteriors/common/media/lua/`.

Java `Animals.java` draws animated animals after the occupied vehicle and uses the cabin depth from `Cutaway`. `Hooks.java`, `Main.java` and `RV.java` supply the integration hooks and Lua bridge. Seven of the eight original snapshot files are unchanged; `Animals.java` has one compile repair: its animation-state local is named `animationState` to avoid colliding with the renderer's integer state index. Original hashes and the repair are recorded in [IMPORT.json](animals/IMPORT.json). Translation keys were adapted to the integrated names in all seven existing languages. The original separate add-on implementation remains in the maintainer's historical local project; it is not a second shipped implementation here.

Companion Dogs is optional, Workshop [3740052292](https://steamcommunity.com/sharedfiles/filedetails/?id=3740052292), mod ID `CompanionDogs`. The branch references its runtime interfaces without copying its code or assets. For compatibility testing, set `$env:MELENS_TEST_EXTRA = '3740052292:CompanionDogs'` before preparing a disposable test profile.

## Developer entry points

The normal `scripts/build.ps1` builds this branch's integrated source. It does not require an additional Animals mod. Existing test helpers are under `dev/animals/`: `animals_test.ps1`, `headings.ps1`, `restart.ps1`, `mp_server.ps1` and `mp_eval.ps1`. Paths now resolve inside this repository; helpers use instance 4 by default. They are building blocks that must run in a bounded guarded session which owns and closes its games/server. Never leave their returned processes unattended.

The drivers can create animals, alter needs, place food/water and remove other test vehicles. Use only disposable worlds. The older add-on's test driver evidence does not prove every integrated-branch workflow.

## Existing evidence and remaining work

Claude's [historical design and status](animals/DESIGN-HISTORY.md) records isolated single-player carry/drop/pickup, food/water, four-heading drawing, save/reload and Companion Dogs checks, plus a one-client dedicated-server run. Those reports were imported; they were not rerun during this repository setup.

The historical notes leave two-player testing, multiplayer interior rendering (a black-world blocker), and a server without ZombieBuddy unverified. Complete these and fresh native input/save-reload checks on the integrated branch before merging or releasing. Animal interaction scope still excludes breeding, eggs, milking/shearing, unrestricted interior AI and large uncarryable animals.

This extraction checks compilation, Lua/JSON syntax and the unchanged base regression suite separately. Those checks do not prove Animals gameplay, visuals, multiplayer behavior or human acceptance.

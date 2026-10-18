# Animals support — WIP

Branch: `animals-support`. Unreleased and kept separate from `main` and the Workshop mod.

Includes animals inside vehicles, carry/drop/pickup, food and water, and Companion Dogs entry/exit. The integrated Java/Lua snapshot, seven translation sets and developer drivers are preserved. The original hashes and the animation-state variable compile fix are recorded in [IMPORT.json](animals/IMPORT.json); [design and earlier test notes](animals/DESIGN-HISTORY.md) are retained for reference.

Optional dependency: [Companion Dogs](https://steamcommunity.com/sharedfiles/filedetails/?id=3740052292), mod ID `CompanionDogs`.

Builds with `scripts/build.ps1`. Existing isolated test helpers are under `dev/animals/`. The base regression suite passes 1,112 assertions; compilation checks 34 Lua files. These do not establish animal gameplay or multiplayer acceptance.

Still unverified: two-player testing, multiplayer interior rendering (an earlier black-world blocker), a server without ZombieBuddy, and fresh native interaction/save-reload on this integrated branch. Breeding, eggs, milking/shearing, unrestricted interior AI and large uncarryable animals are outside the current scope.

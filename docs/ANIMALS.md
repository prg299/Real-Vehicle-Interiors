# Animals support — WIP

Branch: `animals-support`. Unreleased and kept separate from `main` and the Workshop mod.

Includes animals inside vehicles, carry/drop/pickup, food and water, and Companion Dogs entry/exit. The original integrated Java/Lua work and seven translation sets are preserved. Current local checkout: `D:/Stuff/Projects/Real-Vehicle-Interiors-Animals`; package: `build/rv/package/RealVehicleInteriors`.

Optional dependency: [Companion Dogs](https://steamcommunity.com/sharedfiles/filedetails/?id=3740052292), mod ID `CompanionDogs`.

Animals now initialize their own animation set before the model is constructed and supply the native movement/feeding variables. Satisfied animals wait 20–40 game minutes between decisions, usually stay put, and take shorter steps. Existing saved positions acquire a quiet timer without relocation. Local steps check the shared room/furniture geometry along their full length; inaccessible bowls are skipped.

Verified locally on Build 42.21, 2026-10-24:

- Build: 63 Lua files, translations, shipping Java and shader recipes pass. Regression checks: 7,550 Lua assertions, 31 cutaway and 22 vision assertions; these use engine doubles/pure geometry.
- Native input: inventory Drop and world-menu Pick up work inside a Flying Cloud. Hen and Companion Dogs dog idle, walk, eat, drink and rest clips advance with nonzero blend weight; captured frames reviewed. Evidence: `build/rv/animals-20261024-input-d/animals-input/`.
- Native needs: water, suitable food, unsuitable-food rejection, no-water eating and 19 quiet minutes pass. A fresh process preserves animal IDs, names, positions, timers, floor stock, furniture, loot and utilities. Evidence: `build/rv/animals-20261024-needs-save-a/animals-lifecycle/` and `animals-20261024-cold-reload-a/animals-lifecycle/`.
- Dedicated server without Java, two real clients: vanilla world pickup → interior Drop → native world-menu pickup preserves exactly one hen. Both peers render advancing animal clips and receive the same records/water stock. Companion Dogs 0.7.4 follows in/out, stays when commanded, consumes bowl food/water, preserves its identity and leaves no stale occupancy record. Evidence: `build/rv/animals-20261024-mp-b/drivers/animals-world-pickup/output/`. Dog commands and needs were fixtures; owner exit/re-entry used real Interact input.

The first MP run stopped at a missing test-profile acknowledgement. An earlier synthetic carried-animal fixture produced an invalid network setup and duplicates; the replacement uses vanilla world pickup. Retained logs also contain pre-test game/dependency diagnostics, including a vanilla glovebox exception. These runs do not establish a globally error-free mod set.

Still unverified: dedicated-server restart persistence, a server with the Java component, inventory mouse Drop in MP, the dog command-menu workflow, all other animal species and a native furnished-room traversal audit. Breeding, eggs, milking/shearing, unrestricted interior AI and large uncarryable animals remain outside the current feature scope. No Animals publication is authorized.

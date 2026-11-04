# 2.0.22 release qualification

Qualified on 4 November 2026 for Project Zomboid 42.21, stable ZombieBuddy 2.3.4 and 3.0.0-beta3. The candidate repairs sixteen skipped beta hooks and generator pickup from the interior Floor. Existing geometry, profiles, furniture, utility schemas and saved IDs retain their released contracts. No new dependency or signed component is introduced.

Published to Workshop `3811728541` on 4 November through the owner-checked SteamUGC API after [PR #21](https://github.com/prg299/Real-Vehicle-Interiors/pull/21) merged as `037ba59aa5ddaaf1dc1a2c90823d3bd1cfcc820d`. Steam returned EResult 1; official manifest `9197371615592702872` matches all 219 frozen files. Fresh before/after owner queries preserve title, description, cover, all ten gallery entries/order, visibility and the sole ZombieBuddy requirement. Publication receipts are `build/rv/release-2.0.22.source.json`, `.desktop.json` and `.published.json`. Distribution verification does not establish which version an already-running player/server has loaded; restart after updating and approve the changed Java component.

## Native input

- Beta: cold-start entry, idle, walking, running and directional controls use the normal player animation set; sampled opacity remains 1.
- Stable: native walking/running speeds match outdoor controls within 0.5%; stopping distance matches within 0.1%. Aiming, strafe, collision and twelve turning comparisons pass. Furnished camper Rest, sleep cancellation/acceptance and getting up pass.
- Stable and beta: real context-menu generator Grab and Drop retain the same ID. A carried heavy item is preserved when a second pickup is rejected. Ordinary hand items return to inventory. The native `Base.Generator` definition uses a world sprite and has no authored hand model; this patch adds none.
- Stable and beta F700 bank truck: real Dashboard input installs portable fuel/propane and switches the generator/stove. Native food cools and ages more slowly in the powered fridge; power-off clears refrigeration.
- Dedicated server with Java and two actual clients: fifteen movement/rest/exit cases pass, with furniture, storage and player-item IDs preserved. Generator pickup, both-hand equipment and drop back into the same Floor agree on authority, owner and observer.

The input drivers send native keyboard/mouse events through production dispatch and timed actions. Vehicle/fitting/item placement, character start positions and one bounded food-aging clock advance are explicit fixtures. No player save, playset or installed mod was changed.

## Automated checks and artifacts

130 normal/debug Lua compilations, 190,693 Lua assertions, 285 cutaway checks, 22 vision checks, 46 optional-camera checks and 31 actual beta hook matches pass. Argument-bearing hooks keep strict overload matching; each relaxed target has exactly one zero-argument method. Repository checks and 76 PowerShell parses pass.

The frozen package has 219 files. Java SHA-256: `7b081595ea1064f1cd9fd51b28f3fba0deb537c6bf050b180a7290a7aa570b26`. Six SP/server/client deployments match every payload hash. Seven runtime files differ from released 2.0.21, including version markers and one English feedback string. Claude's original Animals WIP remains in source ancestry.

Local evidence in `D:/Stuff/Projects/Real-Vehicle-Interiors-Animals/build/rv`:

- `release-2022-beta-a`: movement, generator and F700 appliance input.
- `release-2022-stable-a`: passed movement/bed/turning subdrivers; its later aggregate fixture failed before pickup because a new field had not streamed. The raw failure is retained.
- `release-2022-stable-b`: corrected focused generator/F700 input, clean native lifetime.
- `release-2022-mp-a`: server and two clients, movement plus generator authority/observer receipts, clean exits.
- `release-2.0.22.qualification.json`: payload, deployment and diagnostic checks.
- `release-2.0.22-approved/RealVehicleInteriors`: frozen upload candidate.

Original SP movement, generator and MP actor/observer frames were opened and reviewed. The beta fixture setup failures, external installed game/PZ Optimization startup diagnostics and first stable aggregate fixture failure remain recorded. No RVI source exceptions were found in the completed native logs. All owned native processes closed; the server and both clients exited zero.

## Limits

Steam transport, controllers, local split-screen, cold restart while holding a generator and every optional camera/furniture combination are outside this pass. The unidentified invisible-interior and dependency exterior-state reports remain unresolved; successful representative tests are not a claim that every Workshop complaint is fixed. The exact reported F700 appliance configuration was not available. See the [report inventory](workshop-bugs-2026-11-03.md).

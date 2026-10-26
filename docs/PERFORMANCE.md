# Performance investigation — 2.0.19

## Reproduction and changes

The 26 October 2026 [stocked-vehicle report](https://steamcommunity.com/sharedfiles/filedetails/?id=3811728541#comment_573804739774640929) describes severe lag even at the 16-item display limit. Released shelf code sorted and packed every stored item every 250 ms, before checking whether anything changed. The display budget applied only after all packing finished, including when the remaining budget was zero.

Shelf layouts now reuse unchanged native inventories. Transfers, replacement items, installed furniture, geometry, budget increases, model readiness and displayed appearance are checked separately. Each rack stops at the global display budget; round-robin sharing still gives later racks a place. Identical item dimensions reuse failed-placement results. Large inventory sorting uses bounded stack depth. No engine-owned dirty flag is cleared and no inventory is copied into a second storage authority.

The animal render cache previously used weak keys whose values strongly referenced those same animals. It now owns only published animals and retires removed models after their queued render states drain. Outdoor player updates skip interior phobia contexts/receipts; interior scopes and native panic rates remain. Loose-item travel checks test the sample deadline before querying vehicle speed.

Vehicle, passenger, furniture, item, loot, utility and network identifiers are unchanged. No save migration is needed for these changes.

## Native measurements

Build 42.21, isolated single-player desktop, only ZombieBuddy/RVI/private test helper. Stress fixture: a native StepVan with 480 real items across 10 rack containers. Fittings are deliberately injected for stress; this is not a proposed vehicle layout. Resolution 1280×720, low-memory texture settings, warmed stationary camera. The machine effectively presented at 60 Hz despite requesting uncapped rendering, so 60 FPS is a ceiling rather than a maximum throughput claim.

| Case | Mean frame | FPS | p95 frame |
| --- | ---: | ---: | ---: |
| Released 2.0.18, dense racks | 289.90 ms | 3.45 | 312.03 ms |
| Fixed, same stress fixture | 16.67 ms | 60.00 | 17.85 ms |
| Released shelf control, same live world/items/Java | 292.01 ms | 3.42 | 305.78 ms |
| Fixed shelf repeat, same live world/items/Java | 16.67 ms | 60.00 | 17.61 ms |
| Fixed, 16-item limit | 16.67 ms | 60.00 | 17.65 ms |

Released shelf calls took 280–284 ms each; warm fixed calls took 0–1 ms at the timer's millisecond resolution. Both implementations still displayed 64 items in the 64-item case. Alternating only the shelf implementation in the same live scene reproduced and removed the slowdown. Native phobia cases and four animal-model create/render/retire cycles passed; each removed animal left zero cached/retiring models. Both owned games exited normally.

Artifacts: `build/rv/performance-baseline-20261026-a` and `performance-fixed-20261026-a`, with frame receipts, original screenshots, JFR recordings and native process identities/exits. These are single-player component results, not exhaustive fleet, large multiplayer-server, long-session leak or all-hardware qualification. Installed PZ Optimization/stock startup diagnostics remain in the logs; no post-frame-zero error headers occurred in these runs. User applications and saves were left untouched.

The final 2.0.19 package also passes `performance-2019-final-20261026-c`: 60 FPS with p95 17.98 ms; reverting just the shelf code returns 3.44 FPS. All 219 deployed files are hashed. Native transfers remove and restore the correct displayed item while preserving its ID/count; panic cases, four advancing hen animation/retirement cycles and Interact exit pass. An intentionally cold rebuild of all ten racks still costs 75–81 ms; the cache removes repeated steady-state work, not all initial loading cost. The final JAR is `d08aee2c50accbbf82f6f6b96649612fa794e51e7337945ca4df6f9ac075d4b9`.

The 25-second JFR samples support the diagnosis: main-thread samples containing Kahlua fall from 2,346 to 122, and GC pause events from 28 to zero in these recordings. Sampling weights are not retained heap measurements. An earlier final-package startup exposed an access modifier error in the new frame hook; that failed run remains in `performance-2019-final-20261026-b`. The hook target is now public and the fresh C startup/gameplay run passes.

`performance-2019-dogs-20261026-a` adds only Companion Dogs: the dense fixture stays at 60 FPS (p95 17.80 ms). Two hen and two dog model cycles verify advancing native clips and zero cached/retiring models after removal. Inventory transfers, native panic and normal exit pass again with the same final JAR. Both final runs exit zero, with 6.24/6.33 GiB peak child-tree memory. Focused checks pass 7,684 Lua, 31 cutaway-state and 22 vision assertions; 128 normal/debug Lua compilations have zero errors. Fresh multiplayer and long-duration server performance are not qualified by these single-player runs.

Published on 26 October 2026 to Workshop item `3811728541`, manifest `2163081680558740587`. SteamCMD timed out before submission; the signed-in owner's SteamUGC client uploaded the same frozen package successfully. Steam's official download matches all 219 qualified files. Fresh SteamUGC queries confirm unchanged description, title, visibility, cover, gallery order and dependencies; the public API and cover-byte comparison also pass. Receipts are in `build/rv/release-2.0.19.desktop.json` and `release-2.0.19.published.json`. Distribution verification does not establish the version loaded by an already-running game or server.

## Repeatable check

Inside this workspace, admit the complete lifetime through the shared test coordinator:

```powershell
node "D:/Stuff/Projects/Game Mods/games/project-zomboid/tools/run-mod-test.mjs" run --kind performance --name rvi-perf --peak-gib 7 -- pwsh -NoProfile -File dev/performance-session.ps1 -Run performance-new -BaselineRef 2712b0fd8edac9a8c5fa0cd7a51bb5df1185c08d
```

Use a fresh run name. The baseline ref supplies only the old shelf implementation for an isolated live A/B control. Omitting it tests the current package alone. The harness records deployed payload hashes, normal entry/exit input, real container transfers, frame percentiles, cold/warm shelf work, native panic behavior, animal animation advancement and model retirement. Build the package before running. Do not compare results with different FPS limits, camera/scene loads or concurrent heavy workloads.

`-WithDogs` additionally enables the installed Companion Dogs test dependency and alternates hen/dog model lifecycle checks. Its presence and results are recorded separately from the core-only run.

## Primary-source research

- [PZ developer guidance on event cost](https://theindiestone.com/forums/topic/322-events-performance/#comment-5063): use slower gameplay events when sufficient. This advice dates to 2013; current game behavior and profiling take precedence. Per-frame movement/interpolation remains per frame.
- [Oracle JFR performance diagnosis](https://docs.oracle.com/en/java/javase/20/troubleshoot/troubleshoot-performance-issues-using-jfr.html): inspect CPU samples, allocation sites, GC pauses and JVM versus machine load. Frame time and retained-object growth are separate measurements.
- [Oracle WeakHashMap contract](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/WeakHashMap.html): values that strongly reference their keys prevent weak-key collection. Explicit cache lifetime avoids that ownership cycle.
- [Oracle StackWalker](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/StackWalker.html): lazy stack traversal can stop at the required caller pair instead of materializing an entire stack.
- [Khronos OpenGL performance measurement](https://wikis.khronos.org/opengl/Performance): CPU draw submission time is not completed GPU rendering time. Whole-frame measurements are used here; no forced GPU synchronization is shipped.

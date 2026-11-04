# Workshop reports — 3 November 2026

Candidate **2.0.22** is based on released 2.0.21 (`754c364`). The owner deferred game testing on 3 November and requested testing and release on 4 November. Corrected stable/beta native input and dedicated-server checks now pass; see [release qualification](release-2.0.22.md). Original saves, enabled mods, the installed framework and the separate rendering checkout are unchanged.

## Fixes prepared

### ZombieBuddy beta movement and appliance hooks

The [one-direction movement report](https://steamcommunity.com/sharedfiles/filedetails/?id=3811728541#comment_574931289648588282) was followed by confirmation that the player uses ZombieBuddy beta. The installed beta input is Workshop `3812624292`, version `3.0.0-beta3`, downloaded through Steam without subscribing or installing it into the game. Stable ZombieBuddy remains the only Workshop requirement.

An isolated cold-start run with the released 219-file RVI package reproduces seated `player-vehicle` animation selection, zero native movement distance and failed directional control while standing. The old exploratory driver initially reported success because it checked visibility/membership without requiring native movement states; its raw report is retained, and the driver now rejects seated animation sets and missing walk/run states.

Beta3's `PatchEngine.buildAdviceMethodMatcher` silently matches no zero-argument methods when `strictMatch` is true. Its log still says advice was applied. This affects sixteen RVI hooks, including player input, animation groups, facing, refrigeration, animal depth, weather and cleanup. Those targets each have exactly one zero-argument method in Build 42.21. They now use ordinary name matching; all argument-bearing hooks retain strict overload selection. No second mod JAR or framework version change is needed.

`scripts/check-framework.ps1` runs the downloaded beta's actual conversion pipeline and private matcher against the installed game's method descriptions. The released baseline reproduces sixteen unmatched hooks; the candidate matches all 31, with a separate assertion that every relaxed target has exactly one zero-argument method. This is a framework contract check, not corrected native movement or rendering acceptance.

### Generator pickup from the floor

The [generator report](https://steamcommunity.com/workshop/filedetails/discussion/3811728541/574930338697137312/?ctp=2#c564798191048952436) is confirmed by the native baseline: a 40 kg `Base.Generator` is rejected by ordinary inventory capacity even when the character carries only 1.065 kg.

The existing Grab action now delegates a generator's authoritative transfer/equip work to the game's `ISEquipHeavyItem.complete`. The same item moves from Floor storage into both hands; the loose-position record is removed afterward. The UI queues normal unequip actions first and takes one heavy item per batch. If either hand already holds a force-drop heavy item, it queues nothing and asks the player to put that item down first: native unequip would otherwise drop it on the exterior world square. A changed hand state, lost vehicle membership, removed item or lost reach rejects completion without dropping or duplicating items. Ordinary items retain capacity checks.

Production-Lua regressions load the actual native heavy-item action and check accepted base/tagged generators, normal capacity rejection, stale hand state, removed items, exit and reach rejection. The real menu callback is also exercised with engine doubles: ordinary hands, carried heavy items in either hand, a changed hand state during approach, a cancelled approach and Grab All. Subsequent native stable/beta mouse checks pass pickup, drop, ordinary hand-item unequip and rejection while carrying another generator. Dedicated-server pickup/equipment/drop agree on the same item ID across authority, owner and observer.

## Other reports

| Report | Current assessment |
| --- | --- |
| [Invisible interior on entry](https://steamcommunity.com/workshop/filedetails/discussion/3811728541/574930338697137312/?ctp=2#c564798191048942746) | No exact reproduction yet. Active Viewpoint perspective rendering, a failed camera handoff, shader failure and missing body transforms have different diagnostic paths; none is established by this report. No speculative geometry or binding change is included. |
| [Second co-op player sees no interior](https://steamcommunity.com/sharedfiles/filedetails/?id=3811728541#comment_574930972897033507) | Need to distinguish separate network clients from local split-screen. The renderer/cabin currently owns one local session; full split-screen support is not implemented by this patch. Prior two-client qualification does not establish split-screen support. |
| [F700 armored stove/fridge](https://steamcommunity.com/workshop/filedetails/discussion/3811728541/574930338697137312/?ctp=2#c564798191049061074) | Corrected stable and beta native F700 bank-truck controls pass fuel/propane installation, generator/stove switching and real food cooling/aging. The exact reported configuration remains unknown. The stove uses inserted propane by default; the fridge uses the integrated generator or shore power. An engine running or a lighter does not supply either contract. |
| [Contaminated tank](https://steamcommunity.com/sharedfiles/filedetails/?id=3811728541#comment_574931289648506354) | Existing potable water is protected from roof runoff in current code. Previously tainted water remains tainted until the tank is emptied and refilled with clean water. No automatic purification or save-state rewrite is included. |
| [Neat UI opacity](https://steamcommunity.com/workshop/filedetails/discussion/3811728541/574930338697137312/?ctp=2#c574930637987937206) | This report predates the existing live-opacity repair and its native Rocco slider/Apply checks. Current code reads live Neat settings. No new opacity change is justified without a current reproduction. |
| [Exterior furniture on another client](https://steamcommunity.com/sharedfiles/filedetails/?id=3811728541#comment_573804739774729377) | Dependency awning/roof state needs a separate host/guest reproduction. No dependency files or saved exterior state are changed here. |

## Evidence and remaining gate

Prepared candidate checks pass: 130 normal/debug Lua compilations, 190,693 Lua assertions, 285 cutaway/state checks, 22 vision checks, 46 optional-camera checks, all 31 beta hook matches, repository validation and 76 PowerShell parses. Lua tests use explicit engine doubles and the native heavy-item action's actual Lua source. Corrected native gameplay, original-image review and focused multiplayer acceptance are recorded separately in the release qualification.

Local intake and baseline evidence: `build/rv/workshop-reports-20261103` and `build/rv/workshop-bugs-20261103-beta-a`. The baseline exits zero and retains native screenshots, render samples, the actual generator rejection and the downloaded dependency's identity. The disposable beta session was stopped. A later native admission was deferred because the owner's game was running; no attempt was made to take over or terminate it.

The 4 November corrected runs retain the 219-file package across all isolated deployments. Stable movement/turning/bed checks, stable/beta heavy-item and F700 controls, and dedicated-server movement/item replication pass. Regression doubles cover stale-input rejection. The invisible/co-op reports remain unresolved without their exact configuration; successful two-client tests do not establish local split-screen support or resolve every user report.

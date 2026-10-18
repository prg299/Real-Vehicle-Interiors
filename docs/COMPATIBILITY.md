# Compatibility and known limitations

Baseline: Project Zomboid **42.21**, Real Vehicle Interiors **2.0.8**, Workshop `3811728541`. Recheck after game or dependency updates. The mod ID is `RealVehicleInteriors`; old internal `MELens` names are stable compatibility identifiers, not a second required mod.

Keep ZombieBuddy, damnlib, KI5 Campers and '87 Ford B700/F700 enabled before this mod. The game and dependency files are external read-only inputs. The older `ME_LENS` mod ID is obsolete; this extraction does not change enabled mods, server lists or any save.

The published beta has engine-double regressions and historical isolated native evidence. These are separate from human acceptance. Known open gates recorded with the 2.0.8 release include full trait acceptance, fresh multiplayer bus/save-reload checks, loose-item right-click coverage and an intermittent standing-passenger position reset on a server. Fresh extraction/build checks do not close them.

- Indoor Agoraphobic/Claustrophobic panic adaptation needs the Java component on the server as well as clients. The other features keep their existing no-Java-server support.
- Ground plants may show through a camper parked on grass. Small cargo trailers are unsupported.
- At most 64 loose items are drawn inside the occupied vehicle (configurable lower); remaining items stay accessible in storage. A placed lamp does not light the room; portable radios follow the game's passenger/held-item rules.
- Controller placement was previously driven by a scripted controller path, not accepted with a physical controller.
- Animals/Companion Dogs are excluded from `main` and the published payload. Their WIP branch preserves incomplete rendering/multiplayer validation and is not a release recommendation.

## Save changes and removal

Back up the entire save before adding/removing mods or installing development builds. Existing saves, custom furniture, native cargo, deliberately empty layouts and pending timed actions need explicit lifecycle testing. This project has no bulk recovery or uninstall migration.

Before removing it, empty all interior containers, Floor and furniture storage through the normal loot UI; have all occupants exit, save, stop the game/server and keep a complete backup. Custom RV items can disappear when the mod is disabled. Repository reorganization does not modify a save or provide a save-safety guarantee.

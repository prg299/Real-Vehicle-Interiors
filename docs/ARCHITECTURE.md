# Architecture

Project Zomboid loads `mod/RealVehicleInteriors/mod.info`, the `42.21` descriptor and shared `common/media` content. ZombieBuddy discovers the compiled Java entry point `me.lens.rv.Main` and its hooks in `RealVehicleInteriors.jar`.

| Area | Source and responsibility |
| --- | --- |
| Interior definitions | `MELens_Profiles.lua`, `MELens_Profile_*.lua` and `MELens_WalkGrid_*.lua` describe vehicles, entry, furniture positions and walkable areas |
| Vehicle state | `MELens_Parts.lua` extends scripts and maintains stable part order on clients and servers |
| Interaction | Client `MELens_Inside.lua`, `MELens_Interact.lua`, `MELens_Placement.lua` and shared `TimedActions/MELens_Actions.lua` connect input to timed actions and authority |
| Loose items | `MELens_Loose.lua`, `MELens_LooseUI.lua`, `MELens_LooseView.lua` and Java `Loose.java` handle placement, menus and rendering |
| Utilities | `MELens_Utilities.lua`, `MELens_Home.lua`, `MELens_Dashboard.lua` and `MELens_Cabin.lua` manage water, power, propane, washing, names and paint |
| Multiplayer | `MELens_Sync.lua` validates/synchronizes interior passenger state; furniture and inventory use native vehicle parts and timed actions |
| Java hooks | `RV.java`, `Cutaway.java`, `Hooks.java`, `Standing.java` and `Phobia.java` adapt rendering, standing passengers and indoor panic |
| Authored assets | `tools-src/blender/rv_kit.py` and `tools-src/vehicles/make_vehicles.py` generate shells, furniture and profiles from measured/spec inputs |

All Lua filenames above are under `mod/RealVehicleInteriors/common/media/lua/` in their client/shared/server subdirectories. Java files are under `src/me/lens/rv/`. Regression fixtures under `tools-src/regression/` run production Lua through the game's Kahlua runtime with explicit engine doubles.

Vehicle parts and modData carry persistent furniture, inventory and utility state. Part order must remain identical on the server and client; a mismatch can route an inventory packet to the wrong box. Preserve existing part/item/network/modData identifiers. Lua globals and Java package names retain the old internal `MELens` namespace for compatibility; only project/developer folder names have changed.

Runtime shader outputs are assembled under `build/` from local game shaders plus authored recipe edits. The public repository contains no compiled JAR or upstream shader source. The developer endpoint mod is copied only into isolated profiles and is excluded from the production package.

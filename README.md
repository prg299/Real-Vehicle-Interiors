# Real Vehicle Interiors

Walk around inside KI5 campers, B700 buses and F700 box trucks in **Project Zomboid Build 42.21**. Furnish your vehicle, sleep, cook, wash, store supplies and take your base with you.

**Version: 2.0.17 (beta).** [Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3811728541) · [Animals details and testing](docs/ANIMALS.md)

2.0.16 fixes the startup Lua compiler error when debug mode is enabled. Vehicle layouts and saved furniture/loot IDs are unchanged.

Includes the vehicle expansion, Viewpoint compatibility, vanilla dashboard and interior sight concealment.

Supports **193 additional vehicle definitions across 12 body families**, including vanilla vans, step vans, E150s, Chevy step vans and additional armored trucks and ambulances. See [supported vehicles](docs/vehicles.md) for optional vehicle mods and fit details.

## Requirements

Enable these dependencies before `RealVehicleInteriors`:

- [ZombieBuddy](https://steamcommunity.com/sharedfiles/filedetails/?id=3619862853) (`ZombieBuddy`)
- [that DAMN Library](https://steamcommunity.com/sharedfiles/filedetails/?id=3171167894) (`damnlib`)
- [Campers!](https://steamcommunity.com/sharedfiles/filedetails/?id=3670064951) (`KI5campers`)
- ['87 Ford B700/F700 Trucks](https://steamcommunity.com/sharedfiles/filedetails/?id=3110911330) (`87fordB700`)

Clients need the Java component loaded through ZombieBuddy. In multiplayer, the native indoor panic, sight and refrigerator food-preservation adapters also need Java on the server. Other interior features retain their existing support on servers without the Java component.

## Build

Requires PowerShell 7, JDK 25, Python 3.10+, and a local Project Zomboid 42.21 installation with ZombieBuddy.

```powershell
$env:PZ_GAME_DIR = 'C:\SteamLibrary\steamapps\common\ProjectZomboid'
$env:PZ_WORKSHOP_DIR = 'C:\SteamLibrary\steamapps\workshop\content\108600'
$env:RVI_JAVA_HOME = 'C:\path\to\jdk-25'
pwsh -NoProfile -File scripts/build.ps1
pwsh -NoProfile -File scripts/check-release.ps1
```

Output: `build/rv/package/RealVehicleInteriors`. Game files and Workshop downloads are external inputs. The build reconstructs cutaway shaders from the installed game's shaders.

## Files

- `mod/` — Lua, models, textures, translations and mod descriptors
- `src/` — Java source
- `scripts/` — build, checks, install and upload tools
- `tools-src/` — asset generators, shader edits and regression fixtures
- `dev/` — isolated test helpers
- `release/` — Workshop metadata

The `MELens` and `me.lens.rv` identifiers remain for save and add-on compatibility.

Back up saves before changing mods. Known beta gaps include intermittent multiplayer passenger-position resets and incomplete fresh multiplayer bus/save-reload, trait and loose-item interaction checks. No bulk uninstall migration is provided; empty interior storage and have occupants exit before removal.

Carry small animals inside and use their normal right-click actions. Animals use native animations and eat and drink when supplied. Optional [Companion Dogs](https://steamcommunity.com/sharedfiles/filedetails/?id=3740052292) can follow their owner in and out, Stay, be carried and use Bring from outside. Loaded vehicles continue their care; unloaded time pauses Companion Dogs needs. Breeding, egg collection, milking, shearing and unrestricted interior animal AI are outside this version's scope.

The dashboard uses the game's standard window and buttons by default. Enabled Neat UI mods retain the rounded dashboard. Its background transparency follows Neat Rocco's setting, or Neat Crafting/Equipment preferences when Rocco is absent, and updates while open. Text and controls remain readable. Both views use the same resource controls and timed actions.

Solid interior walls block zombie sight, independently of the visual roof cutaway. Windows and open, removed or destroyed doors allow normal spotting. Hearing and pursuit memory use the game's normal behavior: entering an interior does not erase an existing target. Sight uses horizontal hull/opening geometry, like the floor-level checks for vanilla rooms.

## Viewpoint compatibility

Tested with Project Viewpoint **0.1.6.1** on Build **42.21**. Entering a walk-in interior switches first-person or third-person view to isometric, including when using interior furniture. Driver seats keep Viewpoint controls; after leaving an interior, use Viewpoint's normal camera keys to change views again.

Native single-player checks cover camper and bus entry/exit, walking, bed/dining seats, Dashboard menus and the F700 driver camera. Multiplayer, split-screen and controller combinations still need testing. Viewpoint remains optional and its files are not included.

## License

[MIT](LICENSE) for authored contributions. See [third-party notices](THIRD_PARTY_NOTICES.md) for external dependencies and generated shaders.

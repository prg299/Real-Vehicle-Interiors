# Vehicle expansion

The expansion adds 193 vehicle definitions to the 10 already supported: **203 total** on Build 42.21. Variants share a layout only when their resolved body mesh and model scales match.

| Body family | Added variants | Vehicle mod |
| --- | ---: | --- |
| Franklin Valuline cargo vans | 55 | Vanilla |
| Franklin Valuline passenger vans | 9 | Vanilla |
| Vanilla ambulance | 1 | Vanilla |
| Radio vans | 2 | Vanilla |
| Chevalier step vans | 29 | Vanilla |
| Ford E150 short vans | 54 | ['86 Ford Econoline E150](https://steamcommunity.com/sharedfiles/filedetails/?id=2870394916), including its expanded variants |
| Ford E150 long vans | 9 | Same E150 mod |
| Ford E150 long passenger vans | 2 | Same E150 mod |
| Chevy step vans | 28 | ['85 Chevrolet Step-Van](https://steamcommunity.com/sharedfiles/filedetails/?id=3614034284), including its expanded variants |
| F700 armored bank truck | 1 | ['87 Ford B700/F700](https://steamcommunity.com/sharedfiles/filedetails/?id=3110911330) |
| F700 SWAT truck | 1 | Same B700/F700 mod |
| Ford F350 ambulance and SWAT | 2 | ['90 Ford F350 Ambulance](https://steamcommunity.com/sharedfiles/filedetails/?id=2952802178) |

Install the vehicle packs you want and enable them before Real Vehicle Interiors. The new packs are optional; they are not bundled or added as mandatory dependencies. The full script-ID list is in [coverage.json](../tools-src/vehicles/coverage.json).

Enter at the rear door using the normal interact key. Interiors begin empty and retain the vehicle's original cargo containers, loot and capacities. Bring RV furniture to furnish them. Smaller vans fit a bed along one wall and a kitchenette across the front, with a clear aisle beside the bed. Wider vehicles have places on both sides. Placement checks the furniture's actual footprint and rejects genuine overlaps. Where alternative markers overlap, the pointer selects the nearest marker centre.

The F700 box truck also accepts a bed and kitchenette along the same wall after clearing the cargo in their footprints. A bed is 1.5 m wide, a kitchenette 1 m, and a cargo box 0.5 m: adjacent highlights are possible positions, not always separate rooms for two pieces. Remove stacked boxes from above before clearing the boxes below.

Stock vehicles retain their native paint masks while inside, and road wheels keep their original rendering. The F700 box, bank and SWAT trucks preserve their separate cab roofs above the cargo cutaway. Each profile resets the previous vehicle's optional cab-height limit, preventing an armored truck's cutoff from damaging a stock van's cab. Shared clipping rules inventory every variant's factory models, including custom rear chairs, liners and roof accessories, while preserving the cab ahead of the compartment.

These are physical interiors inside the vehicle body, with dimensions measured from the installed model. They do not use separate map rooms. The Arcadia RV Interior coverage list was used to identify candidate vehicles; its scripts, room maps and assets are not included. Livestock/Animals support remains separate on `animals-support`.

## Rebuilding the expansion

The ordinary build uses the checked-in profiles, walk grids and authored shell mesh. Regenerating them requires the game and vehicle packs above, Blender 3.6, Python, and the read-only Arcadia Workshop reference `3773972040`. Run the following tools in order through the machine's resource guard:

1. `tools-src/vehicles/catalogue.py` resolves the installed coverage and external assets into ignored `build/rv` metadata.
2. `tools-src/vehicles/prepare_expansion.py` groups matching body meshes and scales.
3. Blender runs `tools-src/blender/measure_fleet.py -- build/rv/floorplans/fleet-measures.json` to measure geometry.
4. `tools-src/vehicles/build_expansion.py` generates layout specs, profiles and model declarations.
5. Blender runs `tools-src/blender/rv_kit.py -- mod/RealVehicleInteriors/common/media --shells-only --shell-file=MELens_Fleet` with every generated `shell_<family>.json` config in the coverage file.

Blender's binary FBX importer handles most models. The vanilla step van uses ASCII FBX; install the `ufbx` Python wheel matching Blender's bundled Python into `.tools/ufbx-blender`, or set `RVI_UFBX_DIR`. This tool dependency and all external vehicle geometry stay outside the shipped mod. New shells reuse the existing F700 wall/floor materials.

Native test evidence and remaining limits are recorded in the feature pull request. The audit covers all 203 script variants with keyboard entry, furnished-aisle movement, exit, four interior headings and a closed exterior. The extra headings use fresh vehicle/seat fixtures rather than driving input. Inventory mouse/UI placement, rejection of genuinely overlapping furniture and rest/get-up are checked per added body family, plus the reported F700 box-truck bed/kitchen case. Dedicated-server, split-screen/controllers, every optional cosmetic combination, performance and human acceptance remain separate checks.

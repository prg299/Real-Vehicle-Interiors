# Real Vehicle Interiors 2.0: the mobile-base upgrade

Written 2026-10-03 against source 1.5.1 and Build 42.21.0 (engine facts below were read from
the game's Lua and from `projectzomboid.jar`, decompiled with the CFR in `.tools`). Status:
**built the same day as source 2.0.0** (section 0 says what is built, what was changed on the way
and what is not done, and why). Checked in the isolated test game and with one and with two players on
a local dedicated server; not installed in the owner's profile and not published.

## 0. What was built

The decisions of section 6 were taken as recommended there (dropped items visible, propane on by
default, things fall in crashes only by default, repaint with any paint can, the shelf unit yes and
the sofa no, refuse to pick up a piece with something on it, M0 and M1 first).

| Milestone | Result |
| --- | --- |
| M0 render spike | Done. `Loose.java` draws items inside the cut vehicle's own draw, after its last sub-model (`Hooks.AfterVehicleModel`), with the part shader: furniture lighting, depth sorted with walls and furniture, same size and turn as the game's ground items, 10 to 25 microseconds a frame. The list belongs to one vehicle (`beginLoose(vehicle)`), a failing entry is skipped and a failure of the whole draw is retried. |
| M1 place and grab | Done. Place mode (mouse and controller), Drop and drag-to-place, Grab, Grab all here, Move, Turn; positions in the Floor part's modData (`loose[itemID] = {t, x, y, z, r, s}`), items stay ordinary items of the Floor container; 1.5 saves get positions for their Floor items on the fly; items with no 3D model are flat pictures of their icon. The server checks every placement again (`MELens.Loose.checked`). |
| M2 surfaces | Done for the kitchen (stove, counter), dinette table, cabinet, fridge, wardrobe, beds, boxes, wheel wells and the new shelf unit. The surfaces are written by hand in `MELens_Loose.lua` (not emitted by `rv_kit.py` as planned); `dev/surface_audit.py` checks each one against the real triangles of its piece, headroom included. |
| M3 items that do something | Bags on a surface are containers with their own loot tab (the loot window is told when the Floor changes). **Not built:** radios (the game only runs a portable radio while a player holds it) and lit candles, lanterns and torches as lights (the game puts them out when they are set down, and does not update items in vehicle containers, so they would never burn down). |
| M4 living systems | Done: rain fills the tank (tainted), propane for the stove and the heater (vehicle modData `MELensPropane`, two tanks' worth, a vehicle starts with 0.4, dashboard card, Insert Propane Tank at the dashboard and the pieces, sandbox option), shore power, washing clothes and bandages at the tap. |
| M5 make it yours | Done: name, wall paint (`MELensWallTint` in the shell shader), the RV Shelf Unit (two compartments and a top, craftable, found as loot, six translations, an icon from the image model). **Not built:** the sofa, which the plan called optional. |
| M6 travel and siege | Done: a crash or hard braking throws what stands on furniture and wheel wells to the floor (sandbox option: stay put, crashes, crashes and hard braking; crashes by default). **Not changed:** who a zombie can hit. `AttackVehicleState.isPassengerExposed` is server Java and this mod's Java is client-only, so the game's rule for the entry door stays. |
| M7 polish | Done: controller place mode, translations (German, French, Spanish, Brazilian Portuguese, Polish, Russian), sandbox and mod options, dashboard cards (Propane, Home, shore power chip), README, Workshop text, version 2.0.0, a new jar. **Not made:** new preview pictures for the Workshop page. |
| M8 multiplayer and release | Done on a local dedicated server: one client (`dev/mp_test.ps1`, 21 checks), two players in one camper (`dev/mp_two.ps1`, 14: both inside, each sees the other walk, what one sets down the other sees and takes), a second player arriving at a camper it had never been sent (`dev/mp_late.ps1`, 14), the Floor tab's own transfer action (`dev/mp_floor_tab.ps1`, 12), rain filling the tank (`dev/mp_rain.ps1`, 6) and a server save, quit and restart on the same world with the camper, its items, name and paint coming back (`dev/mp_save.ps1`, 8); in single player a save and reload (`dev/persist_test.ps1`, 5). It found a bug that is older than 2.0: the server refused every walk-in because the standing seat held no item (fixed with the marker item `Base.MELensRV_Seat`; the published 1.5.x seat parts hold no item either). **Not tried:** a public or Steam server, the Lua checksum with ordinary player installs (the test server has it off), a player logging in next to items, three or four players, a slow connection, a 1.5 save on a server, shore power on a server, a real controller. The release package is prepared by `scripts/workshop_upload.py` (prepare only; the upload is the owner's step). |

Changes on the way, found by looking at the real game: positions carry the item's type so a client
can draw without holding the container's items; the draw uses the game's item scale factor 1.5; bags
keep their colour (`tx tr tg tb`); surfaces with headroom (`head`) for the shelf; hover and clash
tests look at the board's height, not only the piece; a piece placed over items on the floor, or a
box over items on the box below, moves them to free floor (`displace`).

## 1. The goal

Inside a camper, a bus or the box truck should work like a room of a house: you put things
down where you want them, see them lying there, pick them up again, and live out of the
vehicle. The one thing a house has that the inside of a vehicle cannot have is the game's own
tiles and furniture (walls, counters, shelves, posters are map objects on map squares; a
vehicle has none). Everything that is an *item* can work, and that is what this plan builds:

- **Place anything** that the game can place in a house: right-click an item, **Place**, a
  see-through preview follows the mouse over the floor, the counter, the table, the bed, the
  shelves, rotate it, click, and it stands there. What you place is drawn as its 3D model,
  travels with the vehicle, shows in the loot window's Floor, and you grab it back with a
  right-click. Dropped items lie on the floor where you dropped them.
- **Live in it**: a bag on the counter is a container you loot; a radio on the table plays; a
  lit candle or lantern on the floor lights the room; rain on the roof fills the water tank;
  the stove and heater burn propane you have to find; a generator parked beside it powers it;
  you wash your clothes at the sink.
- **Make it yours**: name the vehicle, repaint the walls with any paint can, add a shelf unit
  for your plushies and books, and the layout you built stays with the vehicle.
- **Travel**: slam the brakes and what stood loose on the counter is on the floor (sandbox
  option); zombies only reach you at the door you came in by.
- **Polished**: controller, six translations, sandbox and mod options, multiplayer tested with
  two players, Workshop page with new pictures, and the same visual acceptance as 1.5 (every
  vehicle from four headings).

Out of scope, and why, is in section 7.

## 2. Why Place does nothing today (root cause)

1. The game hides the option in any vehicle: `ISInventoryPaneContextMenu.doPlace3DItemOption`
   (`media/lua/client/ISUI/ISInventoryPaneContextMenu.lua:4414`) starts with
   `if player:getVehicle() then return end`. Inside a walk-in vehicle you are a passenger, so
   the inventory menu never offers **Place**.
2. Even if it did, the game's cursor and action cannot work in a vehicle:
   `ISPlace3DItemCursor` (`media/lua/server/BuildingObjects/ISPlace3DItemCursor.lua`) places
   on a map square under the mouse (`getSquare(worldX, worldY, z)`), checks that square's
   walls and surfaces (`square:getObjects()`), and `ISDropWorldItemAction:complete()` calls
   `square:AddWorldInventoryItem(...)`. A world item is an object *of a square*; it does not
   move with a vehicle, and the squares under a camper are the ground outside.

So the mod needs its own place cursor, its own storage for placed items and its own drawing
of them, the way it already has its own furniture spots. 1.5 already has every building
block for that: a vehicle-attached container (the **Floor** part), a mouse-ray picker over
the furniture (`MELens_Interact.pick`), a placement mode with floor highlights and a ghost
(`MELens_Placement.lua`), server-side timed actions, and a Java render hook that draws
models inside the one vehicle you are in (`Cutaway.beginVehicleDraw`).

## 3. Design: loose items

### 3.1 Data

- A placed or dropped item is an ordinary item in the vehicle's **Floor** container
  (`MELensFloor`, capacity 100), exactly as today. Nothing changes for saves: the Floor is
  already saved and synced by the game as a vehicle part container.
- Where it lies is in the Floor part's modData: `loose[itemID] = { x, y, z, r, s }` in
  passenger space (tiles; `x` left, `y` up, `z` front), `r` the yaw in degrees in 10 degree
  steps like the game's cursor, `s` the surface it stands on (`0` the floor, otherwise the
  spot index of the piece it stands on). Item IDs are stable across saves and the same on
  the server and every client, so this keys cleanly. Server-side changes go out with the
  existing `MELens.Utilities.transmit` (`vehicle:transmitPartModData`), the path the
  generator and tank already use; nothing new to sync.
- An item in the Floor without an entry (a 1.5 save, an item dragged into the Floor tab, a
  mod that moves items) gets a position the first time the Floor part updates on the server:
  at the feet of the nearest standing passenger (the server knows every passenger offset
  through `MELens_Sync`), else just inside the door, scattered a little, on free floor.
  Dropping from the inventory records the position at the character's feet in the drop
  action itself (section 3.4), so the common case is exact.
- Entries whose item left the container are pruned on the same update. Entries whose surface
  piece is gone fall to the floor below (same rule as a box with nothing under it,
  `MELens.Parts.settleBox`).

### 3.2 Surfaces

Each furniture piece declares the flat tops you can put things on, in the piece's own frame
(along its length, out from the wall, height above its base), emitted by
`tools-src/blender/rv_kit.py` into `MELens_RVKit.lua` next to width, depth and capacity:

| Piece | Surfaces (from the builder's boxes in `rv_kit.py`) |
| --- | --- |
| kitchen | `stove`: the steel plate over the burners (height 0.878, a pot on the grate); `sink`: the basin floor (0.838); `counter`: the laminate strip left of the burners and right of the sink (0.845) |
| dinette | `table`: the laminate top (0.595, 0.42 by 0.50); `seat`: each bench cushion (0.31) |
| cabinet | `top` (0.80) |
| fridge | `top` (0.88) |
| wardrobe | `top` (0.90) |
| washroom | `counter` beside the basin (its top height) |
| bed | `mattress` (0.28, the whole 1.47 by 0.53): bags and books on the bed |
| box | `top` (0.40), only while no box stands on it |
| busseat, busseat2 | `seat` cushions (0.415) |
| heater, shelf (new, section 5) | none / three shelves (0.35, 0.62, 0.90) |

The floor is a surface too: the walk grid's open cells plus the furniture-free rectangle in
front of each piece (items may stand where you cannot, under a table, between benches), at
`profile.floorY`. A piece's surfaces convert to passenger space with `MELens.Parts.spotPoint`
(the frame the spots already use), so the same geometry serves the preview, the validity
test, the mouse picker and the drawing.

### 3.3 Drawing (Java, render thread)

The game draws a world item live with `ItemModelRenderer.renderModel`
(`zombie.core.skinnedmodel.model.ItemModelRenderer`, decompiled lines 538 to 641): a static
model, one texture, `basicEffect` or the model script's shader, ambient, tint, one transform,
`model.mesh.Draw(effect)`. Its transform is `scale(modelScript.scale)` times the inverse of
the model script's `attachment world` times the mesh transform
(`ModelInstanceRenderData.postMultiplyMeshTransform`), with the yaw applied by the camera.
That is forty lines we can repeat inside the vehicle's own draw, which is where placed items
must be drawn so that they sort with the walls and furniture (the game sorts a world item by
its square; inside a long camper that puts it in front of or behind the whole vehicle, the
same fault `Cutaway.alignCabinDepth` fixes for characters).

Plan:

- `Loose.java` keeps an immutable array of entries `{ item, model, localMatrix, ghost,
  alpha }` published from the main thread. Lua rebuilds it when the Floor's contents or the
  `loose` table changed (checked twice a second, like `MELens_Interact.updateReach`) and the
  placement mode updates one ghost entry per frame. Model resolution happens on the main
  thread in the publish step: `ScriptManager.getModelScript(item.getWorldStaticItem())`
  (weapons: `getStaticModel()`; head clothing as `ItemModelRenderer.itemHasModel` does), then
  `ModelManager.instance.tryGetLoadedModel(mesh, tex, static, shader)` and, once,
  `loadAdditionalModel`; an entry is drawn only when `model.isReady()` and its mesh and
  texture are. Food states (cooked, burnt, rotten), fluid models and tints follow the
  renderer's rules; weapon attachments (scopes) are a later nicety.
- Draw point: after the vehicle's last sub-model. `ModelSlotRenderData.renderVehicle` is the
  loop that calls `Model.DrawVehicle` for every sub-model; a ZombieBuddy `OnExit` patch on it
  (it is private; if ZombieBuddy cannot bind it, fall back to detecting the last entry of
  `slot.modelData` in the existing `endVehicleDraw`) draws the loose items of the cut vehicle
  only (`slot.object == RV.cutVehicle`), so every other vehicle costs one reference check.
- Per item: `ModelCamera.instance.Begin()`, translate by `slot.centerOfMassY`, push the body
  transform times the item's local matrix (the body transform is what `Cutaway.bodyTransform`
  already finds; the local matrix maps passenger space to the body's mesh space with the
  profile's `mesh.scale` and `mesh.lift`, as `toMesh` does in Lua), start the existing
  `melens_cutaway_part` static shader with `transform` = identity, `MELensToBody` = the local
  matrix, `MELensShade.w` = 1 and `MELensBodyUp.w` = 1 (lit and shaded as furniture, clipped
  out of the wheel wells, never cut), the item's texture on `Texture`, the vehicle's
  `targetDepth`, `Alpha` and `MELensGhost` for the preview, then `mesh.Draw`, `End`, pop.
  The item models are `ImportedStaticMesh` meshes with position, normal and uv at attributes
  0, 1, 2, the layout the static part shader reads (checked for the Motorclub wheels on
  2026-10-01).
- Items without a model (the game draws those as a flat sprite): a unit quad added to
  `MELens_RV.fbx` with the item's icon texture (`item.getTex()`) lying flat on the surface.
- Picking: `MELensRV.looseBounds(item)` returns the loaded model's box (scaled, world
  attachment applied) so Lua can intersect the mouse ray with each item's box first (they
  stand on top of the furniture), then the pieces as today.
- Budget: at most 64 drawn per vehicle (mod option; the rest stay in the Floor tab), one
  draw call each, no allocation on the render thread (arrays are built on the main thread).
  Acceptance: less than 0.3 ms per frame added with 64 items, measured with the existing
  capture harness.

### 3.4 Interaction (Lua)

- **Place** in the inventory and loot menus while inside (added through
  `OnFillInventoryObjectContextMenu`, the game's own option is never patched; same name,
  same Place One / Half / All submenu, favourites refused like the game), for items the game
  itself can place (`item:getWorldStaticItem()`, hand weapons, head clothing). The mode is a
  full-screen element like `MELens.Placement.Mode`: the ghost follows the mouse over the
  topmost surface under it, Toggle Mode cycles to the surfaces below it and the floor as the
  game's cursor does, R and Shift+R turn it in 10 degree steps (hold to spin,
  `KeybindId.ROTATE_BUILDING`), the ghost is green where it fits and red where it does not,
  a label says "Place X here". Fits means: the item's box lies inside the surface rectangle
  (or on open floor), overlaps no piece, no other loose item and no wall, and the Floor has
  weight left. Left click walks you within reach and queues `MELensPlaceLoose`; right-click or
  Escape stops; Place All continues with the next item of the stack.
- **MELensPlaceLoose** (shared, work in `complete()` like the other actions): duration and
  sound as `ISDropWorldItemAction` (by weight, `getPlaceOneSound`), a lit candle or lantern
  becomes its unlit item the way the game does it, the item moves to the Floor container and
  its entry is written and transmitted. Devices (radios) are registered for updates (3.5).
- **Drop** (menu or drag) keeps going to the Floor but through `MELensDropLoose`, which
  records the position at your feet with a small scatter, so what you drop lies where you
  stand, like outside. The game's `onDropItems` loop calls `dropItem` per item, so the
  existing override point covers both paths.
- **Right-click a loose item**: its name as the header, then Grab (walk within reach,
  `MELensGrabLoose` with the game's grab timing), Grab all here (everything within 0.3 tiles),
  Move (re-enter the place mode holding it), Rotate 90 degrees; devices get Turn on / off
  from the game's own inventory handlers (they already work on items in the Floor tab, the
  radio's at `ISInventoryPaneContextMenu.lua:199`). Left click selects the Floor tab in the
  loot window.
- **Furniture rules**: picking up a piece with something on it says "Clear the top first"
  (the same shape as "Empty it first"); placing a piece never overlaps a loose item.
- **Controller**: the place mode positions the ghost 0.3 tiles in front of the character,
  the left stick nudges while Y is held, bumpers rotate, A places, B stops (the game's own
  bindings for its cursor); "Use nearby furniture" also lists the nearest loose items.

### 3.5 Item behaviours inside

- **Containers** (bags, boxes placed on a surface): the loot window already lists container
  items inside vehicle part containers as their own tabs (the game's `refreshBackpacks` does
  it for any part but the glove box), so a bag on the counter is lootable at once. Verify the
  Floor tab's access test keeps them in reach from anywhere inside.
- **Radios and other devices**: an item in a vehicle container is not updated by the game
  (`BaseVehicle` never calls `addItemsToProcessItems`), so a placed radio would be silent.
  Registering it with `getCell():addToProcessItems(item)` on placement and load, and
  `addToProcessItemsRemove` on grab, runs `Radio.update()` like a radio lying on the ground.
  Only devices are registered (`shouldUpdateInWorld` dereferences a world item for food and
  fluids and must not be reached). Where the game positions the sound of a radio without a
  world object is to be verified in milestone 3; the fallback is driving the vehicle's own
  emitter.
- **Light**: a lit candle, lantern or flashlight placed inside (`item:isEmittingLight()`,
  `getLightDistance()`) adds a light to the camper's lamps: the shader's lamp list grows from
  two to eight entries and the world light the mod already keeps for the lamps
  (`updateWorldLight`, an `IsoLightSource` at the vehicle) gets one per lit item, so the room
  and the ground outside light up as they do for the ceiling lamps.
- **Weight**: the Floor's 100 stays; the game's own floor refuses above 50 per square, so
  this is generous and leaves the truck's boxes as the real storage.

### 3.6 Multiplayer

Everything is server-authoritative through what 1.5 already uses: items move in `complete()`,
positions live in part modData and are transmitted by the server, each client draws the
vehicle it is in. New is only the `loose` table and the device registration, which every
client does for the vehicle it is in. The live two-player test that 1.5 still owes is part of
milestone 8 and covers placing, grabbing, seeing the other player's items appear, and a
reload of the server.

### 3.7 Compatibility and save safety

- No game function is replaced for the Place feature; the mod adds its option through
  events and keeps `ISInventoryPaneContextMenu.dropItem` as the one existing override.
- Hooks stay structural (the ZombieBuddy patches bind by class and method, no class hashes),
  the render hook allocates nothing and asks the GL for nothing per frame.
- Saves from 1.5 load unchanged: the Floor's items get positions lazily, parts and IDs are
  untouched, new sandbox options have defaults. Mod ID, part IDs and item types stay.
- Other mods' items place like the game's own as long as they have a `WorldStaticModel`.

## 4. Milestones

Each milestone ends with the stated checks in the isolated test profile
(`scripts\testgame.ps1`, drivers in `dev\lua`, `scripts\lua.ps1`), one `dev\iterate.ps1`
round per change while working and the four-heading sweep (`dev\review_interiors.ps1`,
`dev\review_zoom.py`) once at the end of each milestone that changes what is drawn.
Estimates are working sessions of the kind that produced 1.4 and 1.5.

### M0: render spike (half a session)

Draw one vanilla item model (a plushie and a radio) at a scripted passenger-space point
inside the Flying Cloud 22 through the vehicle draw, lit and depth-sorted with the furniture,
moving with the camper, from all four headings. Nothing in Lua but a test driver.
Pass: the item is drawn inside, hidden by furniture in front of it, visible over furniture
behind it, not drawn in the camper you are not in, and the frame time is unchanged. This is
the only real technical risk of the plan; if the vehicle camera and the part shader do not
take the item meshes as expected, the fallback is a dedicated `melens_item` shader cloned
from `basicEffect` with the cutaway uniforms added.

### M1: place and grab (2 sessions)

The `loose` table, `MELensRV.setLoose` publishing, the place mode (floor only), the place,
drop and grab actions, the loose-item picker and menu, Floor-tab behaviour, lazy positions
for old saves, the model-less quad. Test drivers: `dev\lua\loose_place.lua` (places a set of
items at known points and reports the table), `loose_grab.lua`, a drop test extended from
`dev\lua\drop_test.lua`. Pass: place, see, save, reload, grab, in all eight vehicles; a 1.5
save's Floor items appear on the floor; placing fails cleanly where it should (walls,
furniture, weight).

### M2: surfaces and stacking (1.5 sessions)

Surfaces in `rv_kit.py` and `MELens_RVKit.lua`, surface cycling in the place mode, items on
pieces follow the piece's spot and block its pick-up, items fall when their piece or box goes,
the Floor's free rectangles. Pass: a pot on the stove, dishes in the sink, a bag on the bed,
a plushie on each shelf of a box stack, from four headings; `dev\clip_audit.py` extended to
assert every declared surface lies inside its piece's footprint and clear of the walls.

### M3: items that do something (1 session)

Container items on surfaces verified in the loot window, device updates and the radio sound
position, lit items as lights, the stack and favourite rules, sounds for place and grab.
Pass: a radio on the table plays and keeps playing after a reload; a lit lantern on the
floor lights the room at night (capture); a bag on the counter opens as a tab.

### M4: living systems (1.5 sessions)

- **Rain collection**: the roof fills the tank at a rate from
  `getClimateManager():getRainIntensity()` and the vehicle's roof area, as tainted water (like
  the game's rain barrels; boil it on the stove); sandbox option, default on.
- **Propane** (decision 2): a Propane card on the dashboard that takes propane tanks; the
  stove and heater draw from it, the generator powers the fridge and charges the battery.
  Sandbox toggle "Stove and heater need propane", default on; off keeps 1.5's behaviour.
- **Shore power**: a running, connected generator within three tiles of a parked vehicle
  powers it (fridge, battery charging) without its own generator running; shown on the
  dashboard as "Shore power".
- **Wash clothes and bandages at the sink**: own actions mirroring `ISWashClothing` and
  `ISWashYourself` against the tank's water and your soap.
- Pass: each shown on the dashboard and in a scripted day (`dev\lua` driver advancing the
  clock) with the expected litres and charges.

### M5: make it yours (1.5 sessions)

- **Name it**: rename from the dashboard (vehicle modData, synced); the name appears in the
  dashboard title, "Walk into <name>" and the loot window tooltip.
- **Repaint the walls**: any paint can with a brush recolours the shell walls through a tint
  uniform on the shell models (one uniform, no new textures), per vehicle, synced; the door
  leaf's painted inside follows it.
- **RV Shelf unit**: a new kit piece (0.52 by 0.32 by 0.90, three shelves as surfaces,
  capacity 0), built, baked, iconed, craftable and found as loot like the others, fitted to
  every vehicle's spot list by `make_vehicles.py`; and, if wanted, an **RV Sofa** (a 1.5
  wide seat piece for the dinette spots).
- Pass: the furniture-look comparison against the game's tiles for the new piece
  (`dev\vanilla_compare.ps1`), four headings, rename and repaint survive a reload.

### M6: travel and siege (1 session)

- **Loose items while driving** (decision 3): sandbox option Off / Crashes / Hard braking
  and crashes. On the server, the Floor part's update watches the speed between updates
  (`getBrakeSpeedBetweenUpdate`, a drop of more than 25 km/h in one update as a crash) and
  moves items on surfaces to the floor below with a clatter (`addSound`, a vehicle emitter
  sound). Nothing breaks; nothing leaves the vehicle.
- **Siege rules**: the game lets a zombie hit a passenger when `AttackVehicleState.isPassengerExposed`
  says so, by the door or window of that passenger's seat; the standing seat's door is the
  entry door. Verify what happens with a zombie at the entry door while you stand at the far
  end, and with one at a window; if a zombie reaches you across the room, patch the exposure
  test so a standing passenger is exposed only within 0.8 tiles of that door or a broken
  window near them. Pass: recorded test with a scattered horde (`dev\lua\horde.lua`).

### M7: polish (1.5 sessions)

Controller placement and menus; translations of every new string in DE, FR, ES, PTBR, PL,
RU; sandbox options (rain, propane, loose items while driving, shore power) and mod options
(drawn item cap, show dropped items); the dashboard cards for propane, shore power and the
name; footstep sounds while walking inside if the standing set plays none; tooltips on
disabled options; the README "Playing" section, `release/workshop/description.txt`, change
notes and new preview pictures (`dev\tow_setup.ps1`, `dev\record.ps1`); version 2.0.0 and a
new jar (one ZombieBuddy approval for players).

### M8: multiplayer and release (1 session)

Two clients on `dev\mp_server.ps1`: place, grab, drop, rename, repaint, propane and rain,
both players in one camper, a server restart. Then the four-heading sweep of all eight
vehicles with a furnished floor, the 1.5 regression list (entry, exit, seats, sleep, boxes,
dashboard), `scripts\build.ps1`, `scripts\workshop_upload.py`, the SteamCMD upload through
`Upload Real Vehicle Interiors.cmd` (the owner logs in), and the download comparison the
other projects record.

Total: about 11 sessions. M0 and M1 are the ones that matter; everything after them is
additive and can be reordered or dropped.

## 5. New content list

| Kind | Items |
| --- | --- |
| Furniture pieces | RV Shelf unit (surfaces), optional RV Sofa |
| Dashboard cards | Propane, Shore power, Name |
| Actions | Place loose, Drop loose, Grab loose, Rotate loose, Rename, Repaint, Wash clothing, Wash bandage, Add propane tank |
| Sandbox options | Rain fills the tank, Stove and heater need propane, Loose items while driving, Shore power |
| Mod options | Loose items drawn per vehicle (16 to 64), Show dropped items on the floor |
| Java | `Loose.java` (publish and draw), `MELensRV.setLoose / clearLoose / setLooseGhost / looseBounds / setWallTint`, up to eight lamps, the render hook on `renderVehicle` |
| Tools | surfaces in `rv_kit.py`; `dev\clip_audit.py` surface checks; `dev\lua\loose_*.lua` drivers; a loose-items scene in `dev\review_interiors.ps1` |

## 6. Decisions (taken as recommended on 2026-10-03, see section 0)

1. **Dropped items visible on the floor** (not only in the Floor tab). Recommended: yes, with
   the 64 cap and a mod option to turn it off.
2. **Propane for the stove and heater** as a resource you find, with the generator for the
   fridge and battery. Recommended: yes, sandbox toggle, default on.
3. **Loose items fall off surfaces in crashes and hard braking.** Recommended: on, crashes
   only by default.
4. **Repaint with any vanilla paint can** (tint). Recommended: yes.
5. **New pieces**: the shelf unit yes; the sofa optional; bunks and overhead cabinets no
   (they stand above the cut wall height and would float over the cutaway).
6. **Picking up a piece with items on it**: refuse ("Clear the top first") or tumble them to
   the floor. Recommended: refuse, consistent with "Empty it first".
7. **Order**: M0 then M1 first, before anything else. Recommended.

## 7. Out of scope, and why

- **The game's own furniture, tiles and wall decor** (counters, shelves on the wall,
  posters, curtains, TVs): map objects need map squares, and a vehicle has none. The
  interior-map approach (a separate map cell you teleport into, the ME: VIR project) has
  them but is a different mod with a different feel; this mod's identity is the real vehicle
  with the roof cut away.
- **Wall-mounted decor as mod pieces**: anything on a wall above the cut height (0.6 to 1.05
  above the floor, 0.38 on the camera side) is cut away or floats over the cut edge.
  Decor lives on surfaces instead (the shelf unit exists for this).
- **Fire inside, zombies getting in, windows and blinds, towing changes, walking while the
  vehicle moves**: the game's vehicle rules stay as they are.
- **More vehicles**: the spec pipeline ("Adding another vehicle" in the README) takes new
  KI5 bodies after 2.0; nothing here depends on it.

## 8. Engine facts this plan relies on

| Fact | Where it was read |
| --- | --- |
| Place is hidden in vehicles | `ISInventoryPaneContextMenu.lua:4414` `doPlace3DItemOption`: `if player:getVehicle() then return end` |
| The game's cursor needs squares and surfaces of tile objects | `ISPlace3DItemCursor.lua`: `isValid`, `getSurface`, `renderOpaqueObjectsInWorld` |
| Placing creates a square object | `ISDropWorldItemAction.lua` `complete()`: `sq:AddWorldInventoryItem`, `setWorldZRotation`, radio becomes `IsoRadio` |
| Which items can be placed | `ItemModelRenderer.itemHasModel`: `getWorldStaticItem()` model script, head clothing, hand weapons' `getStaticModel()` |
| How a world item model is drawn | `ItemModelRenderer.renderMain` (model lookup, food and fluid variants, scale, `attachment world`) and `renderModel` (static shader, texture, ambient, tint, `setTransformMatrix`, `mesh.Draw`) |
| Vehicle sub-model draw and depth | `Model.DrawVehicle`: `ModelCamera.instance.Begin()`, translate `centerOfMassY`, `pushAndMultMatrix(instData.xfrm)`, `targetDepth` from `squareDepth`; `ModelSlotRenderData.renderVehicle` loops `modelData` |
| Model loading on demand | `ModelManager.tryGetLoadedModel(mesh, tex, static, shader)`, `loadAdditionalModel`, `getLoadedModel`; readiness `model.isReady()`, `mesh.isReady()`, `tex.isReady()` |
| Items in vehicle containers are not updated | no `addItemsToProcessItems` in `BaseVehicle`; `IsoCell.addToProcessItems(InventoryItem)` is public; `IsoWorldInventoryObject.update` uses it |
| `shouldUpdateInWorld` dereferences the world item for food and fluids | `InventoryItem.java` decompiled line 1217 |
| Container items inside vehicle parts get their own loot tabs | `ISInventoryPage.lua:1581` to `1620` (`refreshBackpacks`, vehicle branch) |
| Item sync has no modData transmit | `InventoryItem` exposes `syncItemFields` only (players and world items); hence positions in part modData |
| Passenger exposure to zombies | `IsoZombie` variable `bpassengerexposed` from `AttackVehicleState.isPassengerExposed`; `BaseVehicle.chooseBestAttackPosition`, `getPassengerDoor(seat)` |
| Lights | `IsoLightSource(x, y, z, r, g, b, radius)`, `IsoCell.addLamppost` / `removeLamppost`; `InventoryItem.isEmittingLight`, `getLightDistance`, `getLightStrength` |
| Static mesh attribute layout | position, normal, uv0 at 0, 1, 2 (`games/project-zomboid/LEARNINGS.md`, Motorclub 2026-10-01); the mod's `melens_cutaway_part_static.vert` reads exactly these |

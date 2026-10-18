# Historical Animals design and validation notes

These are Claude's existing design/status notes, imported as provenance. They were not rerun or independently accepted during the open-source extraction. Paths below describe the original isolated project. See [current branch status](../ANIMALS.md).

# Animals inside (plan, 2026-10-17)

The owner asked: animals can be dropped inside the interiors and picked up again; Companion Dogs then work inside
too; animals eat and drink from bowls of food and water inside, as they do outside.

## What the game already has (read from Build 42.21)

- A carried animal is an `AnimalInventoryItem` (`Base.Animal`) holding the `IsoAnimal`. Drop puts it back into the
  world (`IsoGridSquare.AddWorldInventoryItem(item, ..., true)`); inside ME: LENS the game would drop it outside.
- Livestock trailers keep animals in the vehicle's own list (`BaseVehicle.animals`): `addAnimalFromHandsInTrailer`,
  `addAnimalInTrailer`, `removeAnimalFromTrailer` (out at the script area `AnimalEntry`). The list is saved with the
  vehicle, synced to clients, and every animal in it is updated each tick at the vehicle's position (`animal.update()`:
  it ages, gets hungry and thirsty, rides along). The animals are not drawn. In a vehicle they eat only from a part
  named `TrailerAnimalFood` and never drink.
- `AnimalData.eatItem(item, false)` eats a food item out of any container (removal, leftovers, the item it turns into,
  the multiplayer messages). Diets are the Lua definitions: `AnimalDefinitions.animals[type].eatTypeTrough`
  ("AnimalFeed,Grass,..." matched against the food type or the animal feed type; "All").
- Companion Dogs (Workshop 3740052292) treats an owner in any vehicle seat as "mounted": the following dog is stashed
  (despawned to a record, back beside the owner on exit) and a dog carried in is stashed out of the owner's arms.
  It supports dogs in a vehicle's animal list (trailers): it finds them, keeps them invincible and registered (no
  duplicate) and takes them out with `removeAnimalFromTrailer`. Its needs are the game's own hunger and thirst
  stats; its bowl (`Base.CompanionDogsBowl`) keeps food or water as a stock in the item's modData.
- `AnimatedModel` draws an animated character or animal model at a world point (`setCharacter(animal)` copies its
  visual; `setAnimSetName`, `setState`, `setVariable`, `setAngle`, `DoRenderToWorld`); mannequins are drawn that way
  through `SpriteRenderer.drawGeneric`.

## Design

1. **An animal inside lives in the vehicle's animal list**, as in a livestock trailer: saved, synced, simulated and
   carried along by the game, no physics or zombies inside the walls, and Companion Dogs already knows the place.
   Where it stands and what it does inside is in the vehicle's modData (`MELensAnimals[animal id]` = x, z, facing,
   pose), set on the server and sent with the vehicle's modData.
2. **Drop** a carried animal while inside (the menu's Drop, dragging it out): it is put down where you stand, into the
   list (`MELensDropAnimal`, done in `complete()` on the server). Room is limited by the animals' trailer sizes.
3. **Pick up**: right-click it inside (Pick up, Info): walk to it, `MELensPickUpAnimal` takes it out of the list into
   your arms the way the game's trailer Grab does.
4. **Drawn** by the Java part in the vehicle you are in: one `AnimatedModel` per animal, queued right after the
   vehicle's own draw (`IsoSprite.renderVehicle`; `BaseVehicle.render` is not called with the PZ Optimization
   renderer), in the vehicle's depth like the passengers (set after `AnimatedModel$WorldModelCamera.Begin`, which
   gives the model the depth of its own square), idle, walking, eating or lying (the animal's own anim set; a
   Companion dog eats and drinks with the dog mod's own animations). Its height is the game's own:
   `ModelSlotRenderData` draws a vehicle's local height y at `origin.y - 0.7 + y` model units and `Core.DoPushIsoStuff`
   a character model's feet at `level * 2.44949 - 0.72`.
5. **Food and water inside** (server, every game minute): a hungry animal eats what lies on the floor that its diet
   allows (or, for a Companion dog, what the dog mod allows); a thirsty one drinks from any unsealed container on the
   floor holding water, tainted water or a mix of the two (a pet water dish, a bowl, a pot, a bucket). Thirst comes
   first; a thirsty animal with nothing to drink still eats. A Companion Dogs bowl feeds only the dog mod's dogs, as
   outside, by the dog mod's rules (its sandbox restore, `CD.setNeed`, the vet's rolls for tainted water and food
   allergy, protein meals). It walks there first and plays its eating animation. Now and then it wanders to a free
   spot. On a server the changed item goes to the clients out of the container and back in with the same id (the game
   sends changed item fields only for a player's inventory or the ground, and a client ignores an item it already has).
6. **Companion Dogs**: while you stand or sit inside, the dog mod no longer counts you as mounted (no stash, no
   taking the dog out of your arms). Your following dog that comes up to the way in walks in; when you leave the
   vehicle your following dogs walk out with you; a dog told to stay stays inside. The vehicles get the script area
   `AnimalEntry` at the way in, which the game and the dog mod use to put an animal out.

## Not planned

- Animals walking about freely by their own AI inside (they move only as described above).
- Milking, shearing, petting, breeding and eggs inside (the game's actions need the animal in the world).
- Big animals (adult cows, sheep, pigs, deer): they cannot be carried, so they cannot be put inside.

## Historical status reported by the Animals project (2026-10-18)

Built and tested in the add-on's own test game (test profile `testhome4`, Lua port 18476, Flying Cloud 22) and on its
own local dedicated server (`dev/mp_server.ps1`, ports 17391/17392, server Lua 18479), one client.

Single player, checked:
- Drop a carried hen and dog inside (they land on free floor, not where you stand), pick them up again (menu option),
  save and reload (animals, places, bowls' stock kept).
- Drawn inside, from all four headings (`dev/headings.ps1`): on the floor, sorted behind furniture and in front of it
  like the player; walking, lying, the hen's and the dog's eating and drinking poses.
- Drinking from a water dish (0.25 l for 0.5 thirst), eating corn (eaten up: item and its floor place gone), nothing to
  drink: eats anyway; a hen ignores a dog bowl and a hammer; a dog drinks and eats from Companion Dogs bowls.
- Companion Dogs: a companion inside stays a companion (no stash, the dog mod sees it as in a vehicle); the owner
  leaves: it walks out beside them, still following, no duplicate; the owner walks in: it walks in; picked up inside
  and put down again; carried, it stays in the arms (no stash).

Multiplayer (dedicated server with ZombieBuddy, one client), checked:
- A hen the server spawned, picked up outside, carried in, put down: in the vehicle's list and record on the server
  and the client; picked up inside and put down again.
- Drinking from a dish and eating corn on the server: thirst, hunger, the dish's water and the eaten corn reach the
  client; a companion dog follows the owner in and out; the dog at its bowl by the dog mod's rules, the stock reaches
  the client.

Not tested, and why:
- Two players at once: 0.5 GB of RAM was free with one client and the server running.
- What a client draws inside in multiplayer: inside a camper the client showed a black world (the player outside saw
  the world). It stayed black with the add-on's drawing switched off, so it is not this add-on; single player inside
  draws. Left for Real Vehicle Interiors' own multiplayer work.
- A server without ZombieBuddy (`-NoJava`): the add-on's server part is Lua only, so it should not matter.

Merging into Real Vehicle Interiors: copy the Lua (it uses only the main mod's public functions and wraps four of
them), the translations and the Java classes (`me.lens.animals` into `me.lens.rv`, the Cutaway reflection becoming a
plain call), and coordinate with Codex, who works on the main mod at the same time.

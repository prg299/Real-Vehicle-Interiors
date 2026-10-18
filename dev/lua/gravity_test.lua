-- Developer test driver: a box with nothing under it falls (MELens.Parts.settleBox). In a box truck:
-- takes the bottom box of the first column away the way a save from an earlier layout would have it, with
-- the top box holding an item, runs the part's update and checks the top box and its item came down.
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a vehicle with a profile" end
local P = MELens.Parts
local out = {}
local function say(fmt, ...) out[#out + 1] = string.format(fmt, ...) end

local bottom, top = 1, 2
local pb, pt = P.spotPart(vehicle, bottom), P.spotPart(vehicle, top)
say("start: bottom=%s top=%s", tostring(P.pieceAt(pb)), tostring(P.pieceAt(pt)))
if not (P.pieceAt(pb) == "box" and P.pieceAt(pt) == "box") then return table.concat(out, "\n") .. "\nneeds both boxes standing" end

-- something in the top box
local marker = instanceItem("Base.Nails")
pt:getItemContainer():AddItem(marker)
-- the bottom box gone, as a save from an earlier layout can have it
local bottomItem = pb:getInventoryItem()
local held = pb:getItemContainer():getItems():size()
pb:setInventoryItem(nil)
P.applyPiece(vehicle, pb)
say("bottom taken (it held %d); supported(top)=%s (must be false)", held, tostring(P.supported(vehicle, profile, top)))

P.updateSpot(vehicle, pt, 1)
say("after the update: bottom=%s top=%s (must be box / nil)", tostring(P.pieceAt(pb)), tostring(P.pieceAt(pt)))
local into = pb:getItemContainer()
say("bottom holds the item: %s (must be true); top holds %d (must be 0)", tostring(into:contains(marker)),
    pt:getItemContainer() and pt:getItemContainer():getItems():size() or -1)
say("rules agree: supported(top)=%s placeTest(top)=%s", tostring(P.supported(vehicle, profile, top)),
    tostring(P.placeTest(vehicle, pt, player)))

-- tidy up: the item out, a box back on top
into:Remove(marker)
local item = instanceItem(P.itemType("box"))
pt:setInventoryItem(item)
P.applyPiece(vehicle, pt)
say("restored: bottom=%s top=%s", tostring(P.pieceAt(pb)), tostring(P.pieceAt(pt)))
return table.concat(out, "\n")

-- Developer test driver: placing furniture in the vehicle you are in, as from the
-- inventory's "Place furniture" (replace PIECE with a piece, e.g. "cabinet", and N with
-- which of the places it fits to preview). The preview stays on that place until the
-- mode stops (Escape, right-click, or MELens.Placement.active:stop()).
local player = getPlayer()
local P, L = MELens.Parts, MELens.Placement
if not L.canPlace(player) then return "not inside a vehicle you can furnish" end
local item = player:getInventory():AddItem(P.itemType("PIECE"))
if not item then return "no item for PIECE" end
L.start(player, item)
local mode = L.active
if not mode then return "placing did not start (no empty place fits PIECE?)" end
local place = mode.places[N] or mode.places[1]
mode.placeUnderMouse = function() return place end   -- the scripted mouse
mode:setHover(place)
local list = {}
for _, p in ipairs(mode.places) do
    table.insert(list, string.format("%d(%.2f..%.2f, %.2f..%.2f)", p.index, p.x0, p.x1, p.z0, p.z1))
end
return string.format("places %s; previewing spot %d", table.concat(list, " "), place.index)

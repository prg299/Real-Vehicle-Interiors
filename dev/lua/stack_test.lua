-- Developer test driver: the rules for stacked boxes in a box truck, without the timed actions: which boxes can
-- be picked up, where a box can go, and that the game agrees after boxes are taken off and put back. Works on
-- the first column of the truck, whatever its height (the truck's stacks differ: one to three boxes).
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a vehicle with a profile" end
local P, L = MELens.Parts, MELens.Placement
local out = {}
local function say(fmt, ...) out[#out + 1] = string.format(fmt, ...) end

-- the first column: its spots by level
local first = profile.spots[1]
local column = {}
for index, spot in ipairs(profile.spots) do
    if spot.level and spot.wall == first.wall and math.abs(spot.x - first.x) < 0.001 and math.abs(spot.z - first.z) < 0.001 then
        column[spot.level] = index
    end
end
local standing = {}
for level, index in ipairs(column) do
    if P.pieceAt(P.spotPart(vehicle, index)) then standing[#standing + 1] = level end
end
say("column: %d places, boxes standing at levels %s", #column, table.concat(standing, ","))
if #standing < 2 then return table.concat(out, "\n") .. "\nneeds a column with two boxes" end
local topLevel = standing[#standing]

-- (a box holding something cannot be picked up: this disposable truck's boxes are emptied first)
for _, level in ipairs(standing) do
    local container = P.spotPart(vehicle, column[level]):getItemContainer()
    if container then container:removeAllItems() end
end

-- only the top box can be picked up
for _, level in ipairs(standing) do
    local part = P.spotPart(vehicle, column[level])
    local allowed = P.pickUpTest(vehicle, part, player)
    say("pick up level %d allowed: %s (must be %s)", level, tostring(allowed), tostring(level == topLevel))
end

-- take the top box off the way the pick-up action does, then look at the rules
local topPart = P.spotPart(vehicle, column[topLevel])
local topItem = topPart:getInventoryItem()
topPart:setInventoryItem(nil)
P.applyPiece(vehicle, topPart)
local below = P.spotPart(vehicle, column[topLevel - 1])
say("top taken: the box below it can be picked up now: %s (must be true)", tostring(P.pickUpTest(vehicle, below, player)))
local places = L.placesFor(vehicle, profile, "box")
local found, only = false, true
for _, p in ipairs(places) do
    if p.index == column[topLevel] then found = true end
    local spot = profile.spots[p.index]
    if spot.level and spot.level > 1 and not P.supported(vehicle, profile, p.index) then only = false end
end
say("places for a box now: %d; the top's place is offered: %s; every offered stacked place is supported: %s",
    #places, tostring(found), tostring(only))

-- take everything but the bottom off, then the place above the bottom is offered; with the bottom gone too,
-- the places above it are not (nothing to rest on)
local taken = {}
for level = topLevel - 1, 1, -1 do
    local part = P.spotPart(vehicle, column[level])
    taken[#taken + 1] = { part = part, item = part:getInventoryItem() }
    part:setInventoryItem(nil)
    P.applyPiece(vehicle, part)
end
local offered = {}
for _, p in ipairs(L.placesFor(vehicle, profile, "box")) do offered[p.index] = true end
say("with the whole column gone: the bottom place is offered: %s (must be true); the one above it: %s (must be false)",
    tostring(offered[column[1]] or false), tostring(offered[column[2]] or false))

-- put everything back
for k = #taken, 1, -1 do
    taken[k].part:setInventoryItem(taken[k].item)
    P.applyPiece(vehicle, taken[k].part)
end
topPart:setInventoryItem(topItem)
P.applyPiece(vehicle, topPart)
local back = {}
for _, level in ipairs(standing) do back[#back + 1] = tostring(P.pieceAt(P.spotPart(vehicle, column[level]))) end
say("restored: %s", table.concat(back, " / "))
return table.concat(out, "\n")

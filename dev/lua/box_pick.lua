-- Developer test driver for picking up a box truck's boxes the way a player does (dev\boxes_test.ps1).
-- MODE is replaced by the caller:
--   empty   take everything out of every box (the Pick up option wants an empty box)
--   next    right-click the next box nobody stands on and nothing rests on (the one nearest the door first),
--           pointing the scripted mouse at a part of it that is in view, and choose Pick up
--   which   the index of the box `next` would right-click (nothing is clicked)
--   count   "<boxes standing> <boxes carried>"
local MODE = "MODE"
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a vehicle with a profile" end
local P, I = MELens.Parts, MELens.Interact
local offset = vehicle:getScript():getModel():getOffset()
local vec = Vector3f.new()
local base = vehicle:getWorldPos(0, 0, 0, Vector3f.new()):z()

local function screenOf(x, y, z)
    vehicle:getWorldPos(offset:x() + x, offset:y() + y, offset:z() + z, vec)
    return ISCoordConversion.ToScreen(vec:x(), vec:y(), base + (offset:y() + y) / 2.44949)
end

local function boxes()
    local list = {}
    for index, spot in ipairs(profile.spots) do
        if spot.cargo and P.pieceAt(P.spotPart(vehicle, index)) == "box" then list[#list + 1] = index end
    end
    return list
end

if MODE == "count" then
    return string.format("%d %d", #boxes(), player:getInventory():getCountTypeRecurse("MELensRV_Box"))
end

if MODE == "empty" then
    local n = 0
    for _, index in ipairs(boxes()) do
        local container = P.spotPart(vehicle, index):getItemContainer()
        if container then
            n = n + container:getItems():size()
            container:removeAllItems()
        end
    end
    return "emptied, items removed: " .. n
end

-- next: the points of a box to aim at, its top first and then its two faces toward the camera; the first one the
-- pick finds this box at is where the mouse goes
local function aimAt(index, spot)
    local _, depth, height = P.footprint(spot, "box")
    local top = profile.floorY + (spot.rise or 0) + height
    local tries = {}
    for _, a in ipairs({ 0, -0.15, 0.15 }) do
        for _, d in ipairs({ depth / 2, depth - 0.08, 0.08 }) do
            local x, z = P.spotPoint(spot, a, d)
            tries[#tries + 1] = { x, top - 0.01, z }
        end
    end
    for _, a in ipairs({ -0.24, 0.24 }) do
        for _, h in ipairs({ 0.3, 0.2, 0.1 }) do
            local x, z = P.spotPoint(spot, a, depth / 2)
            tries[#tries + 1] = { x, top - h, z }
        end
    end
    for _, h in ipairs({ 0.3, 0.2, 0.1 }) do
        local x, z = P.spotPoint(spot, 0, depth - 0.005)
        tries[#tries + 1] = { x, top - h, z }
    end
    for _, t in ipairs(tries) do
        local sx, sy = screenOf(t[1], t[2], t[3])
        local hit = I.pick(vehicle, profile, sx, sy)
        if hit and hit.index == index then return sx, sy end
    end
    return nil
end

local door = profile.door
local candidates = {}
for _, index in ipairs(boxes()) do
    if not P.covered(vehicle, profile, index) then
        local spot = profile.spots[index]
        candidates[#candidates + 1] = { index = index, d = (spot.x - door.x) ^ 2 + (spot.z - door.z) ^ 2 + (spot.level or 1) * 0.001 }
    end
end
table.sort(candidates, function(a, b) return a.d < b.d end)
if #candidates == 0 then return "none left" end
local unseen = {}
for _, c in ipairs(candidates) do
    local spot = profile.spots[c.index]
    local sx, sy = aimAt(c.index, spot)
    if sx and MODE == "which" then
        return tostring(c.index)
    end
    if sx then
        I.testMouse = { x = sx, y = sy }
        local context = ISContextMenu.get(0, 100, 100)
        I.fillMenu(player, context)
        I.testMouse = nil
        local chosen
        for _, option in ipairs(context.options or {}) do
            local sub = option.subOption and context:getSubMenu(option.subOption)
            for _, o in ipairs(sub and sub.options or {}) do
                if o.name == getText("ContextMenu_MELens_PickUp") then chosen = o end
            end
        end
        context:setVisible(false)
        if not chosen then return string.format("box %d: no Pick up option", c.index) end
        if chosen.notAvailable then
            return string.format("box %d: Pick up is off: %s", c.index, chosen.toolTip and chosen.toolTip.description or "")
        end
        chosen.onSelect(chosen.target, chosen.param1, chosen.param2)
        return string.format("picking %d (L%d)%s", c.index, spot.level or 0, #unseen > 0 and (", not in view: " .. table.concat(unseen, ",")) or "")
    end
    unseen[#unseen + 1] = tostring(c.index)
end
return "no box in view: " .. table.concat(unseen, ",")

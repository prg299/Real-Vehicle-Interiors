-- Developer test driver: open the right-click menu of the camper you are in as if the
-- mouse were over a piece of furniture (replace TARGET with a spot number, "panel" or
-- "floor"), and show it at the middle of the screen.
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a camper" end
local P = MELens.Parts
local target = "TARGET"
local offset = vehicle:getScript():getModel():getOffset()
local vec = Vector3f.new()
local base = vehicle:getWorldPos(0, 0, 0, Vector3f.new()):z()

local function screenOf(x, y, z)
    vehicle:getWorldPos(offset:x() + x, offset:y() + y, offset:z() + z, vec)
    return ISCoordConversion.ToScreen(vec:x(), vec:y(), base + (offset:y() + y) / 2.44949)
end

local sx, sy
if target == "panel" then
    local p = profile.panel
    sx, sy = screenOf(p.x, p.y, p.z)
elseif target == "floor" then
    sx, sy = screenOf(0, profile.floorY, 1.0)
else
    local index = tonumber(target)
    local spot = profile.spots[index]
    local part = P.spotPart(vehicle, index)
    local length, depth, height = P.footprint(spot, P.pieceAt(part))
    local x, z = P.spotPoint(spot, 0, depth / 2)
    sx, sy = screenOf(x, profile.floorY + height, z)
end
MELens.Interact.testMouse = { x = sx, y = sy }
local context = ISContextMenu.get(0, getCore():getScreenWidth() / 2, getCore():getScreenHeight() / 2)
MELens.Interact.fillMenu(player, context)
MELens.Interact.testMouse = nil
context:setVisible(true)
local names = {}
for _, option in ipairs(context.options or {}) do
    local text = option.name
    if option.subOption then
        local sub = context:getSubMenu(option.subOption)
        local inner = {}
        for _, o in ipairs(sub and sub.options or {}) do
            inner[#inner + 1] = o.name .. (o.notAvailable and " (off)" or "")
        end
        text = text .. " > [" .. table.concat(inner, "; ") .. "]"
    end
    names[#names + 1] = text
end
return table.concat(names, " | ")

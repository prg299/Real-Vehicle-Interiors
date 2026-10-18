-- Developer test driver: pick an option from the right-click menu of a piece of
-- furniture in the camper you are in, as if you had clicked it (replace TARGET with a
-- spot number, "panel", "floor" or "driver", and OPTION with the option's text, e.g. "Rest").
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a camper" end
local P = MELens.Parts
local target = "TARGET"
local wanted = "OPTION"
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
elseif target == "driver" then
    local d = profile.driver
    sx, sy = screenOf((d.x1 + d.x2) / 2, profile.floorY + 0.4, (d.z1 + d.z2) / 2)
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

local function find(menu)
    for _, option in ipairs(menu.options or {}) do
        if option.name == wanted then return option end
        if option.subOption then
            local found = find(menu:getSubMenu(option.subOption))
            if found then return found end
        end
    end
end
local option = find(context)
context:hideAndChildren()
if not option then return "no option " .. wanted end
if option.notAvailable then return "option " .. wanted .. " is disabled" end
option.onSelect(option.target, option.param1, option.param2, option.param3, option.param4,
    option.param5, option.param6, option.param7, option.param8, option.param9, option.param10)
return "picked " .. wanted

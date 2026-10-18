-- Developer test driver: placing, dropping and grabbing loose items in the vehicle you are in.
-- Replace MODE (and ARG) before sending:
--   give  ARG = item types "Base.Hammer,Base.Pot"   add them to your inventory
--   start ARG = a type "Hammer"                       the Place mode with that item (as the inventory menu's Place)
--   at    ARG = "x,y,z"                               the mode's mouse is over that passenger-space point
--   hover                                             what the mode shows now (surface, place, fits)
--   yaw   ARG = degrees                               turn the item in the mode
--   commit                                            click (walks there and sets it down)
--   list                                              everything that lies in the vehicle
--   drop  ARG = a type                                the inventory menu's Drop
--   menu  ARG = "x,y,z" or "x,y,z|Option"             the right-click menu at that point (or pick the option)
--   clear                                             empty the floor and forget all positions
local mode, arg = "MODE", "ARG"
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a camper" end
local UI, L, P = MELens.LooseUI, MELens.Loose, MELens.Parts
local offset = vehicle:getScript():getModel():getOffset()
local vec = Vector3f.new()
local base = vehicle:getWorldPos(0, 0, 0, Vector3f.new()):z()

local function screenOf(x, y, z)
    vehicle:getWorldPos(offset:x() + x, offset:y() + y, offset:z() + z, vec)
    return ISCoordConversion.ToScreen(vec:x(), vec:y(), base + (offset:y() + y) / 2.44949)
end

local function point(text)
    local x, y, z = string.match(text, "([^,|]+),([^,|]+),([^,|]+)")
    return tonumber(x), tonumber(y), tonumber(z)
end

if mode == "give" then
    local out = {}
    for t in string.gmatch(arg, "[^,]+") do
        local item = player:getInventory():AddItem(t)
        out[#out + 1] = t .. "=" .. tostring(item ~= nil)
    end
    return out
elseif mode == "start" then
    local item = player:getInventory():getFirstTypeRecurse(arg)
    if not item then return "no " .. arg end
    UI.testMouse = nil
    UI.start(player, { item })
    return UI.active and "mode on" or "no mode"
elseif mode == "at" then
    local x, y, z = point(arg)
    local sx, sy = screenOf(x, y, z)
    UI.testMouse = { x = sx, y = sy }
    return { sx, sy }
elseif mode == "hover" then
    local m = UI.active
    if not m then return "no mode" end
    local h = m.hover
    if not h then return "no hover (yaw " .. m.yaw .. ")" end
    return string.format("%s s=%d at %.3f,%.3f,%.3f valid=%s reason=%s yaw=%d", h.surface.kind, h.surface.s, h.x, h.y, h.z,
        tostring(h.valid), tostring(h.reason), m.yaw)
elseif mode == "yaw" then
    UI.active.yaw = tonumber(arg)
    return UI.active.yaw
elseif mode == "commit" then
    UI.active:commit()
    return "committed, queued " .. #ISTimedActionQueue.getTimedActionQueue(player).queue .. ", pathing " .. tostring(MELens.pathing(player))
elseif mode == "place" then
    -- ARG = "Type|x,y,z,yaw,s": set the item down there without the mouse (the walk and the action, as the mode queues them)
    local t, rest = string.match(arg, "([^|]+)|(.+)")
    local x, y, z, yaw, s = string.match(rest, "([^,]+),([^,]+),([^,]+),([^,]+),([^,]+)")
    x, y, z, yaw, s = tonumber(x), tonumber(y), tonumber(z), tonumber(yaw), tonumber(s)
    local item = player:getInventory():getFirstTypeRecurse(t)
    if not item then return "no " .. t end
    local sx, sz = UI.standFor(vehicle, profile, x, z, s, player)
    MELens.standingThen(player, function()
        MELens.walkTo(player, sx, sz, function()
            ISTimedActionQueue.add(MELensPlaceLoose:new(player, vehicle, item, x, y, z, yaw, s))
        end)
    end)
    return "walking to " .. sx .. "," .. sz
elseif mode == "list" then
    local out = {}
    for _, e in ipairs(L.list(vehicle, profile)) do
        out[#out + 1] = string.format("%d %s x=%.2f y=%.2f z=%.2f r=%d s=%d%s", e.id, e.t, e.x, e.y, e.z, e.r, e.s, e.orphan and " orphan" or "")
    end
    out[#out + 1] = "java: " .. MELensRV.looseStatus()
    return out
elseif mode == "drop" then
    local item = player:getInventory():getFirstTypeRecurse(arg)
    if not item then return "no " .. arg end
    ISInventoryPaneContextMenu.dropItem(item, 0)
    return "queued " .. #ISTimedActionQueue.getTimedActionQueue(player).queue
elseif mode == "menu" then
    local where, wanted = string.match(arg, "([^|]+)|?(.*)")
    local x, y, z = point(where)
    local sx, sy = screenOf(x, y, z)
    MELens.Interact.testMouse = { x = sx, y = sy }
    local context = ISContextMenu.get(0, getCore():getScreenWidth() / 2, getCore():getScreenHeight() / 2)
    MELens.Interact.fillMenu(player, context)
    MELens.Interact.testMouse = nil
    local names = {}
    local function walk(menu, prefix)
        for _, option in ipairs(menu.options or {}) do
            names[#names + 1] = prefix .. option.name .. (option.notAvailable and " (off)" or "")
            if option.subOption then walk(menu:getSubMenu(option.subOption), prefix .. "  ") end
        end
    end
    walk(context, "")
    local chosen
    if wanted ~= "" then
        local function find(menu)
            for _, option in ipairs(menu.options or {}) do
                if option.name == wanted then return option end
                if option.subOption then
                    local found = find(menu:getSubMenu(option.subOption))
                    if found then return found end
                end
            end
        end
        chosen = find(context)
        if chosen and not chosen.notAvailable then
            chosen.onSelect(chosen.target, chosen.param1, chosen.param2, chosen.param3, chosen.param4,
                chosen.param5, chosen.param6, chosen.param7, chosen.param8, chosen.param9, chosen.param10)
        end
        names[#names + 1] = chosen and (chosen.notAvailable and "option is off" or "picked " .. wanted) or ("no option " .. wanted)
    end
    context:hideAndChildren()
    return names
elseif mode == "clear" then
    local floor = L.floorContainer(vehicle)
    if floor then floor:clear() end
    local part = L.floorPart(vehicle)
    if part then part:getModData()[L.KEY] = nil end
    return "cleared"
end
return "unknown mode " .. mode

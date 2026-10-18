-- Developer test driver: dropping inside a walk-in vehicle. Adds test items, builds the
-- inventory context menu for one of them and reports whether "Drop" is available, then
-- drops it the way the menu does (MODE = "drop") or reports where things are (MODE = "where").
local player = getPlayer()
local vehicle = player:getVehicle()
if not vehicle then return "not in a vehicle" end
local mode = "MODE"
local floor = MELens.floorContainer(vehicle)

local function count(container, type)
    local n = 0
    local items = container:getItems()
    for i = 0, items:size() - 1 do
        if items:get(i):getType() == type then n = n + 1 end
    end
    return n
end

local function worldItemsNear()
    -- everything lying on the ground within 4 tiles of the vehicle (outside), by type
    local found = {}
    local cx, cy = math.floor(vehicle:getX()), math.floor(vehicle:getY())
    for x = cx - 6, cx + 6 do
        for y = cy - 6, cy + 6 do
            local sq = getCell():getGridSquare(x, y, 0)
            if sq then
                local objs = sq:getWorldObjects()
                for i = 0, objs:size() - 1 do
                    local o = objs:get(i)
                    found[#found + 1] = o:getItem():getType() .. "@" .. x .. "," .. y
                end
            end
        end
    end
    return found
end

if mode == "drop" then
    local inv = player:getInventory()
    local item = inv:AddItem("Base.Hammer")
    inv:AddItem("Base.Nails")
    MELensTest.dropped = item
    -- is Drop available in the menu the player would get?
    local ok, menu = pcall(function()
        return ISInventoryPaneContextMenu.createMenu(0, true, { item }, getCore():getScreenWidth() / 2, getCore():getScreenHeight() / 2)
    end)
    local dropState = "no menu (" .. tostring(menu) .. ")"
    if ok and menu then
        dropState = "Drop option missing"
        for _, option in ipairs(menu.options or {}) do
            if option.name == getText("ContextMenu_Drop") then
                dropState = "Drop " .. (option.notAvailable and "GREYED" or "available")
            end
        end
        menu:setVisible(false)
    end
    ISInventoryPaneContextMenu.dropItem(item, 0)
    return dropState .. "; queued the drop; floor has hammers=" .. count(floor, "Hammer")
end

return string.format("floor hammers=%d, inventory hammers=%d, on the ground nearby: [%s]",
    count(floor, "Hammer"), count(player:getInventory(), "Hammer"), table.concat(worldItemsNear(), " "))

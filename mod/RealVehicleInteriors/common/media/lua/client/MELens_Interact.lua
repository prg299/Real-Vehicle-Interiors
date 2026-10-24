--
-- ME: LENS: using the inside of a camper like any other room. Right-click a piece of
-- furniture for what it does (sleep or rest on a bed, rest at the dinette, drink, fill
-- and wash at the kitchen, the stove and heater switches), right-click the utility
-- panel by the door for the lights and the camper's dashboard, and place or pick up
-- furniture. Storage shows in the loot window when you stand at it.
--
require "MELens_Parts"
require "MELens_Utilities"
require "TimedActions/MELens_Actions"
require "Definitions/ContainerButtonIcons"

MELens = MELens or {}
local M = MELens
M.Interact = M.Interact or {}
local I = M.Interact
local P = M.Parts
local U = M.Utilities

local HEIGHT_STEP = 0.02      -- tiles between the heights tested along the mouse ray
local STAND_OFF = 0.17        -- tiles in front of a piece where you stand to use it
local Z_LEVEL = 2.44949       -- a floor level in the game's 3D units (tiles)

local function java()
    return MELensRV
end

------------------------------------------------------------------------------------
-- What is under the mouse
------------------------------------------------------------------------------------

local vecA, vecB = nil, nil

-- The camper's passenger-space point (x, z) under screen point (sx, sy) at height h.
local function screenToCamper(vehicle, sx, sy, h)
    vecA = vecA or Vector3f.new()
    vecB = vecB or Vector3f.new()
    local offset = vehicle:getScript():getModel():getOffset()
    local base = vehicle:getWorldPos(0, 0, 0, vecA):z()
    local level = base + (offset:y() + h) / Z_LEVEL
    local wx, wy = ISCoordConversion.ToWorld(sx, sy, level)
    local l = vehicle:getLocalPos(wx, wy, level, vecB)
    return l:x() - offset:x(), l:z() - offset:z()
end

-- Walks down the mouse ray from above the tallest furniture to the floor and returns
-- the first thing it meets (the one you see): { kind = "piece" | "spot" | "panel", ... }.
function I.pick(vehicle, profile, sx, sy)
    local candidates = {}
    -- what lies there comes first: it stands on what is below it
    if M.LooseUI then
        for _, c in ipairs(M.LooseUI.pickCandidates(vehicle, profile)) do
            table.insert(candidates, c)
        end
    end
    for index, spot in ipairs(profile.spots or {}) do
        local part = P.spotPart(vehicle, index)
        local piece = part and P.pieceAt(part)
        -- an empty place higher up a stack is placed through the inventory (Place furniture)
        if part and (piece or (spot.level or 1) == 1) then
            local length, depth, height = P.footprint(spot, piece)
            local base = profile.floorY + (spot.rise or 0)
            table.insert(candidates, {
                kind = piece and "piece" or "spot", index = index, part = part, spot = spot, piece = piece,
                length = length, depth = depth, bottom = base, top = base + height,
            })
        end
    end
    -- The utility panel first: it is small and low on the wall, so tall furniture in
    -- front of it must not hide it from the mouse.
    local panel = profile.panel
    if panel then
        local h = panel.y + panel.halfY
        while h >= panel.y - panel.halfY do
            local x, z = screenToCamper(vehicle, sx, sy, h)
            if math.abs(x - panel.x) <= panel.halfX + 0.05 and math.abs(z - panel.z) <= panel.halfZ + 0.02 then
                return { kind = "panel", x = x, z = z }
            end
            h = h - HEIGHT_STEP / 2
        end
    end
    -- The vehicle's own driver's seat (a bus): from its top down to the floor.
    local driver = profile.driver
    if driver then
        local h = profile.floorY + 0.75
        while h >= profile.floorY do
            local x, z = screenToCamper(vehicle, sx, sy, h)
            if x >= driver.x1 and x <= driver.x2 and z >= driver.z1 and z <= driver.z2 then
                return { kind = "driver", x = x, z = z }
            end
            h = h - HEIGHT_STEP * 2
        end
    end
    -- Start above every candidate, including upper boxes and items on their tops.
    local h = profile.floorY + 1.5
    for _, c in ipairs(candidates) do h = math.max(h, c.top + HEIGHT_STEP) end
    while h >= profile.floorY - 0.001 do
        local x, z = screenToCamper(vehicle, sx, sy, h)
        for _, c in ipairs(candidates) do
            if h <= c.top and h >= c.bottom - 0.001 then
                if c.hits then
                    if c.hits(x, z) then
                        c.x, c.z = x, z
                        return c
                    end
                else
                    local a, d = P.toSpot(c.spot, x, z)
                    if math.abs(a) <= c.length / 2 and d >= 0 and d <= c.depth then
                        c.a, c.x, c.z = a, x, z
                        return c
                    end
                end
            end
        end
        h = h - HEIGHT_STEP
    end
    return nil
end

------------------------------------------------------------------------------------
-- Helpers
------------------------------------------------------------------------------------

local function say(player, key, ...)
    HaloTextHelper.addBadText(player, getText(key, ...))
end

local function addTip(option, text)
    local tip = ISWorldObjectContextMenu.addToolTip()
    tip.description = text
    option.toolTip = tip
    return option
end

local function disabled(option, reason)
    option.notAvailable = true
    if reason then addTip(option, getText(reason)) end
    return option
end

-- A spot as seen from the aisle: where to stand to use it at `a` along its length.
local function standPoint(spot, piece, a)
    local length, depth = P.footprint(spot, piece)
    a = math.max(-length / 2 + 0.1, math.min(length / 2 - 0.1, a or 0))
    return P.spotPoint(spot, a, depth + STAND_OFF)
end

I.screenToCamper = screenToCamper
I.standPoint = standPoint

-- Where to stand to use a piece at `a` along it: in front of that place, or, when furniture
-- beside it leaves no room there, the nearest open place along its front.
local function openStandPoint(vehicle, spot, piece, a, player)
    player = player or getSpecificPlayer(0)
    if player and player:getVehicle() == vehicle and M.isStanding(player) then
        local px, pz = P.characterAt(vehicle, player)
        if px and P.distanceTo(spot, piece, px, pz) <= P.REACH then
            return px, pz
        end
    end
    local x, z = standPoint(spot, piece, a)
    local profile = M.profileFor(vehicle)
    if not profile or M.walkableAt(profile, x, z) then
        return x, z
    end
    local length = P.footprint(spot, piece)
    for step = 1, math.ceil(length / 0.04) do
        for _, sign in ipairs({ 1, -1 }) do
            local sx, sz = standPoint(spot, piece, (a or 0) + sign * step * 0.04)
            if M.walkableAt(profile, sx, sz) then
                return sx, sz
            end
        end
    end
    return x, z
end

I.openStandPoint = openStandPoint

-- Walk to a piece, then do something. Seated or lying, you get up first.
local function atPiece(player, hit, fn)
    local x, z = openStandPoint(player:getVehicle(), hit.spot, hit.piece, hit.a, player)
    M.standingThen(player, function()
        M.walkTo(player, x, z, function()
            fn()
        end)
    end)
end

local function queue(player, action)
    ISTimedActionQueue.add(action)
end

local function itemIcon(item)
    return item and item:getTex() or nil
end

-- The free seat of a piece nearest to (x, z), and where to stand for it (only the seats
-- the piece standing there has: one on a bed, two on a dinette or a pair of bus seats).
local function freeSeat(vehicle, hit, x, z)
    local profile = M.profileFor(vehicle)
    local best, bestD, bx, bz
    for _, id in ipairs(hit.spot.seats or {}) do
        local index, sx, sz = P.seatPoint(vehicle, profile, id)
        if index and P.seatPose(vehicle, profile, id) and vehicle:isSeatInstalled(index) and not vehicle:getCharacter(index) then
            local d = (sx - x) ^ 2 + (sz - z) ^ 2
            if not bestD or d < bestD then
                best, bestD, bx, bz = id, d, sx, sz
            end
        end
    end
    if not best then return nil end
    local a = P.toSpot(hit.spot, bx, bz)
    return best, openStandPoint(vehicle, hit.spot, hit.piece, a)
end

------------------------------------------------------------------------------------
-- Furniture menus
------------------------------------------------------------------------------------

local function useSeatOptions(player, vehicle, hit, sub)
    local kind = P.kit(hit.piece).kind
    local seatId, sx, sz = freeSeat(vehicle, hit, hit.x or 0, hit.z or 0)
    local current = vehicle:getSeat(player)
    local onThis = false
    for _, id in ipairs(hit.spot.seats or {}) do
        if vehicle:getScript():getPassengerIndex(id) == current then onThis = true end
    end
    if kind == "bed" then
        local blocked = M.sleepBlocker(player, vehicle)
        local option
        if onThis then
            option = sub:addOption(getText("ContextMenu_Sleep"), player, ISVehicleMenu.onSleep, vehicle)
        elseif seatId then
            option = sub:addOption(getText("ContextMenu_Sleep"), player, M.useSeat, seatId, sx, sz, true)
        else
            option = disabled(sub:addOption(getText("ContextMenu_Sleep")), "IGUI_PlayerText_VehicleSomeoneInSeat")
        end
        if blocked and not option.notAvailable then
            disabled(option, blocked)
        end
    end
    if not onThis then
        if seatId then
            sub:addOption(getText("ContextMenu_Rest"), player, M.useSeat, seatId, sx, sz, false)
        else
            disabled(sub:addOption(getText("ContextMenu_Rest")), "IGUI_PlayerText_VehicleSomeoneInSeat")
        end
    end
end

-- Containers that can take water from the tap (like filling at a sink).
local function fillables(player)
    local list = {}
    local items = player:getInventory():getItems()
    for i = 0, items:size() - 1 do
        local item = items:get(i)
        local fc = item:getFluidContainer()
        if fc and not fc:isFull() and fc:canAddFluid(Fluid.Water) and (fc:isEmpty() or fc:isPureFluid(Fluid.Water) or fc:isPureFluid(Fluid.TaintedWater)) then
            table.insert(list, item)
        end
    end
    return list
end

-- Clothing, bags and items the game's washing action can clean.
local function washables(player)
    local list = {}
    local found = player:getInventory():getAllEvalRecurse(MELensWashClothing.canWash)
    for i = 0, found:size() - 1 do
        table.insert(list, found:get(i))
    end
    return list
end

-- Washes the items one after the other at the tap, with the camper's water and your soap (the game's rules:
-- blood needs soap, dirt only water).
local function washItems(player, vehicle, hit, items)
    local soaps = player:getInventory():getSoapList(nil, true)
    local soapLeft = ISWashClothing.GetSoapRemaining(soaps)
    atPiece(player, hit, function()
        for _, item in ipairs(items) do
            local noSoap = true
            local needed = ISWashClothing.GetRequiredSoap(item)
            if soapLeft > 0 then
                noSoap = false
                soapLeft = soapLeft - math.min(soapLeft, needed)
            end
            local blood, dirt = 0, 0
            if instanceof(item, "Clothing") or instanceof(item, "InventoryContainer") then
                local parts = BloodClothingType.getCoveredParts(item:getBloodClothingType())
                for j = 0, (parts and parts:size() or 0) - 1 do
                    blood = blood + item:getBlood(parts:get(j))
                end
                dirt = item:getDirtiness() or 0
            else
                blood = item:getBloodLevel()
            end
            ISWorldObjectContextMenu.transferIfNeeded(player, item)
            queue(player, MELensWashClothing:new(player, vehicle, item, blood, dirt, noSoap))
        end
    end)
end

local function tapOptions(player, vehicle, hit, sub)
    local water = U.waterState(vehicle)
    local empty = not water or water.water <= 0
    local drink = sub:addOption(getText("ContextMenu_Drink"), player, function()
        atPiece(player, hit, function() queue(player, MELensDrinkFromTank:new(player, vehicle)) end)
    end)
    if empty then
        disabled(drink, "IGUI_MELens_TankEmpty")
    elseif player:getStats():get(CharacterStat.THIRST) <= 0.01 then
        disabled(drink, "IGUI_MELens_NotThirsty")
    end
    local containers = fillables(player)
    local fillOption = sub:addOption(getText("ContextMenu_Fill"))
    if empty then
        disabled(fillOption, "IGUI_MELens_TankEmpty")
    elseif #containers == 0 then
        disabled(fillOption, "IGUI_MELens_NothingToFill")
    else
        local fillSub = ISContextMenu:getNew(sub)
        sub:addSubMenu(fillOption, fillSub)
        for _, item in ipairs(containers) do
            local option = fillSub:addOption(item:getDisplayName(), player, function()
                atPiece(player, hit, function() queue(player, MELensFillFromTank:new(player, vehicle, item)) end)
            end)
            option.iconTexture = itemIcon(item)
        end
    end
    local wash = sub:addOption(getText("ContextMenu_MELens_WashYourself"), player, function()
        atPiece(player, hit, function() queue(player, MELensWashFromTank:new(player, vehicle)) end)
    end)
    if not water or water.water < MELensWashFromTank.WATER_PER_PART then
        disabled(wash, "IGUI_MELens_TankEmpty")
    elseif ISWashYourself.GetRequiredWater(player) <= 0 then
        disabled(wash, "IGUI_MELens_AlreadyClean")
    end
    if water and water.tainted and not empty then
        addTip(drink, getText("IGUI_MELens_TankTainted"))
    end
    -- clothes, bags and bandages
    local dirty = washables(player)
    local washOption = sub:addOption(getText("ContextMenu_MELens_WashClothes"))
    if empty then
        disabled(washOption, "IGUI_MELens_TankEmpty")
    elseif #dirty == 0 then
        disabled(washOption, "IGUI_MELens_NothingToWash")
    else
        local washSub = ISContextMenu:getNew(sub)
        sub:addSubMenu(washOption, washSub)
        if #dirty > 1 then
            washSub:addOption(getText("ContextMenu_MELens_WashAll"), player, function()
                washItems(player, vehicle, hit, dirty)
            end)
        end
        for _, item in ipairs(dirty) do
            local option = washSub:addOption(item:getDisplayName(), player, function()
                washItems(player, vehicle, hit, { item })
            end)
            option.iconTexture = itemIcon(item)
            local need = ISWashClothing.GetRequiredWater(item)
            if water.water < need then
                addTip(option, getText("IGUI_MELens_NeedWaterAmount", string.format("%d", need)))
                option.notAvailable = true
            end
        end
    end
end

local function switchOption(player, vehicle, hit, sub, which, label)
    local on = U.isOn(vehicle, which)
    local text = getText(on and "ContextMenu_Turn_Off" or "ContextMenu_Turn_On")
    if label then text = getText(label, text) end
    local option = sub:addOption(text, player, function()
        atPiece(player, hit, function() queue(player, MELensSwitch:new(player, vehicle, which, not on)) end)
    end)
    if not on and not U.canBurn(vehicle) then
        if U.propaneOn() then
            disabled(option, "IGUI_MELens_NoPropane")
        else
            addTip(option, getText("IGUI_MELens_NeedsPower"))
        end
    end
    return option
end

-- "Insert Propane Tank" at the stove and the heater, when you carry one.
local function propaneOption(player, vehicle, hit, sub)
    if not U.propaneOn() then return end
    local tank = player:getInventory():getFirstEvalRecurse(function(item) return P.propaneIn(item) > 0 end)
    local option = sub:addOption(getText("ContextMenu_Insert_Propane_Tank"), player, function()
        ISWorldObjectContextMenu.transferIfNeeded(player, tank)
        atPiece(player, hit, function() queue(player, MELensInsertPropane:new(player, vehicle, tank)) end)
    end)
    if not tank then
        disabled(option, "IGUI_BBQ_NeedsPropaneTank")
    elseif U.propaneLevel(vehicle) >= U.PROPANE_CAPACITY - 0.001 then
        disabled(option, "IGUI_MELens_PropaneFull")
    end
end

local function pickUpOption(player, vehicle, hit, sub)
    local option = sub:addOption(getText("ContextMenu_MELens_PickUp"), player, function()
        atPiece(player, hit, function() queue(player, MELensPickUpFurniture:new(player, vehicle, hit.part)) end)
    end)
    local container = hit.part:getItemContainer()
    local profile = M.profileFor(vehicle)
    if container and not container:isEmpty() then
        disabled(option, "IGUI_MELens_EmptyItFirst")
    elseif P.seatTaken(vehicle, hit.part) then
        disabled(option, "IGUI_PlayerText_VehicleSomeoneInSeat")
    elseif profile and P.covered(vehicle, profile, hit.index) then
        disabled(option, "IGUI_MELens_TakeTopFirst")
    elseif M.Loose and M.Loose.itemsOn(vehicle, hit.index) then
        disabled(option, "IGUI_MELens_ClearTopFirst")
    end
end

local function pieceMenu(player, vehicle, hit, context)
    local item = hit.part:getInventoryItem()
    local header = context:addOptionOnTop(item and item:getDisplayName() or getText("IGUI_MELens_Furniture"))
    header.iconTexture = itemIcon(item)
    local sub = ISContextMenu:getNew(context)
    context:addSubMenu(header, sub)
    local kind = P.kit(hit.piece).kind
    if kind == "bed" or kind == "seat" then
        useSeatOptions(player, vehicle, hit, sub)
    end
    if hit.piece == "kitchen" or hit.piece == "washroom" then
        tapOptions(player, vehicle, hit, sub)
    end
    if hit.piece == "kitchen" then
        switchOption(player, vehicle, hit, sub, "stove", "ContextMenu_MELens_Stove")
        propaneOption(player, vehicle, hit, sub)
    elseif hit.piece == "heater" then
        switchOption(player, vehicle, hit, sub, "heater")
        propaneOption(player, vehicle, hit, sub)
    elseif hit.piece == "fridge" then
        disabled(sub:addOption(getText(U.hasPower(vehicle) and "IGUI_MELens_FridgeCold" or "IGUI_MELens_FridgeNoPower")))
    end
    pickUpOption(player, vehicle, hit, sub)
end

-- Furniture items you carry that fit this spot, and have room there beside what stands
-- in its neighbours' places.
local function placeables(player, vehicle, hit)
    local list, seen = {}, {}
    local profile = M.profileFor(vehicle)
    local index = P.spotIndex(hit.part)
    local standing = profile and index and P.standing(vehicle, profile)
    local items = player:getInventory():getItems()
    for i = 0, items:size() - 1 do
        local item = items:get(i)
        local piece = P.pieceOfItem(item)
        if piece and not seen[piece] and P.fits(hit.spot, piece)
                and (not standing or P.roomFor(profile, standing, index, piece)) then
            seen[piece] = true
            table.insert(list, item)
        end
    end
    return list
end

local function spotMenu(player, vehicle, hit, context)
    local items = placeables(player, vehicle, hit)
    if #items == 0 then return end
    local header = context:addOptionOnTop(getText("ContextMenu_MELens_PlaceFurniture"))
    local sub = ISContextMenu:getNew(context)
    context:addSubMenu(header, sub)
    for _, item in ipairs(items) do
        local option = sub:addOption(item:getDisplayName(), player, function()
            atPiece(player, hit, function() queue(player, MELensPlaceFurniture:new(player, vehicle, hit.part, item)) end)
        end)
        option.iconTexture = itemIcon(item)
    end
end

local function panelMenu(player, vehicle, profile, context)
    local header = context:addOptionOnTop(getText("IGUI_MELens_UtilityPanel"))
    header.iconTexture = getTexture("Item_LightBulb")
    local sub = ISContextMenu:getNew(context)
    context:addSubMenu(header, sub)
    local p = profile.panel
    local near = function(fn)
        M.standingThen(player, function()
            M.walkTo(player, p.x + 0.25, p.z, fn)
        end)
    end
    local on = M.lightsSwitchedOn(vehicle)
    local lights = sub:addOption(getText(on and "ContextMenu_Turn_Off" or "ContextMenu_Turn_On"), player, function()
        near(function() queue(player, MELensSwitch:new(player, vehicle, "lights", not on)) end)
    end)
    lights.iconTexture = getTexture("Item_LightBulb")
    local battery = vehicle:getBattery()
    if not on and not (battery and battery:getInventoryItem()) then
        addTip(lights, getText("IGUI_MELens_NoBattery"))
    elseif not on and M.batteryCharge(vehicle) <= 0 then
        addTip(lights, getText("IGUI_MELens_BatteryEmpty"))
    end
    sub:addOption(getText("ContextMenu_MELens_Dashboard"), player, function()
        near(function() M.Dashboard.open(player, vehicle) end)
    end)
end

-- The camper's dashboard (the camper manager): always in the menu inside a camper, and
-- outside next to one (see MELens_Cabin.lua).
function I.addDashboardOption(player, vehicle, context)
    local option = context:addOptionOnTop(getText("ContextMenu_MELens_Dashboard"), player, function()
        M.Dashboard.open(player, vehicle)
    end)
    option.iconTexture = getTexture("Item_Generator")
    return option
end

-- The vehicle's own driver's seat: drive from inside (a bus).
local function driverMenu(player, vehicle, profile, context)
    local driver = profile.driver
    local seat = M.seatIndex(vehicle, driver.seat)
    local option = context:addOptionOnTop(getText("ContextMenu_MELens_Drive"), player, function()
        local x, z = M.driverStandPoint(profile)
        M.useSeat(player, driver.seat, x, z, false)
    end)
    option.iconTexture = getTexture("media/ui/vehicles/vehicle_changeseats.png")
    if seat < 0 or vehicle:getCharacter(seat) then
        disabled(option, "IGUI_PlayerText_VehicleSomeoneInSeat")
    end
end

-- Adds the options for what is under the mouse, and the dashboard.
function I.fillMenu(player, context)
    local vehicle = player:getVehicle()
    local profile = M.profileFor(vehicle)
    if not profile or not java() or M.cabinSeat(vehicle, profile) < 0 then return false end
    if M.inVanillaSeat(player, vehicle, profile) then return false end   -- driving: the game's own menu
    -- I.testMouse: scripted test runs name the screen point (like MELens.testInput).
    local mouse = I.testMouse
    local hit = I.pick(vehicle, profile, mouse and mouse.x or getMouseXScaled(), mouse and mouse.y or getMouseYScaled())
    -- addOptionOnTop puts the latest first: the thing under the mouse, then the dashboard.
    if not hit or hit.kind ~= "panel" then
        I.addDashboardOption(player, vehicle, context)
    end
    if not hit then return true end
    if hit.kind == "panel" then
        panelMenu(player, vehicle, profile, context)
    elseif hit.kind == "driver" then
        driverMenu(player, vehicle, profile, context)
    elseif hit.kind == "loose" then
        M.LooseUI.menu(player, vehicle, profile, hit, context)
    elseif hit.kind == "piece" then
        pieceMenu(player, vehicle, hit, context)
    else
        spotMenu(player, vehicle, hit, context)
    end
    return true
end

------------------------------------------------------------------------------------
-- Without a mouse (a controller): the menu of what is nearest to the character
------------------------------------------------------------------------------------

-- The nearest piece, empty place, utility panel or driver's seat to where the character stands.
function I.nearestHit(player, vehicle, profile)
    local x, z = P.characterAt(vehicle, player)
    if not x then return nil end
    local best, bestD
    local function consider(hit, hx, hz)
        local d = (hx - x) ^ 2 + (hz - z) ^ 2
        -- what lies on a piece loses to the piece unless it is clearly nearer (standing at the stove you want the stove)
        if hit.kind == "loose" then d = d + 0.06 end
        if not bestD or d < bestD then best, bestD = hit, d end
    end
    for index, spot in ipairs(profile.spots or {}) do
        local part = P.spotPart(vehicle, index)
        local piece = part and P.pieceAt(part)
        if part and (piece or (spot.level or 1) == 1) then
            consider({ kind = piece and "piece" or "spot", index = index, part = part, spot = spot, piece = piece,
                a = 0, x = spot.x, z = spot.z }, spot.x, spot.z)
        end
    end
    if profile.panel then
        consider({ kind = "panel", x = profile.panel.x, z = profile.panel.z }, profile.panel.x, profile.panel.z)
    end
    -- what lies there
    if M.LooseUI then
        for _, c in ipairs(M.LooseUI.pickCandidates(vehicle, profile)) do
            consider(c, c.entry.x, c.entry.z)
        end
    end
    if profile.driver then
        local d = profile.driver
        consider({ kind = "driver", x = (d.x1 + d.x2) / 2, z = (d.z1 + d.z2) / 2 }, (d.x1 + d.x2) / 2, (d.z1 + d.z2) / 2)
    end
    return best
end

-- Opens the context menu of the nearest thing (the radial menu's "Use nearby furniture").
function I.nearbyMenu(player)
    local vehicle = player:getVehicle()
    local profile = M.profileFor(vehicle)
    if not profile then return end
    local playerNum = player:getPlayerNum()
    local sx = isoToScreenX(playerNum, player:getX(), player:getY(), player:getZ())
    local sy = isoToScreenY(playerNum, player:getX(), player:getY(), player:getZ())
    local context = ISContextMenu.get(playerNum, sx, sy)
    I.addDashboardOption(player, vehicle, context)
    local hit = I.nearestHit(player, vehicle, profile)
    if hit then
        if hit.kind == "panel" then
            panelMenu(player, vehicle, profile, context)
        elseif hit.kind == "driver" then
            driverMenu(player, vehicle, profile, context)
        elseif hit.kind == "loose" then
            M.LooseUI.menu(player, vehicle, profile, hit, context)
        elseif hit.kind == "piece" then
            pieceMenu(player, vehicle, hit, context)
        else
            spotMenu(player, vehicle, hit, context)
        end
    end
    if JoypadState.players[playerNum + 1] then
        context.origin = JoypadState.players[playerNum + 1].focus
        context.mouseOver = 1
        setJoypadFocus(playerNum, context)
    end
end

------------------------------------------------------------------------------------
-- Sleep from the vehicle radial menu: the nearest free bed
------------------------------------------------------------------------------------

function I.nearestBed(player, vehicle, profile)
    local x, z = P.characterAt(vehicle, player)
    x, z = x or profile.door.x, z or profile.door.z
    local best
    for index, spot in ipairs(profile.spots or {}) do
        local part = P.spotPart(vehicle, index)
        local piece = P.pieceAt(part)
        if piece and P.kit(piece).kind == "bed" then
            local hit = { spot = spot, piece = piece, part = part }
            local seatId, sx, sz = freeSeat(vehicle, hit, x, z)
            if seatId then
                local d = (sx - x) ^ 2 + (sz - z) ^ 2
                if not best or d < best.d then
                    best = { d = d, seatId = seatId, x = sx, z = sz }
                end
            end
        end
    end
    return best
end

function I.sleepInCamper(player, vehicle)
    local profile = M.profileFor(vehicle)
    local bed = profile and I.nearestBed(player, vehicle, profile)
    if not bed then
        say(player, "IGUI_MELens_NoFreeBed")
        return
    end
    M.useSeat(player, bed.seatId, bed.x, bed.z, true)
end

------------------------------------------------------------------------------------
-- The use key (E) inside: sit or lie down on what is next to you
------------------------------------------------------------------------------------

I.SEAT_REACH = 0.75     -- tiles between you and a bed, dinette or bus seat (or a bus's driver's seat) for E to use it

-- The free seat of the nearest piece within reach that you can sit or lie on, or the driver's seat:
-- { seatId, x, z } (where to stand for it). nil when there is none; then the reason when a piece within reach
-- has seats but someone uses them all.
function I.seatNear(player, vehicle, profile)
    local x, z = P.characterAt(vehicle, player)
    if not x then return nil end
    local best, taken
    for index, spot in ipairs(profile.spots or {}) do
        local part = P.spotPart(vehicle, index)
        local piece = part and P.pieceAt(part)
        if piece and spot.seats and #spot.seats > 0 then
            local d = P.distanceTo(spot, piece, x, z)
            if d <= I.SEAT_REACH and (not best or d < best.d) then
                local posed = false
                for _, id in ipairs(spot.seats) do
                    if P.seatPose(vehicle, profile, id) then posed = true end
                end
                if posed then
                    local seatId, sx, sz = freeSeat(vehicle, { spot = spot, piece = piece, part = part }, x, z)
                    if seatId then
                        best = { d = d, seatId = seatId, x = sx, z = sz }
                    else
                        taken = true
                    end
                end
            end
        end
    end
    local driver = profile.driver
    if driver then
        local dx = math.max(0, driver.x1 - x, x - driver.x2)
        local dz = math.max(0, driver.z1 - z, z - driver.z2)
        local d = math.sqrt(dx * dx + dz * dz)
        if d <= I.SEAT_REACH and (not best or d < best.d) then
            local index = M.seatIndex(vehicle, driver.seat)
            if index >= 0 and not vehicle:getCharacter(index) then
                local sx, sz = M.driverStandPoint(profile)
                best = { d = d, seatId = driver.seat, x = sx, z = sz }
            else
                taken = true
            end
        end
    end
    if best then return best end
    return nil, taken and "IGUI_PlayerText_VehicleSomeoneInSeat" or nil
end

-- E while standing inside: sit at the dinette, lie on the bed or take the bus seat or driver's seat next to you.
-- True when it did something.
function I.useNearestSeat(player, vehicle)
    local profile = M.profileFor(vehicle)
    if not profile then return false end
    local seat, why = I.seatNear(player, vehicle, profile)
    if not seat then
        if why then say(player, why) end
        return false
    end
    M.useSeat(player, seat.seatId, seat.x, seat.z, false)
    return true
end

------------------------------------------------------------------------------------
-- Loot window: names and icons of the camper's storage, and a refresh when you walk
-- into or out of reach of a piece.
------------------------------------------------------------------------------------

local ICONS = {
    MELensRV_bed = "dresser", MELensRV_dinette = "crate", MELensRV_kitchen = "counter",
    MELensRV_fridge = "fridge", MELensRV_cabinet = "dresser", MELensRV_wardrobe = "wardrobe",
    MELensRV_washroom = "medicine", MELensOven = "stove",
    MELensRV_box = "cardboardbox",
    MELensRV_busseat = "SeatFrontLeft", MELensRV_busseat2 = "SeatFrontLeft",
    MELensFloor = "floor",
}
for key, vanilla in pairs(ICONS) do
    ContainerButtonIcons[key] = ContainerButtonIcons[key] or ContainerButtonIcons[vanilla]
end
if getTexture then
    for _, piece in ipairs({ "metalcase", "stretcher", "safe", "parcels", "medlocker", "medbench", "equipmentrack", "workbench" }) do
        local icon = getTexture("media/textures/Item_MELensRV_" .. piece .. ".png")
        if icon then ContainerButtonIcons["MELensRV_" .. piece] = icon end
    end
end

local reachKey = nil
local reachTimer = 0

function I.updateReach(player, dt)
    reachTimer = reachTimer + dt
    if reachTimer < 0.25 then return end
    reachTimer = 0
    local vehicle = player:getVehicle()
    local key = ""
    local profile = M.profileFor(vehicle)
    if profile then
        -- A preview (the green see-through piece) only stands where the placing mode's mouse is now: one left behind
        -- (reported after placing, having started placing several times) goes, whatever left it there.
        local active = M.Placement and M.Placement.active
        local keep = active and active.hover and active.hover.part
        local stale = {}
        for part in pairs(P.ghosts or {}) do
            if part ~= keep then stale[#stale + 1] = part end
        end
        for _, part in ipairs(stale) do
            P.showPiece(part, true, false)
        end
        for index = 1, #(profile.spots or {}) do
            P.showPiece(P.spotPart(vehicle, index))
        end
        for i = 0, vehicle:getPartCount() - 1 do
            local part = vehicle:getPartByIndex(i)
            if part:getItemContainer() and vehicle:canAccessContainer(i, player) then
                key = key .. i .. ","
            end
        end
    end
    if key ~= reachKey then
        local first = reachKey == nil
        reachKey = key
        if not first then
            local loot = getPlayerLoot(player:getPlayerNum())
            if loot then loot:refreshBackpacks() end
        end
    end
end

------------------------------------------------------------------------------------
-- Generator sound: running generators hum, like the ones on the ground
------------------------------------------------------------------------------------

local hums = {}
local humTimer = 0
local HUM_RANGE = 14     -- tiles around you searched for running campers

-- Campers standing on the squares around the player (the cell's vehicle list cannot be
-- walked from Lua).
local function campersNear(player)
    local found, list = {}, {}
    local cell = getCell()
    local px, py, pz = math.floor(player:getX()), math.floor(player:getY()), math.floor(player:getZ())
    for x = px - HUM_RANGE, px + HUM_RANGE, 2 do
        for y = py - HUM_RANGE, py + HUM_RANGE, 2 do
            local square = cell:getGridSquare(x, y, pz)
            local vehicle = square and square:getVehicleContainer()
            if vehicle and not found[vehicle] and M.profileFor(vehicle) then
                found[vehicle] = true
                table.insert(list, vehicle)
            end
        end
    end
    local own = player:getVehicle()
    if own and not found[own] and M.profileFor(own) then
        table.insert(list, own)
    end
    return list
end

function I.updateHum(player, dt)
    humTimer = humTimer + dt
    if humTimer < 1.0 then return end
    humTimer = 0
    local keep = {}
    for _, vehicle in ipairs(campersNear(player)) do
        if U.hasPower(vehicle) then
            local id = vehicle:getId()
            local hum = hums[id]
            local emitter = vehicle:getEmitter()
            if emitter and (not hum or hum.emitter ~= emitter or not emitter:isPlaying(hum.sound)) then
                hum = { emitter = emitter, sound = emitter:playSound("GeneratorLoop") }
            end
            keep[id] = hum
        end
    end
    for id, hum in pairs(hums) do
        if not keep[id] and hum.emitter:isPlaying(hum.sound) then
            hum.emitter:stopSound(hum.sound)
        end
    end
    hums = keep
end

function I.reset()
    reachKey = nil
    hums = {}
    P.shown = {}
    P.ghosts = {}
end

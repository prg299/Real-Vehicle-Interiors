--
-- ME: LENS: placing furniture. Right-click an RV furniture item in your inventory and
-- choose "Place furniture" while you are inside: every place it fits lights up on the
-- floor, the one under the mouse shows the piece there as a see-through preview (its
-- ghost model, drawn by the Java part), a left-click puts it there (you walk over and
-- set it down) and a right-click or Escape stops.
--
require "ISUI/ISUIElement"
require "ISUI/ISInventoryPaneContextMenu"
require "MELens_Parts"
require "TimedActions/MELens_Actions"

MELens = MELens or {}
local M = MELens
local P = M.Parts
M.Placement = M.Placement or {}
local L = M.Placement

local COLOUR = { 0.36, 0.86, 0.45 }     -- the places it fits
local STRENGTH = 0.55
local HOVER_STRENGTH = 1.0

local function java()
    return MELensRV
end

local function say(player, key, ...)
    HaloTextHelper.addBadText(player, getText(key, ...))
end

-- Passenger space (tiles) to the body's mesh space (the Java part's floor markers).
local function toMesh(profile, x, y, z)
    local m = profile.mesh
    return -x / m.scale, z / m.scale, m.lift - y / m.scale
end

-- The places a piece fits in a vehicle: the empty spots big enough for it (a stacked box
-- only where there is a box below it to rest on).
function L.placesFor(vehicle, profile, piece)
    local list = {}
    local standing = P.standing(vehicle, profile)
    for index, spot in ipairs(profile.spots or {}) do
        local part = P.spotPart(vehicle, index)
        if part and part:getInventoryItem() == nil and P.fits(spot, piece) and P.supported(vehicle, profile, index)
                and P.roomFor(profile, standing, index, piece) then
            -- the rectangle the piece would stand on (centred along the spot)
            local length, depth = P.footprint(spot, piece)
            local xs, zs = {}, {}
            for _, a in ipairs({ -length / 2, length / 2 }) do
                for _, d in ipairs({ 0, depth }) do
                    local x, z = P.spotPoint(spot, a, d)
                    table.insert(xs, x)
                    table.insert(zs, z)
                end
            end
            local x0, x1 = math.min(unpack(xs)), math.max(unpack(xs))
            local z0, z1 = math.min(unpack(zs)), math.max(unpack(zs))
            table.insert(list, { index = index, spot = spot, part = part, rise = spot.rise or 0,
                                 x0 = x0, x1 = x1, z0 = z0, z1 = z1 })
        end
    end
    return list
end

-- Whether you can place furniture now (standing or seated inside, not driving).
function L.canPlace(player)
    local vehicle = player and player:getVehicle()
    local profile = M.profileFor(vehicle)
    if not profile or not java() or M.cabinSeat(vehicle, profile) < 0 then return false end
    return not M.inVanillaSeat(player, vehicle, profile)
end

------------------------------------------------------------------------------------
-- The placing mode: a transparent full-screen element that takes the mouse
------------------------------------------------------------------------------------

L.Mode = ISUIElement:derive("MELensPlacementMode")

function L.Mode:new(player, vehicle, profile, item, piece, places)
    local o = ISUIElement.new(self, 0, 0, getCore():getScreenWidth(), getCore():getScreenHeight())
    o.player, o.vehicle, o.profile = player, vehicle, profile
    o.item, o.piece, o.places = item, piece, places
    o.hover = nil
    o.anchorLeft, o.anchorRight, o.anchorTop, o.anchorBottom = true, true, true, true
    o:setWantKeyEvents(true)
    return o
end

function L.Mode:showMarkers()
    local rv = java()
    rv.clearSpotMarkers()
    local scale = self.profile.mesh.scale
    for i, place in ipairs(self.places) do
        local cx, cz = (place.x0 + place.x1) / 2, (place.z0 + place.z1) / 2
        local mx, my, mz = toMesh(self.profile, cx, self.profile.floorY + place.rise, cz)
        local strength = place == self.hover and HOVER_STRENGTH or STRENGTH
        rv.setSpotMarker(i - 1, mx, my, mz, (place.x1 - place.x0) / 2 / scale, (place.z1 - place.z0) / 2 / scale,
            0.12 / scale, COLOUR[1], COLOUR[2], COLOUR[3], strength)
    end
end

function L.Mode:placeUnderMouse()
    local sx, sy = getMouseXScaled(), getMouseYScaled()
    local floor = self.profile.floorY
    -- Each place at the height of its own floor (the top of the box below, for a stacked
    -- one), highest first as what stands higher is drawn in front, and a little above it
    -- (a piece's preview stands in front of its floor).
    local order = {}
    for _, place in ipairs(self.places) do
        table.insert(order, place)
    end
    table.sort(order, function(a, b) return a.rise > b.rise end)
    for _, place in ipairs(order) do
        for _, lift in ipairs({ 0, 0.3 }) do
            local x, z = M.Interact.screenToCamper(self.vehicle, sx, sy, floor + place.rise + lift)
            if x >= place.x0 and x <= place.x1 and z >= place.z0 and z <= place.z1 then
                return place
            end
        end
    end
    return nil
end

function L.Mode:setHover(place)
    if place == self.hover then return end
    if self.hover then
        P.showPiece(self.hover.part, true, false)
    end
    self.hover = place
    if place then
        P.showPiece(place.part, true, self.piece)
    end
    self:showMarkers()
end

-- The item may be in a bag or a container of the vehicle (the loot window): placing it
-- moves it to your inventory first (ISInventoryPaneContextMenu.transferIfNeeded).
function L.Mode:stillValid()
    return self.player:getVehicle() == self.vehicle and L.canPlace(self.player)
        and self.item:getContainer() ~= nil
end

function L.Mode:update()
    if not self:stillValid() then
        self:stop()
        return
    end
    self:setHover(self:placeUnderMouse())
end

function L.Mode:prerender()
    if self.hover then
        local text = getText("IGUI_MELens_PlaceHere", self.item:getDisplayName())
        local x, y = getMouseX() + 18, getMouseY() + 8
        local w = getTextManager():MeasureStringX(UIFont.Small, text) + 10
        self:drawRect(x - self.x, y - self.y, w, 20, 0.7, 0, 0, 0)
        self:drawText(text, x - self.x + 5, y - self.y + 2, 1, 1, 1, 1, UIFont.Small)
    end
end

function L.Mode:onMouseDown(x, y)
    local place = self.hover or self:placeUnderMouse()
    if place then
        local player, vehicle, item, piece = self.player, self.vehicle, self.item, self.piece
        self:stop()
        ISInventoryPaneContextMenu.transferIfNeeded(player, item)
        local a = 0
        local sx, sz = M.Interact.standPoint(place.spot, piece, a)
        M.standingThen(player, function()
            M.walkTo(player, sx, sz, function()
                ISTimedActionQueue.add(MELensPlaceFurniture:new(player, vehicle, place.part, item))
            end)
        end)
    end
    return true
end

function L.Mode:onRightMouseDown(x, y)
    self:stop()
    return true
end

function L.Mode:onMouseUp(x, y) return true end
function L.Mode:onRightMouseUp(x, y) return true end

function L.Mode:onKeyRelease(key)
    if key == Keyboard.KEY_ESCAPE then
        self:stop()
    end
end

function L.Mode:isKeyConsumed(key)
    return key == Keyboard.KEY_ESCAPE
end

function L.Mode:stop()
    if self.hover then
        P.showPiece(self.hover.part, true, false)
        self.hover = nil
    end
    if java() then java().clearSpotMarkers() end
    self:removeFromUIManager()
    if L.active == self then L.active = nil end
end

-- Starts placing an item's piece in the vehicle you are in.
function L.start(player, item)
    if L.active then L.active:stop() end
    local piece = P.pieceOfItem(item)
    if not piece then return end
    if not L.canPlace(player) then
        say(player, "IGUI_MELens_WalkInsideToPlace")
        return
    end
    local vehicle = player:getVehicle()
    local profile = M.profileFor(vehicle)
    local places = L.placesFor(vehicle, profile, piece)
    if #places == 0 then
        say(player, "IGUI_MELens_NoPlaceFits")
        return
    end
    local mode = L.Mode:new(player, vehicle, profile, item, piece, places)
    mode:initialise()
    mode:addToUIManager()
    mode:setAlwaysOnTop(true)
    mode:showMarkers()
    L.active = mode
end

------------------------------------------------------------------------------------
-- "Place furniture" on RV furniture items in the inventory
------------------------------------------------------------------------------------

local function onFillInventoryObjectContextMenu(playerNum, context, items)
    local player = getSpecificPlayer(playerNum)
    if not player then return end
    for _, entry in ipairs(items) do
        local item = entry
        if type(entry) == "table" and entry.items then
            item = entry.items[1]
        end
        if item and P.pieceOfItem(item) then
            local option = context:addOptionOnTop(getText("ContextMenu_MELens_PlaceFurniture"), player, L.start, item)
            option.iconTexture = item:getTex()
            if not L.canPlace(player) then
                option.notAvailable = true
                local tip = ISWorldObjectContextMenu.addToolTip()
                tip.description = getText("IGUI_MELens_WalkInsideToPlace")
                option.toolTip = tip
            end
            return
        end
    end
end

Events.OnFillInventoryObjectContextMenu.Add(onFillInventoryObjectContextMenu)

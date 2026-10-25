--
-- ME: LENS loose items, what you do with them (MELens_Loose.lua says where each lies, MELens_LooseView.lua
-- hands them to the Java part that draws them):
--
--   * Place: right-click an item in your inventory (or the loot window) while you are inside a vehicle, Place.
--     A see-through copy follows the mouse over the floor and over the tops of the furniture (the counter, the
--     table, the bed, the cabinets, the wheel wells); green where it fits, red where it does not. R turns it, a
--     left click walks you there and sets it down, a right click or Escape stops.
--   * Drop (the menu's Drop, or dragging an item out of the inventory) puts the item on the floor where you stand.
--   * Right-click a thing that lies there: Grab, Move, Turn.
--
require "ISUI/ISUIElement"
require "ISUI/ISInventoryPaneContextMenu"
require "ISUI/ISInventoryPane"
require "MELens_Cabin"
require "MELens_Interact"
require "MELens_Placement"
require "MELens_Loose"
require "MELens_LooseView"
require "TimedActions/MELens_Actions"

MELens = MELens or {}
local M = MELens
M.LooseUI = M.LooseUI or {}
local UI = M.LooseUI
local L = M.Loose
local P = M.Parts
local I = M.Interact
local V = M.LooseView

local function java()
    return M.java()
end

local function say(player, key, ...)
    HaloTextHelper.addBadText(player, getText(key, ...))
end

------------------------------------------------------------------------------------
-- Sizes
------------------------------------------------------------------------------------

local sizes = {}

-- An item's size in tiles at yaw 0: along the vehicle's left, up, and front. Nil while its model loads.
function UI.size(item)
    local rv = java()
    if not rv or not item then return nil end
    local k = item:getFullType()
    local s = sizes[k]
    if s == nil then
        local text = rv.itemSize(item)
        if text == nil then return nil end
        local a, b, c = string.match(text, "([^,]+),([^,]+),([^,]+)")
        s = { tonumber(a) or 0.2, tonumber(b) or 0.1, tonumber(c) or 0.2 }
        sizes[k] = s
    end
    return s[1], s[2], s[3]
end

-- Whether the item can be placed: shown as its model, or as a flat picture of its icon.
function UI.placeable(item)
    local rv = java()
    return rv ~= nil and item ~= nil and P.pieceOfItem(item) == nil and rv.canShow(item)
end

function UI.canPlace(player)
    return M.Placement.canPlace(player)
end

------------------------------------------------------------------------------------
-- Where to stand
------------------------------------------------------------------------------------

-- Where to stand to reach a point on a surface: in front of the piece it is on; for the floor, next to the
-- spot on the side you come from (not on top of it); else the nearest open floor.
function UI.standFor(vehicle, profile, x, z, s, player, reach)
    player = player or getSpecificPlayer(0)
    -- Actions already accept this reach. Keep an available standing position rather
    -- than taking an unnecessary approach path into a narrow furniture corner.
    if player and M.isStanding(player) then
        local px, pz = P.characterAt(vehicle, player)
        if px and ((reach and (px-x)^2+(pz-z)^2 <= reach^2)
                or (not reach and P.reachesLoose(player, vehicle, x, z))) then return px, pz end
    end
    if s and s > 0 then
        local spot = profile.spots[s]
        local piece = spot and P.pieceAt(P.spotPart(vehicle, s))
        if spot and piece then
            local a = P.toSpot(spot, x, z)
            return I.openStandPoint(vehicle, spot, piece, a)
        end
    end
    local fx, fz = M.nearestWalkableAt(profile, x, z)
    -- a ring round the spot: the open floor on the side you come from
    local px, pz = P.characterAt(vehicle, player)
    if px then
        local best, bx, bz = nil, fx, fz
        for step = 0, 11 do
            local angle = step * math.pi / 6
            local cx, cz = x + 0.42 * math.cos(angle), z + 0.42 * math.sin(angle)
            if M.walkableAt(profile, cx, cz) then
                local d = (cx - px) ^ 2 + (cz - pz) ^ 2
                if not best or d < best then
                    best, bx, bz = d, cx, cz
                end
            end
        end
        if best then return bx, bz end
    end
    return fx, fz
end

-- True while you are busy walking or doing something (a second thing must wait).
function UI.busy(player)
    return ISTimedActionQueue.isPlayerDoingAction(player) or M.pathing(player) or M.afterStanding ~= nil
end

------------------------------------------------------------------------------------
-- The ray under the mouse and the furniture in front of the floor
------------------------------------------------------------------------------------

-- Where the mouse ray meets the plane at height h, remembered for the frame: a truck has dozens of box tops at
-- three heights, and every surface and every step of the furniture test asks for the same few.
local rays = { sx = nil, sy = nil, ms = 0, vehicle = nil, byHeight = {} }

local function rayAt(vehicle, sx, sy, h)
    local now = getTimestampMs()
    if rays.sx ~= sx or rays.sy ~= sy or rays.vehicle ~= vehicle or now - rays.ms > 30 then
        rays.sx, rays.sy, rays.vehicle, rays.ms, rays.byHeight = sx, sy, vehicle, now, {}
    end
    local key = math.floor(h * 500 + 0.5)
    local at = rays.byHeight[key]
    if not at then
        local x, z = I.screenToCamper(vehicle, sx, sy, h)
        at = { x, z }
        rays.byHeight[key] = at
    end
    return at[1], at[2]
end

-- Whether furniture stands between the camera and the floor at this screen point (the mouse is over the side
-- of a counter, the floor behind it is hidden).
function UI.furnitureHides(vehicle, profile, sx, sy)
    local floorY = profile.floorY
    for index, spot in ipairs(profile.spots or {}) do
        local piece = P.pieceAt(P.spotPart(vehicle, index))
        if piece then
            local length, depth, height = P.footprint(spot, piece)
            local base = floorY + (spot.rise or 0)
            local h = base + height
            while h > base + 0.03 do
                local x, z = rayAt(vehicle, sx, sy, h)
                local a, d = P.toSpot(spot, x, z)
                if math.abs(a) <= length / 2 and d >= 0 and d <= depth then
                    return true
                end
                h = h - 0.07
            end
        end
    end
    return false
end

local function clashes(list, surface, x, z, hx, hz, skipId)
    local s = surface.s
    for _, e in ipairs(list) do
        if e.id ~= skipId and e.s == s and math.abs((e.y or surface.y) - surface.y) < 0.03 then
            local proto = V.proto(e.t)
            local w, _, d = UI.size(proto)
            local ex, ez = L.half(w or 0.2, d or 0.2, e.r)
            if math.abs(e.x - x) < ex + hx - 0.002 and math.abs(e.z - z) < ez + hz - 0.002 then
                return true
            end
        end
    end
    return false
end

-- Keeps an item's middle on a top: it may hang over the edge by the share L.overhang allows. An item longer than
-- the top sits in its middle (and fits only if the overhang allows that much).
local function clampOnto(surface, x, z, hx, hz)
    local keep = 1 - L.overhang(surface)
    local ox, oz = hx * keep, hz * keep
    local lo, hi = surface.x0 + ox, surface.x1 - ox
    x = lo <= hi and math.max(lo, math.min(hi, x)) or (surface.x0 + surface.x1) / 2
    lo, hi = surface.z0 + oz, surface.z1 - oz
    z = lo <= hi and math.max(lo, math.min(hi, z)) or (surface.z0 + surface.z1) / 2
    return x, z
end

UI.SNAP_RADIUS = 0.3      -- how far the preview may move to where the item fits
UI.SNAP_STEP = 0.03
UI.SNAP_CLEAR = 0.12      -- how far it may move to keep clear of other items (beyond that it overlaps them)

-- Where an item goes when the mouse is at (x, z) on a surface: there when it fits; else the nearest place within
-- UI.SNAP_RADIUS that does. Items may overlap others, like items on the ground outside, but a free place close by
-- is taken first. Returns x, z, fits, why ("tall", or what keeps the place under the mouse from fitting).
local function settle(vehicle, profile, surface, x, z, hx, hz, h, list, skip)
    if surface.head and h > surface.head then return x, z, false, "tall" end
    local fits, why = L.fitsSurface(vehicle, profile, surface, x, z, hx, hz)
    if fits and not clashes(list, surface, x, z, hx, hz, skip) then return x, z, true end
    local first = fits and { x, z } or nil
    local r = UI.SNAP_STEP
    while r <= UI.SNAP_RADIUS + 1e-6 do
        local count = math.max(8, math.floor(math.pi * r / UI.SNAP_STEP))
        for k = 0, count - 1 do
            local a = k * 2 * math.pi / count
            local px, pz = x + r * math.cos(a), z + r * math.sin(a)
            if surface.kind ~= "floor" then px, pz = clampOnto(surface, px, pz, hx, hz) end
            if L.fitsSurface(vehicle, profile, surface, px, pz, hx, hz) then
                if not clashes(list, surface, px, pz, hx, hz, skip) then return px, pz, true end
                first = first or { px, pz }
            end
        end
        if first and r >= UI.SNAP_CLEAR then break end
        r = r + UI.SNAP_STEP
    end
    if first then return first[1], first[2], true end
    return x, z, false, why
end

-- Where an item turned `yaw` degrees goes for a point (x, z) on a surface, without the mouse (a controller's
-- spots, scripted tests): { surface, x, y, z, valid, reason }, or nil while the item's model is loading.
function UI.placeNear(vehicle, profile, item, yaw, surface, x, z, list)
    local w, h, d = UI.size(item)
    if not w then return nil end
    local hx, hz = L.half(w, d, yaw)
    list = list or L.list(vehicle, profile)
    if surface.kind ~= "floor" then
        x, z = clampOnto(surface, x, z, hx, hz)
    end
    local px, pz, fits, why = settle(vehicle, profile, surface, x, z, hx, hz, h, list, item:getID())
    return { surface = surface, x = px, y = surface.y, z = pz, valid = fits, reason = why }
end

------------------------------------------------------------------------------------
-- The placing mode
------------------------------------------------------------------------------------

UI.Mode = ISUIElement:derive("MELensLooseMode")

local REASONS = {
    wall = "IGUI_MELens_ReasonWall", furniture = "IGUI_MELens_ReasonFurniture",
    edge = "IGUI_MELens_ReasonEdge", item = "IGUI_MELens_ReasonItem", tall = "IGUI_MELens_ReasonTall",
}

function UI.Mode:new(player, vehicle, profile, items)
    local o = ISUIElement.new(self, 0, 0, getCore():getScreenWidth(), getCore():getScreenHeight())
    o.player, o.vehicle, o.profile, o.items = player, vehicle, profile, items
    o.yaw = UI.lastYaw or 0
    o.hover = nil
    o.busy = false
    o.rotateHeld = nil
    o.joypad = player:getJoypadBind() ~= -1      -- a controller: the places round you instead of the mouse
    o.index = 1
    o.anchorLeft, o.anchorRight, o.anchorTop, o.anchorBottom = true, true, true, true
    o:setWantKeyEvents(true)
    return o
end

function UI.Mode:current()
    return self.items[1]
end

-- The item may be in a bag or the loot window: placing it brings it to your inventory first.
function UI.Mode:stillValid()
    local item = self:current()
    return item ~= nil and self.player:getVehicle() == self.vehicle and UI.canPlace(self.player)
        and item:getContainer() ~= nil
end

function UI.Mode:data()
    local now = getTimestampMs()
    if not self.surfaces or now - (self.dataAt or 0) > 400 then
        self.surfaces = L.surfaces(self.vehicle, self.profile)
        self.list = L.list(self.vehicle, self.profile)
        self.dataAt = now
    end
    return self.surfaces, self.list
end

-- With a controller: the places round you to choose from, the floor in front first, then the tops of the
-- furniture within reach, then the floor to the sides and behind. { surface, x, z }.
function UI.Mode:joypadSpots(item)
    local w, _, d = UI.size(item)
    if not w then return {} end
    local hx, hz = L.half(w, d, self.yaw)
    local surfaces = self:data()
    local px, pz = P.characterAt(self.vehicle, self.player)
    if not px then return {} end
    local facing = M.facingOf(self.player) or 0
    local fx, fz = -math.sin(facing), math.cos(facing)
    local floorSurface = surfaces[#surfaces]
    local front, around, tops = {}, {}, {}
    for k = 0, 7 do
        local a = k * math.pi / 4
        local dx = fx * math.cos(a) - fz * math.sin(a)
        local dz = fx * math.sin(a) + fz * math.cos(a)
        local spot = { surface = floorSurface, x = px + 0.55 * dx, z = pz + 0.55 * dz }
        if k == 0 then front[#front + 1] = spot else around[#around + 1] = spot end
    end
    for _, surface in ipairs(surfaces) do
        if surface.kind ~= "floor" then
            local cx = math.max(surface.x0 + hx, math.min(surface.x1 - hx, px))
            local cz = math.max(surface.z0 + hz, math.min(surface.z1 - hz, pz))
            local dist = (cx - px) ^ 2 + (cz - pz) ^ 2
            if dist <= 1.4 * 1.4 then
                tops[#tops + 1] = { surface = surface, x = cx, z = cz, dist = dist }
            end
        end
    end
    table.sort(tops, function(a, b) return a.dist < b.dist end)
    local out = {}
    for _, group in ipairs({ front, tops, around }) do
        for _, spot in ipairs(group) do out[#out + 1] = spot end
    end
    return out
end

function UI.Mode:joypadHover(item)
    local now = getTimestampMs()
    if not self.spots or now - (self.spotsAt or 0) > 350 or self.spotsYaw ~= self.yaw then
        self.spots = self:joypadSpots(item)
        self.spotsAt, self.spotsYaw = now, self.yaw
    end
    if #self.spots == 0 then return nil end
    self.index = math.max(1, math.min(#self.spots, self.index))
    local spot = self.spots[self.index]
    local _, list = self:data()
    -- (worked out again only when the spot, the turn or what lies there changes)
    local key = table.concat({ self.index, self.yaw, self.spotsAt or 0, self.dataAt or 0, item:getID() }, "|")
    if self.padKey ~= key then
        self.padKey = key
        self.padHover = UI.placeNear(self.vehicle, self.profile, item, self.yaw, spot.surface, spot.x, spot.z, list)
    end
    return self.padHover
end

-- A controller: the d-pad chooses the place, the bumpers turn the item, A sets it down, B stops.
function UI.Mode:onJoypadDown(button)
    if button == Joypad.AButton then
        if not self.busy then self:commit() end
    elseif button == Joypad.BButton then
        self:stop()
    elseif button == Joypad.LBumper then
        self.yaw = (self.yaw - 45) % 360
    elseif button == Joypad.RBumper then
        self.yaw = (self.yaw + 45) % 360
    end
end

function UI.Mode:nextSpot(step)
    local count = self.spots and #self.spots or 0
    if count > 0 then
        self.index = (self.index - 1 + step) % count + 1
    end
end

function UI.Mode:onJoypadDirUp() self:nextSpot(-1) end
function UI.Mode:onJoypadDirLeft() self:nextSpot(-1) end
function UI.Mode:onJoypadDirDown() self:nextSpot(1) end
function UI.Mode:onJoypadDirRight() self:nextSpot(1) end

-- Where an item would go for the mouse at screen point (sx, sy), turned yaw degrees: the highest surface under it.
-- { surface, x, y, z, valid, reason }, or nil when the point is over no surface (or the model is still loading).
function UI.hoverFor(vehicle, profile, item, yaw, sx, sy, surfaces, list)
    local w, h, d = UI.size(item)
    if not w then return nil end
    local hx, hz = L.half(w, d, yaw)
    surfaces = surfaces or L.surfaces(vehicle, profile)
    list = list or L.list(vehicle, profile)
    local skip = item:getID()
    for _, surface in ipairs(surfaces) do
        local x, z = rayAt(vehicle, sx, sy, surface.y)
        local over
        if surface.kind == "floor" then
            over = L.inRoom(profile, x, z) and not UI.furnitureHides(vehicle, profile, sx, sy)
        else
            over = x >= surface.x0 - 0.03 and x <= surface.x1 + 0.03 and z >= surface.z0 - 0.03 and z <= surface.z1 + 0.03
        end
        if over then
            if surface.kind ~= "floor" then
                x, z = clampOnto(surface, x, z, hx, hz)
            end
            local px, pz, fits, why = settle(vehicle, profile, surface, x, z, hx, hz, h, list, skip)
            return { surface = surface, x = px, y = surface.y, z = pz, valid = fits, reason = why }
        end
    end
    return nil
end

-- (worked out again only when the mouse, the turn, the item or what lies there changes: finding a place that fits
-- can try a few hundred spots)
function UI.Mode:hoverAt(item, sx, sy)
    local surfaces, list = self:data()
    local key = table.concat({ sx, sy, self.yaw, item:getID(), self.dataAt or 0 }, "|")
    if self.hoverKey ~= key then
        self.hoverKey = key
        self.hoverCache = UI.hoverFor(self.vehicle, self.profile, item, self.yaw, sx, sy, surfaces, list)
    end
    return self.hoverCache
end

local ROTATE_STEP = 15          -- degrees per tap of the rotate key
local ROTATE_HOLD = 0.35        -- seconds held before it keeps turning
local ROTATE_RATE = 150         -- degrees a second while held

function UI.Mode:rotateKeys()
    local key = KeybindId and KeybindId.ROTATE_BUILDING
    if not key then return end
    local now = getTimestampMs()
    if isKeyDown(key) then
        local direction = isShiftKeyDown() and -1 or 1
        if not self.rotateHeld then
            self.rotateHeld = now
            self.rotateLast = now
            self.yaw = (self.yaw + direction * ROTATE_STEP) % 360
        elseif now - self.rotateHeld > ROTATE_HOLD * 1000 then
            local dt = (now - self.rotateLast) / 1000
            self.yaw = (self.yaw + direction * ROTATE_RATE * dt) % 360
        end
        self.rotateLast = now
    else
        if self.rotateHeld and now - self.rotateHeld > ROTATE_HOLD * 1000 then
            self.yaw = math.floor(self.yaw / 5 + 0.5) * 5 % 360     -- a held key ends on a multiple of 5
        end
        self.rotateHeld = nil
    end
end

function UI.Mode:update()
    if not self:stillValid() then
        self:stop()
        return
    end
    local rv = java()
    if self.busy then
        if UI.busy(self.player) then
            rv.clearLooseGhost()
            self.hover = nil
            return
        end
        self.busy = false
    end
    local item = self:current()
    -- UI.testMouse: scripted test runs name the screen point (like MELens.Interact.testMouse)
    local mouse = UI.testMouse
    if self.joypad and not mouse then
        self.hover = self:joypadHover(item)
    else
        self:rotateKeys()
        self.hover = self:hoverAt(item, mouse and mouse.x or getMouseXScaled(), mouse and mouse.y or getMouseYScaled())
    end
    local hover = self.hover
    if hover then
        rv.setLooseGhost(item, hover.x, hover.y, hover.z, self.yaw, hover.valid)
    else
        rv.clearLooseGhost()
    end
end

function UI.Mode:prerender()
    local item = self:current()
    if not item or self.busy then return end
    local x, y = getMouseX() + 20, getMouseY() + 10
    if self.joypad then
        -- a controller has no mouse: the hints sit above the middle of the bottom of the screen
        x, y = getCore():getScreenWidth() / 2 - 150, getCore():getScreenHeight() - 150
    end
    local lines = {}
    local hover = self.hover
    if hover then
        local text = getText("IGUI_MELens_PlaceHere", item:getDisplayName())
        if not hover.valid then
            text = getText(REASONS[hover.reason] or "IGUI_MELens_ReasonEdge")
        end
        lines[1] = { text, hover.valid and 1 or 1, hover.valid and 1 or 0.55, hover.valid and 1 or 0.5 }
    end
    if self.joypad then
        lines[#lines + 1] = { getText("IGUI_MELens_PlaceKeysPad"), 0.78, 0.78, 0.8 }
    else
        local rotate = KeybindId and getKeyName(getCore():getKey(KeybindId.ROTATE_BUILDING)) or "R"
        lines[#lines + 1] = { getText("IGUI_MELens_PlaceKeys", rotate), 0.78, 0.78, 0.8 }
    end
    local width = 0
    for _, line in ipairs(lines) do
        width = math.max(width, getTextManager():MeasureStringX(UIFont.Small, line[1]))
    end
    local height = 6 + 17 * #lines
    self:drawRect(x - self.x, y - self.y, width + 12, height, 0.72, 0, 0, 0)
    for i, line in ipairs(lines) do
        self:drawText(line[1], x - self.x + 6, y - self.y + 3 + 17 * (i - 1), line[2], line[3], line[4], 1, UIFont.Small)
    end
end

-- Brings the item to you and walks you to the spot, then sets it down: hover is {surface, x, y, z} (UI.hoverFor).
-- unequipped: the caller has already queued taking it off.
function UI.placeAt(player, vehicle, profile, item, hover, yaw, unequipped)
    local sx, sz = UI.standFor(vehicle, profile, hover.x, hover.z, hover.surface.s, player)
    local x, y, z, r, s = hover.x, hover.y, hover.z, yaw, hover.surface.s
    local floor = L.floorContainer(vehicle)
    if item:getContainer() ~= floor then
        player:removeAttachedItem(item)
        if not unequipped and player:isEquipped(item) then
            ISTimedActionQueue.add(ISUnequipAction:new(player, item, 1, "place"))
        end
        ISInventoryPaneContextMenu.transferIfNeeded(player, item)
    end
    M.standingThen(player, function()
        M.walkTo(player, sx, sz, function()
            ISTimedActionQueue.add(MELensPlaceLoose:new(player, vehicle, item, x, y, z, r, s))
            V.refresh()
        end)
    end)
end

-- Walks you there and sets the item down.
function UI.Mode:commit()
    local hover, item = self.hover, self:current()
    if not hover or not item then return end
    if not hover.valid then
        say(self.player, REASONS[hover.reason] or "IGUI_MELens_ReasonEdge")
        return
    end
    local player, vehicle, profile = self.player, self.vehicle, self.profile
    UI.placeAt(player, vehicle, profile, item, hover, self.yaw)
    UI.lastYaw = self.yaw
    table.remove(self.items, 1)
    java().clearLooseGhost()
    self.hover = nil
    self.busy = true
    if #self.items == 0 then
        self:stop()
    end
end

function UI.Mode:onMouseDown(x, y)
    if not self.busy then
        self:commit()
    end
    return true
end

function UI.Mode:onRightMouseDown(x, y)
    self:stop()
    return true
end

function UI.Mode:onMouseUp(x, y) return true end
function UI.Mode:onRightMouseUp(x, y) return true end

function UI.Mode:onKeyRelease(key)
    if key == Keyboard.KEY_ESCAPE then
        self:stop()
    end
end

function UI.Mode:isKeyConsumed(key)
    return key == Keyboard.KEY_ESCAPE
end

function UI.Mode:stop()
    if java() then java().clearLooseGhost() end
    if self.joyfocus then
        setJoypadFocus(self.player:getPlayerNum(), nil)
    end
    self:removeFromUIManager()
    if UI.active == self then UI.active = nil end
end

-- Starts placing items (a list of inventory items) in the vehicle you are in.
function UI.start(player, items)
    if UI.active then UI.active:stop() end
    if not UI.canPlace(player) then
        say(player, "IGUI_MELens_WalkInsideToPlace")
        return
    end
    local vehicle = player:getVehicle()
    local profile = M.profileFor(vehicle)
    local list = {}
    for _, item in ipairs(items) do
        if UI.placeable(item) then list[#list + 1] = item end
    end
    if #list == 0 then return end
    -- the windows get out of the way, as when the game places an item on the ground
    local playerNum = player:getPlayerNum()
    for _, window in ipairs({ getPlayerInventory(playerNum), getPlayerLoot(playerNum) }) do
        if window and window:isVisible() and not window.isCollapsed and not window.pin then
            window.isCollapsed = true
            window:setMaxDrawHeight(window:titleBarHeight())
        end
    end
    local mode = UI.Mode:new(player, vehicle, profile, list)
    mode:initialise()
    mode:addToUIManager()
    mode:setAlwaysOnTop(true)
    UI.active = mode
    if mode.joypad then
        setJoypadFocus(playerNum, mode)
    end
end

------------------------------------------------------------------------------------
-- "Place" in the inventory menu
------------------------------------------------------------------------------------

local function onFillInventoryObjectContextMenu(playerNum, context, items)
    local player = getSpecificPlayer(playerNum)
    if not player or not java() or not player:getVehicle() then return end
    if not M.profileFor(player:getVehicle()) then return end
    local actual = ISInventoryPane.getActualItems(items)
    if not actual or #actual == 0 then return end
    local favourite = false
    for _, item in ipairs(actual) do
        if not UI.placeable(item) then return end
        if item:isFavorite() then favourite = true end
    end
    local option = context:addOption(getText("ContextMenu_MELens_PlaceItem"), player, UI.start, actual)
    option.iconTexture = actual[1]:getTex()
    if not UI.canPlace(player) then
        option.notAvailable = true
        local tip = ISInventoryPaneContextMenu.addToolTip()
        tip.description = getText("IGUI_MELens_WalkInsideToPlace")
        option.toolTip = tip
    elseif favourite then
        option.notAvailable = true
        local tip = ISInventoryPaneContextMenu.addToolTip()
        tip.description = getText("Tooltip_CantPlaceFavoriteItems")
        option.toolTip = tip
    end
end

-- (Registered once, calling through UI, so that a developer's reload of this file takes effect.)
UI.onFillInventoryObjectContextMenu = onFillInventoryObjectContextMenu
if not UI.hooked then
    UI.hooked = true
    Events.OnFillInventoryObjectContextMenu.Add(function(...) return UI.onFillInventoryObjectContextMenu(...) end)
    Events.OnGameStart.Add(function() UI.reset() end)
    Events.OnMainMenuEnter.Add(function() UI.reset() end)
end

------------------------------------------------------------------------------------
-- Dropping: onto the floor where you stand
------------------------------------------------------------------------------------

-- The floor places the items of one Drop were given: their actions record them one after the other, so the next
-- item must not be given the same place. { x, z, ms }, forgotten after a while.
local promised = {}

local function promises()
    local now = getTimestampMs()
    local keep = {}
    for _, p in ipairs(promised) do
        if now - p.ms < 20000 then keep[#keep + 1] = p end
    end
    promised = keep
    return keep
end

-- Puts an item on the vehicle's floor at your feet (the Drop of the menu and of dragging). Anything not in your
-- inventory comes to it first; a bag is dropped with what is in it.
function UI.drop(player, vehicle, profile, item)
    -- dragged out of the inventory and let go over the vehicle's inside: it goes where it was let go, if it fits
    -- (only the first of several; the rest fall at your feet)
    local point = UI.dragPoint
    if point then
        point.n = point.n + 1
        if point.n == 1 and UI.canPlace(player) then
            -- a turn the item's number picks, else square to the vehicle (a pot does not fit a small top at an angle)
            local surfaces, list = L.surfaces(vehicle, profile), L.list(vehicle, profile)
            for _, yaw in ipairs({ (item:getID() * 37) % 360, 0, 90 }) do
                local hover = UI.hoverFor(vehicle, profile, item, yaw, point.x, point.y, surfaces, list)
                if hover and hover.valid then
                    UI.placeAt(player, vehicle, profile, item, hover, yaw, true)
                    return
                end
            end
        end
    end
    ISInventoryPaneContextMenu.transferIfNeeded(player, item)
    local x, z = P.characterAt(vehicle, player)
    if not x then x, z = profile.door.x, profile.door.z end
    if not M.isStanding(player) then
        x, z = M.nearestWalkableAt(profile, x, z)
    end
    local px, pz = L.dropSpot(vehicle, profile, x, z, item:getID(), promises())
    promised[#promised + 1] = { x = px, z = pz, ms = getTimestampMs() }
    local yaw = (item:getID() * 37) % 360
    ISTimedActionQueue.add(MELensPlaceLoose:new(player, vehicle, item, px, profile.floorY, pz, yaw, 0))
    V.refresh()
end

------------------------------------------------------------------------------------
-- Pointing at what lies there (MELens_Interact.lua asks for the candidates and the menu)
------------------------------------------------------------------------------------

-- What the mouse ray can hit, as I.pick's candidates (a box each, a little generous: a hammer is thin).
function UI.pickCandidates(vehicle, profile)
    local out = {}
    local rv = java()
    if not rv then return out end
    local installed = {}
    for index = 1, #(profile.spots or {}) do
        installed[index] = P.pieceAt(P.spotPart(vehicle, index)) ~= nil
    end
    for _, e in ipairs(L.list(vehicle, profile)) do
        local proto = V.proto(e.t)
        if proto and rv.canShow(proto) then
            local w, h, d = UI.size(proto)
            local hx, hz = L.half(w or 0.2, d or 0.2, e.r)
            hx, hz = math.max(hx, 0.07) + 0.03, math.max(hz, 0.07) + 0.03
            local y = e.y
            if e.s and e.s > 0 and not installed[e.s] then y = profile.floorY end
            local entry = e
            out[#out + 1] = {
                kind = "loose", id = e.id, entry = e, bottom = y, top = y + math.max(h or 0.1, 0.12),
                hits = function(x, z) return math.abs(x - entry.x) <= hx and math.abs(z - entry.z) <= hz end,
            }
        end
    end
    return out
end

local function grabNow(player, vehicle, profile, entries)
    local first = entries[1]
    local sx, sz = UI.standFor(vehicle, profile, first.x, first.z, first.s, player)
    M.standingThen(player, function()
        M.walkTo(player, sx, sz, function()
            for _, e in ipairs(entries) do
                local proto = V.proto(e.t)
                ISTimedActionQueue.add(MELensGrabLoose:new(player, vehicle, e.id, proto and proto:getActualWeight() or 1))
            end
            V.refresh()
        end)
    end)
end

-- The menu of an item that lies in the vehicle.
function UI.menu(player, vehicle, profile, hit, context)
    local e = hit.entry
    local floor = L.floorContainer(vehicle)
    local real = floor and floor:getItemById(e.id)
    local item = real or V.proto(e.t)
    if not item then return end
    local header = context:addOptionOnTop(item:getDisplayName())
    header.iconTexture = item:getTex()
    local sub = ISContextMenu:getNew(context)
    context:addSubMenu(header, sub)
    sub:addOption(getText("ContextMenu_Grab"), player, function()
        grabNow(player, vehicle, profile, { e })
    end)
    -- everything within reach of it
    local near = {}
    for _, other in ipairs(L.list(vehicle, profile)) do
        if other.s == e.s and math.abs((other.y or e.y) - (e.y or 0)) < 0.05
                and math.abs(other.x - e.x) < 0.35 and math.abs(other.z - e.z) < 0.35 then
            near[#near + 1] = other
        end
    end
    if #near > 1 then
        sub:addOption(getText("ContextMenu_MELens_GrabAllHere"), player, function()
            grabNow(player, vehicle, profile, near)
        end)
    end
    local move = sub:addOption(getText("ContextMenu_MELens_MoveItem"), player, function()
        UI.start(player, { real })
    end)
    if not real then
        move.notAvailable = true
        local tip = ISInventoryPaneContextMenu.addToolTip()
        tip.description = getText("IGUI_MELens_OpenFloorFirst")
        move.toolTip = tip
    end
    sub:addOption(getText("ContextMenu_MELens_TurnItem"), player, function()
        local sx, sz = UI.standFor(vehicle, profile, e.x, e.z, e.s, player)
        M.standingThen(player, function()
            M.walkTo(player, sx, sz, function()
                ISTimedActionQueue.add(MELensTurnLoose:new(player, vehicle, e.id, 45))
                V.refresh()
            end)
        end)
    end)
end

function UI.reset()
    sizes = {}
    if UI.active then UI.active:stop() end
end

------------------------------------------------------------------------------------
-- The name of the item under the mouse
------------------------------------------------------------------------------------

local label = { text = nil, checked = 0 }

-- Four times a second: what the mouse points at (an item that lies there), if no window or menu is in the way.
local function updateLabel()
    local now = getTimestampMs()
    if now - label.checked < 250 then return end
    label.checked = now
    label.text = nil
    local rv = java()
    local player = getSpecificPlayer(0)
    if not rv or not player or UI.active or not M.itemNamesOn() or player:getJoypadBind() ~= -1 then return end
    if not UI.canPlace(player) or UIManager.isMouseOverInventory() then return end
    local menu = getPlayerContextMenu(0)
    if menu and menu:isAnyVisible() then return end
    local vehicle = player:getVehicle()
    local profile = M.profileFor(vehicle)
    local ok, hit = pcall(I.pick, vehicle, profile, getMouseXScaled(), getMouseYScaled())
    if ok and hit and hit.kind == "loose" then
        local proto = V.proto(hit.entry.t)
        label.text = proto and proto:getDisplayName() or nil
    end
end

local function drawLabel()
    updateLabel()
    if not label.text then return end
    local tm = getTextManager()
    local x, y = getMouseX() + 18, getMouseY() + 24
    local width = tm:MeasureStringX(UIFont.Small, label.text)
    tm:DrawString(UIFont.Small, x + 1, y + 1, label.text, 0, 0, 0, 0.8)
    tm:DrawString(UIFont.Small, x, y, label.text, 1, 1, 1, 1)
end

UI.drawLabel = drawLabel
if not UI.labelHooked then
    UI.labelHooked = true
    Events.OnPostUIDraw.Add(function() UI.drawLabel() end)
end

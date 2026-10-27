--
-- ME: LENS loose items: what you place or drop inside a vehicle lies where it was put.
--
-- The items themselves are ordinary items in the vehicle's Floor container (MELensFloor, the "Floor" in the
-- loot window), so the game saves, syncs and loots them as it does everything else. Where each one lies is
-- kept beside them in the Floor part's modData, which the game saves with the vehicle and the server sends to
-- every client:
--
--     modData.loose["<item id>"] = { t = "Base.Radio", x, y, z, r, s }
--
-- t the item's type (so a client can draw it without holding the container's items), x y z its place in the
-- vehicle's passenger space (x to the left, y up, z to the front; tiles), r the turn in degrees, s what it
-- stands on: 0 the floor, a number above 0 the furniture spot of that number, below 0 the wheel well of that
-- number. The client draws them (MELens_LooseView.lua and the Java part's Loose class); the timed actions that
-- change them are in TimedActions/MELens_Actions.lua. modData.tumbles counts the times a crash or hard braking threw
-- what stood on furniture down to the floor (see "Travel" below).
--
require "MELens_Parts"

MELens = MELens or {}
local M = MELens
M.Loose = M.Loose or {}
local L = M.Loose
local P = M.Parts

L.KEY = "loose"
local EPS = 0.004

-- The flat tops things can stand on, per piece, in the piece's own frame: a0 .. a1 along its length from the
-- middle, d0 .. d1 out from its wall, h above its base. Read off the boxes of tools-src/blender/rv_kit.py
-- (a box's d is the piece's depth / 2 - the box's y; dev/surface_check.py compares them with the models).
-- A bench's cushions and a washroom's rail are left out: you sit on the one and the other is a rail.
-- head: the room above a board up to the next one (the tallest thing that can stand there).
L.SURFACES = {
    kitchen = {
        { a0 = -0.46, a1 = -0.06, d0 = 0.05, d1 = 0.48, h = 0.868, name = "stove" },
        { a0 = -0.04, a1 = 0.47, d0 = 0.05, d1 = 0.48, h = 0.848, name = "counter" },
    },
    dinette = { { a0 = -0.20, a1 = 0.20, d0 = 0.04, d1 = 0.46, h = 0.597, name = "table" } },
    cabinet = { { a0 = -0.22, a1 = 0.22, d0 = 0.04, d1 = 0.48, h = 0.800, name = "top" } },
    fridge = { { a0 = -0.19, a1 = 0.19, d0 = 0.07, d1 = 0.45, h = 0.880, name = "top" } },
    wardrobe = { { a0 = -0.22, a1 = 0.22, d0 = 0.04, d1 = 0.48, h = 0.900, name = "top" } },
    bed = { { a0 = -0.68, a1 = 0.68, d0 = 0.05, d1 = 0.50, h = 0.285, name = "mattress" } },
    box = { { a0 = -0.20, a1 = 0.20, d0 = 0.05, d1 = 0.45, h = 0.400, name = "top" } },
    shelf = {
        { a0 = -0.23, a1 = 0.23, d0 = 0.03, d1 = 0.29, h = 0.090, head = 0.355, name = "shelf1" },
        { a0 = -0.23, a1 = 0.23, d0 = 0.03, d1 = 0.29, h = 0.470, head = 0.405, name = "shelf2" },
        { a0 = -0.25, a1 = 0.25, d0 = 0.03, d1 = 0.30, h = 0.900, name = "top" },
    },
    workbench = {
        { a0 = -.425, a1 = .425, d0 = .025, d1 = .375, h = .765, name = "worktop" },
    },
    medlocker = {
        { a0 = -.22, a1 = .22, d0 = .045, d1 = .285, h = .383, head = .267, name = "shelf1" },
        { a0 = -.22, a1 = .22, d0 = .045, d1 = .285, h = .673, head = .284, name = "shelf2" },
    },
    equipmentrack = {
        { a0 = -.27, a1 = .27, d0 = .035, d1 = .285, h = .052, head = .288, name = "shelf1" },
        { a0 = -.27, a1 = .27, d0 = .035, d1 = .285, h = .362, head = .288, name = "shelf2" },
        { a0 = -.27, a1 = .27, d0 = .035, d1 = .285, h = .672, head = .283, name = "shelf3" },
    },
}

------------------------------------------------------------------------------------
-- The positions in the Floor part
------------------------------------------------------------------------------------

local function key(id)
    return string.format("%d", id)
end

-- A moved fitting keeps the released coordinate frame in saved Floor records.
-- Project on read and invert on explicit placement; loading never rewrites it.
local function spotOffset(profile, index)
    if not profile or not profile.looseSpotOffsets or type(index) ~= "number"
            or index <= 0 or index ~= math.floor(index) then return nil end
    return profile.looseSpotOffsets[key(index)]
end

local function placedPosition(profile, entry)
    local offset = spotOffset(profile, entry.s)
    if not offset then return entry.x, entry.z end
    return entry.x + (offset.x or 0), entry.z + (offset.z or 0)
end

function L.floorPart(vehicle)
    return vehicle and vehicle:getPartById(P.FLOOR) or nil
end

function L.floorContainer(vehicle)
    local part = L.floorPart(vehicle)
    return part and part:getItemContainer() or nil
end

-- The table of positions (created when asked to), and the Floor part.
function L.positions(vehicle, create)
    local part = L.floorPart(vehicle)
    if not part then return nil end
    local data = part:getModData()
    local positions = data[L.KEY]
    if positions == nil and create then
        positions = {}
        data[L.KEY] = positions
    end
    return positions, part
end

function L.entry(vehicle, id)
    local positions = L.positions(vehicle, false)
    local entry = positions and positions[key(id)] or nil
    local profile = entry and M.profileFor(vehicle)
    if not entry or not spotOffset(profile, entry.s) then return entry end
    local shown = {}
    for k, value in pairs(entry) do shown[k] = value end
    shown.x, shown.z = placedPosition(profile, entry)
    return shown
end

-- How a bag or a hat looks (its texture and tint come from the item, not from its type), or nil for the
-- rest: { tx = texture, tr, tg, tb = tint }.
function L.lookOf(item)
    local clothing = item:getClothingItem()
    local visual = clothing and item:getVisual()
    if not visual then return nil end
    local texture
    if clothing:getTextureChoices():isEmpty() then
        texture = visual:getBaseTexture(clothing)
    else
        texture = visual:getTextureChoice(clothing)
    end
    local r, g, b
    if item:isCustomColor() then
        r, g, b = item:getColorRed(), item:getColorGreen(), item:getColorBlue()
    else
        local tint = visual:getTint(clothing)
        r, g, b = tint:getRedFloat(), tint:getGreenFloat(), tint:getBlueFloat()
    end
    return { tx = texture, tr = r, tg = g, tb = b }
end

-- Records where an item lies. The caller sends the part's modData (MELens.Utilities.transmit) on a server.
function L.set(vehicle, item, x, y, z, r, s)
    local positions, part = L.positions(vehicle, true)
    if not positions then return nil end
    local offset = spotOffset(M.profileFor(vehicle), s)
    if offset then x, z = x - (offset.x or 0), z - (offset.z or 0) end
    local e = { t = item:getFullType(), x = x, y = y, z = z, r = r or 0, s = s or 0 }
    local look = L.lookOf(item)
    if look then
        e.tx, e.tr, e.tg, e.tb = look.tx, look.tr, look.tg, look.tb
    end
    positions[key(item:getID())] = e
    if e.s ~= 0 then
        L.watch(vehicle)
    end
    return part
end

function L.remove(vehicle, id)
    local positions, part = L.positions(vehicle, false)
    if positions and positions[key(id)] ~= nil then
        positions[key(id)] = nil
        return part
    end
    return nil
end

local function finite(value)
    return value ~= nil and value == value and value ~= math.huge and value ~= -math.huge
end

-- A placement a client asked for, made safe before the server keeps it: the numbers are numbers, the turn is in
-- 0 .. 360, the surface exists now (a piece may have been picked up while the asker walked over), the height is
-- one of its boards' and the middle of the item lies on it. Returns x, y, z, r, s, or nil.
function L.checked(vehicle, x, y, z, r, s)
    x, y, z, r, s = tonumber(x), tonumber(y), tonumber(z), tonumber(r), tonumber(s)
    if not (finite(x) and finite(y) and finite(z) and finite(r) and finite(s)) then return nil end
    local profile = M.profileFor(vehicle)
    if not profile then return nil end
    r = math.floor(r + 0.5) % 360
    s = math.floor(s + 0.5)
    if s == 0 then
        if not L.inRoom(profile, x, z) then return nil end
        return x, profile.floorY, z, r, 0
    end
    local best
    for _, surface in ipairs(L.surfaces(vehicle, profile)) do
        if surface.s == s and math.abs(surface.y - y) < 0.04 and (best == nil or math.abs(surface.y - y) < math.abs(best.y - y)) then
            best = surface
        end
    end
    if not best then return nil end
    local pad = 0.05
    if x < best.x0 - pad or x > best.x1 + pad or z < best.z0 - pad or z > best.z1 + pad then return nil end
    return x, best.y, z, r, s
end

-- The record of an item that lies in the Floor, made if it has none (an item put there through the loot window, or
-- by an older version: its place is the one L.list works out for it). nil if the item is not in the Floor.
function L.adopt(vehicle, id)
    local entry = L.entry(vehicle, id)
    if entry then return entry end
    local profile = M.profileFor(vehicle)
    local floor = L.floorContainer(vehicle)
    local item = floor and floor:getItemById(id)
    if not profile or not item then return nil end
    for _, e in ipairs(L.list(vehicle, profile)) do
        if e.id == id then
            L.set(vehicle, item, e.x, e.y, e.z, e.r, e.s)
            return L.entry(vehicle, id)
        end
    end
    return nil
end

-- Forgets the positions of items that are not in the Floor any more (taken out through the loot window).
-- Only where the container is the truth: single player and servers; a client may not hold its items.
function L.prune(vehicle)
    if isClient() then return nil end
    local positions, part = L.positions(vehicle, false)
    local floor = part and part:getItemContainer()
    if not positions or not floor then return nil end
    local gone = {}
    for k in pairs(positions) do
        if not floor:getItemById(tonumber(k)) then
            gone[#gone + 1] = k
        end
    end
    for _, k in ipairs(gone) do
        positions[k] = nil
    end
    return #gone > 0 and part or nil
end

-- Whether anything lies on the piece at spot `index` (it cannot be picked up then).
function L.itemsOn(vehicle, index)
    local positions = L.positions(vehicle, false)
    if not positions then return false end
    for _, e in pairs(positions) do
        if type(e) == "table" and e.s == index then
            return true
        end
    end
    return false
end

------------------------------------------------------------------------------------
-- Geometry
------------------------------------------------------------------------------------

local function rectOf(spot, piece)
    local length, depth = P.footprint(spot, piece)
    local x0, x1, z0, z1 = math.huge, -math.huge, math.huge, -math.huge
    for _, a in ipairs({ -length / 2, length / 2 }) do
        for _, d in ipairs({ 0, depth }) do
            local x, z = P.spotPoint(spot, a, d)
            x0, x1 = math.min(x0, x), math.max(x1, x)
            z0, z1 = math.min(z0, z), math.max(z1, z)
        end
    end
    return x0, x1, z0, z1
end

-- Half the width and depth (passenger x and z) of the box of an item whose size is (sx, sz) at yaw 0,
-- turned `yaw` degrees. A turn is counter-clockwise in (x, z).
function L.half(sx, sz, yaw)
    local a = math.rad(yaw or 0)
    local c, s = math.abs(math.cos(a)), math.abs(math.sin(a))
    return (c * sx + s * sz) / 2, (s * sx + c * sz) / 2
end

local function inRing(ring, x, z)
    local inside = false
    local n = #ring
    local j = n
    for i = 1, n do
        local xi, zi, xj, zj = ring[i][1], ring[i][2], ring[j][1], ring[j][2]
        if (zi > z) ~= (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi then
            inside = not inside
        end
        j = i
    end
    return inside
end

-- Whether a point is inside the room (the walls' lining).
function L.inRoom(profile, x, z)
    local ring = profile.walkGrid and M.RoomRings and M.RoomRings[profile.walkGrid]
    if not ring or #ring < 3 then return true end
    return inRing(ring, x, z)
end

-- The room's bounds, for scanning it.
function L.roomBounds(profile)
    local ring = profile.walkGrid and M.RoomRings and M.RoomRings[profile.walkGrid]
    if not ring or #ring < 3 then return nil end
    local x0, x1, z0, z1 = math.huge, -math.huge, math.huge, -math.huge
    for _, c in ipairs(ring) do
        x0, x1 = math.min(x0, c[1]), math.max(x1, c[1])
        z0, z1 = math.min(z0, c[2]), math.max(z1, c[2])
    end
    return x0, x1, z0, z1
end

-- What stands on the floor and takes its room: the installed furniture, the wheel wells, the vehicle's own
-- things (a bus driver's seat). Rectangles { x0, x1, z0, z1 }.
function L.solids(vehicle, profile)
    local list = {}
    for index, spot in ipairs(profile.spots or {}) do
        local piece = P.pieceAt(P.spotPart(vehicle, index))
        if piece then
            local x0, x1, z0, z1 = rectOf(spot, piece)
            list[#list + 1] = { x0 = x0, x1 = x1, z0 = z0, z1 = z1 }
        end
    end
    for _, well in ipairs(profile.wheelWells or {}) do
        list[#list + 1] = { x0 = math.min(well.x[1], well.x[2]), x1 = math.max(well.x[1], well.x[2]),
                            z0 = math.min(well.z[1], well.z[2]), z1 = math.max(well.z[1], well.z[2]) }
    end
    for _, b in ipairs(profile.blocked or {}) do
        list[#list + 1] = { x0 = b.x1, x1 = b.x2, z0 = b.z1, z1 = b.z2 }
    end
    return list
end

-- The places things can stand, highest first, the floor last:
-- { kind = "piece" | "well" | "floor", s, y, x0, x1, z0, z1, name, spot, piece }.
function L.surfaces(vehicle, profile)
    local list = {}
    for index, spot in ipairs(profile.spots or {}) do
        local piece = P.pieceAt(P.spotPart(vehicle, index))
        local defs = piece and L.SURFACES[piece]
        -- a box with another on it has no free top
        if defs and not P.covered(vehicle, profile, index) then
            for _, d in ipairs(defs) do
                local x0, x1, z0, z1 = math.huge, -math.huge, math.huge, -math.huge
                for _, a in ipairs({ d.a0, d.a1 }) do
                    for _, dd in ipairs({ d.d0, d.d1 }) do
                        local x, z = P.spotPoint(spot, a, dd)
                        x0, x1 = math.min(x0, x), math.max(x1, x)
                        z0, z1 = math.min(z0, z), math.max(z1, z)
                    end
                end
                list[#list + 1] = { kind = "piece", s = index, name = d.name, piece = piece, spot = spot, head = d.head,
                                    y = profile.floorY + (spot.rise or 0) + d.h, x0 = x0, x1 = x1, z0 = z0, z1 = z1 }
            end
        end
    end
    for i, well in ipairs(profile.wheelWells or {}) do
        list[#list + 1] = { kind = "well", s = -i, name = "well", y = well.y[2],
                            x0 = math.min(well.x[1], well.x[2]), x1 = math.max(well.x[1], well.x[2]),
                            z0 = math.min(well.z[1], well.z[2]), z1 = math.max(well.z[1], well.z[2]) }
    end
    table.sort(list, function(a, b) return a.y > b.y end)
    list[#list + 1] = { kind = "floor", s = 0, name = "floor", y = profile.floorY }
    return list
end

-- The surface with number `s` (see the header), or nil.
function L.surfaceById(vehicle, profile, s)
    for _, surface in ipairs(L.surfaces(vehicle, profile)) do
        if surface.s == s then return surface end
    end
    return nil
end

-- How strict the fit is. An item's box is only roughly its shape, so it may reach a little into a wall's lining or
-- a piece of furniture standing on the floor, and hang over the edge of a top by a share of its size (not inside a
-- shelf's compartment, whose side boards it would go through).
L.WALL_SLACK = 0.03
L.SOLID_SLACK = 0.025
L.OVERHANG = 0.3

-- The share of an item's half size that may hang over a surface's edge.
function L.overhang(surface)
    if surface.kind == "floor" or surface.head then return 0 end
    return L.OVERHANG
end

-- Whether a box (centre x z, half sizes hx hz) fits on a surface, clear of walls and furniture:
-- true, or false and why ("wall", "furniture" or "edge").
function L.fitsSurface(vehicle, profile, surface, x, z, hx, hz)
    if surface.kind == "floor" then
        local wx, wz = math.max(0, hx - L.WALL_SLACK), math.max(0, hz - L.WALL_SLACK)
        local x0, x1, z0, z1 = x - wx, x + wx, z - wz, z + wz
        local points = { { x0, z0 }, { x0, z1 }, { x1, z0 }, { x1, z1 }, { x, z0 }, { x, z1 }, { x0, z }, { x1, z } }
        for _, c in ipairs(points) do
            if not L.inRoom(profile, c[1], c[2]) then return false, "wall" end
        end
        local sx, sz = math.max(0, hx - L.SOLID_SLACK), math.max(0, hz - L.SOLID_SLACK)
        local s0, s1, t0, t1 = x - sx, x + sx, z - sz, z + sz
        for _, r in ipairs(L.solids(vehicle, profile)) do
            if s0 < r.x1 - EPS and r.x0 < s1 - EPS and t0 < r.z1 - EPS and r.z0 < t1 - EPS then
                return false, "furniture"
            end
        end
        return true
    end
    local keep = 1 - L.overhang(surface)
    local ox, oz = hx * keep, hz * keep
    if x - ox < surface.x0 - EPS or x + ox > surface.x1 + EPS or z - oz < surface.z0 - EPS or z + oz > surface.z1 + EPS then
        return false, "edge"
    end
    -- hanging over the edge is for the open side: what hangs over may not go into the wall the piece stands against
    if keep < 1 then
        local wx, wz = math.max(0, hx - L.WALL_SLACK), math.max(0, hz - L.WALL_SLACK)
        for _, c in ipairs({ { x - wx, z - wz }, { x - wx, z + wz }, { x + wx, z - wz }, { x + wx, z + wz } }) do
            local onTop = c[1] >= surface.x0 - EPS and c[1] <= surface.x1 + EPS and c[2] >= surface.z0 - EPS and c[2] <= surface.z1 + EPS
            if not onTop and not L.inRoom(profile, c[1], c[2]) then return false, "wall" end
        end
    end
    return true
end

-- Free floor to put things that have no place (see L.list): points 0.3 apart that a small item fits at.
local pointsCache = { key = nil, points = nil }

function L.floorPoints(vehicle, profile)
    local pieces = {}
    for index = 1, #(profile.spots or {}) do
        pieces[index] = P.pieceAt(P.spotPart(vehicle, index)) or "-"
    end
    local k = tostring(vehicle:getId()) .. "|" .. table.concat(pieces, ",")
    if pointsCache.key == k then return pointsCache.points end
    local points = {}
    local x0, x1, z0, z1 = L.roomBounds(profile)
    if x0 then
        local floor = { kind = "floor", s = 0, y = profile.floorY }
        local x = x0 + 0.15
        while x < x1 do
            local z = z0 + 0.15
            while z < z1 do
                if L.fitsSurface(vehicle, profile, floor, x, z, 0.1, 0.1) then
                    points[#points + 1] = { x, z }
                end
                z = z + 0.3
            end
            x = x + 0.3
        end
    end
    pointsCache.key, pointsCache.points = k, points
    return points
end

-- Factory floor bays describe safe envelopes for real inventory, not extra items.
-- Reuse them after vanilla transfers prune the original positions. This calculation
-- stays shared and pure: no renderer sizes, item creation or saved-placement writes.
local function cargoEnvelope(profile, itemType, yaw)
    local hx, hz
    for _, bay in ipairs(profile.factoryFloor or {}) do
        if bay.t == itemType and finite(bay.hx) and finite(bay.hz) and bay.hx > 0 and bay.hz > 0 then
            local x, z = L.half(2 * bay.hx, 2 * bay.hz, (yaw or 0) - (bay.r or 0))
            hx, hz = math.max(hx or 0, x), math.max(hz or 0, z)
        end
    end
    return hx, hz
end

local function cargoFree(vehicle, profile, out, x, z, hx, hz)
    local ring = profile.walkGrid and M.RoomRings and M.RoomRings[profile.walkGrid]
    if not ring or #ring < 3 then return false end
    local x0, x1, z0, z1 = x - hx, x + hx, z - hz, z + hz
    -- Unlike ordinary small-item placement, declared freight envelopes get no wall
    -- or furniture slack. A concave lining vertex inside the box also rejects it.
    for _, c in ipairs({ {x0,z0}, {x0,z1}, {x1,z0}, {x1,z1} }) do
        if not L.inRoom(profile, c[1], c[2]) then return false end
    end
    for _, c in ipairs(ring) do
        if c[1] > x0 and c[1] < x1 and c[2] > z0 and c[2] < z1 then return false end
    end
    for _, solid in ipairs(L.solids(vehicle, profile)) do
        if x0 < solid.x1 and solid.x0 < x1 and z0 < solid.z1 and solid.z0 < z1 then return false end
    end
    for _, e in ipairs(out) do
        if e.s == 0 then
            local ex, ez = cargoEnvelope(profile, e.t, e.r)
            -- An arbitrary item has no authoritative size in shared Lua. Do not
            -- guess a native-model footprint or depend on client model loading.
            if not ex then return false end
            if math.abs(e.x - x) < ex + hx and math.abs(e.z - z) < ez + hz then return false end
        end
    end
    return true
end

-- Everything that lies in the vehicle, with where: the recorded positions, and for the Floor's items that have
-- none (dropped by an older version, or put there some other way) a place on the floor worked out from the item's
-- number, so it is the same on every client. Sorted by item number. { id, t, x, y, z, r, s, orphan }.
function L.list(vehicle, profile)
    local out, seen = {}, {}
    local positions = L.positions(vehicle, false)
    if positions then
        for k, e in pairs(positions) do
            local id = tonumber(k)
            if id and type(e) == "table" and e.t and e.x and e.z then
                local x, z = placedPosition(profile, e)
                out[#out + 1] = { id = id, t = e.t, x = x, y = e.y or profile.floorY, z = z, r = e.r or 0, s = e.s or 0,
                                  tx = e.tx, tr = e.tr, tg = e.tg, tb = e.tb }
                seen[id] = true
            end
        end
    end
    local floor = L.floorContainer(vehicle)
    if floor then
        local items = floor:getItems()
        local orphans = {}
        for i = 0, items:size() - 1 do
            local item = items:get(i)
            if not seen[item:getID()] then
                orphans[#orphans + 1] = item
            end
        end
        if #orphans > 0 then
            -- each to its own free point: from the one its number picks, on to the next free one
            table.sort(orphans, function(a, b) return a:getID() < b:getID() end)
            local points = L.floorPoints(vehicle, profile)
            local count = #points
            local used = {}
            local unknown = false
            if #(profile.factoryFloor or {}) > 0 then
                -- Reserve unknown orphan footprints conservatively before any
                -- preferred bay is assigned, regardless of their inventory order.
                for _, item in ipairs(orphans) do
                    if not cargoEnvelope(profile, item:getFullType(), 0) then unknown = true end
                end
                for _, e in ipairs(out) do
                    if e.s == 0 and not cargoEnvelope(profile, e.t, e.r) then unknown = true end
                end
            end
            for k, item in ipairs(orphans) do
                local id, itemType = item:getID(), item:getFullType()
                local px, pz, yaw
                local hx, hz = cargoEnvelope(profile, itemType, 0)
                if hx and not unknown then
                    for _, bay in ipairs(profile.factoryFloor) do
                        if bay.t == itemType and finite(bay.x) and finite(bay.z) then
                            local bx, bz = cargoEnvelope(profile, itemType, bay.r)
                            if cargoFree(vehicle, profile, out, bay.x, bay.z, bx, bz) then
                                px, pz, yaw = bay.x, bay.z, bay.r or 0
                                break
                            end
                        end
                    end
                end
                if px == nil and count > 0 and k <= count then
                    local index = id % count + 1
                    for _ = 1, count do
                        local point = points[index]
                        -- Known freight that cannot use a bay still needs its full
                        -- envelope at the fallback grid point. Unknown mixed cargo
                        -- retains the existing generic behaviour; no size is guessed.
                        if not used[index] and (not hx or unknown or cargoFree(vehicle, profile, out, point[1], point[2], hx, hz)) then
                            used[index] = true
                            px, pz, yaw = point[1], point[2], 0
                            break
                        end
                        index = index % count + 1
                    end
                end
                if px ~= nil then
                    local look = L.lookOf(item) or {}
                    out[#out + 1] = { id = id, t = itemType, x = px, y = profile.floorY,
                                      z = pz, r = yaw, s = 0, orphan = true,
                                      tx = look.tx, tr = look.tr, tg = look.tg, tb = look.tb }
                end
            end
        end
    end
    table.sort(out, function(a, b) return a.id < b.id end)
    return out
end

-- A position for an item dropped at (x, z): there, or the nearest free floor with room for a small thing, so
-- several dropped at one spot do not lie on top of each other. extra: places { x, z } already promised to
-- other items (their actions have not recorded them yet).
function L.dropSpot(vehicle, profile, x, z, id, extra)
    local floor = { kind = "floor", s = 0, y = profile.floorY }
    local taken = {}
    for _, e in ipairs(L.list(vehicle, profile)) do
        if e.s == 0 then taken[#taken + 1] = e end
    end
    for _, e in ipairs(extra or {}) do
        taken[#taken + 1] = e
    end
    local function free(px, pz)
        if not L.fitsSurface(vehicle, profile, floor, px, pz, 0.08, 0.08) then return false end
        for _, e in ipairs(taken) do
            if math.abs(e.x - px) < 0.2 and math.abs(e.z - pz) < 0.2 then return false end
        end
        return true
    end
    -- a little scatter by the item's number, then rings round the spot
    local angle0 = ((id or 0) % 8) * math.pi / 4
    for ring = 0, 8 do
        local r = ring * 0.16
        local steps = ring == 0 and 1 or ring * 6
        for step = 0, steps - 1 do
            local a = angle0 + step * 2 * math.pi / steps
            local px, pz = x + r * math.cos(a), z + r * math.sin(a)
            if free(px, pz) then return px, pz end
        end
    end
    return x, z
end

-- Furniture was put at spot `index`. What lay on the floor where it stands, and what lay on a piece that has
-- another on top of it now, would be buried: it goes to the nearest free floor. Returns the Floor part if
-- anything moved (the caller sends its data on a server), else nil.
function L.displace(vehicle, index)
    local profile = M.profileFor(vehicle)
    local positions, part = L.positions(vehicle, false)
    if not profile or not positions or not part then return nil end
    local spot = profile.spots and profile.spots[index]
    local piece = spot and P.pieceAt(P.spotPart(vehicle, index))
    local x0, x1, z0, z1
    if spot and piece then
        x0, x1, z0, z1 = rectOf(spot, piece)
    end
    local ids = {}
    for k, e in pairs(positions) do
        if type(e) == "table" and e.x and e.z and tonumber(k) then
            local buried = false
            if e.s == 0 and x0 then
                buried = e.x > x0 - 0.04 and e.x < x1 + 0.04 and e.z > z0 - 0.04 and e.z < z1 + 0.04
            elseif e.s and e.s > 0 and P.covered(vehicle, profile, e.s) then
                buried = true
            end
            if buried then ids[#ids + 1] = tonumber(k) end
        end
    end
    if #ids == 0 then return nil end
    table.sort(ids)
    for _, id in ipairs(ids) do
        local e = positions[key(id)]
        local px, pz = placedPosition(profile, e)
        local x, z = L.dropSpot(vehicle, profile, px, pz, id)
        e.x, e.z, e.y, e.s = x, z, profile.floorY, 0
    end
    return part
end

------------------------------------------------------------------------------------
-- Travel: a crash, or braking hard, throws what stands on the furniture and the wheel wells down to the floor
-- (sandbox option LooseWhileDriving: 1 they stay put, 2 crashes, 3 crashes and hard braking). Only where the game
-- runs vehicle logic (single player, a server); every client sees the new places, and MELens_LooseView.lua makes
-- the clatter. The speed is looked at four times a second, and only for vehicles with something up on a surface.
------------------------------------------------------------------------------------

L.CRASH_DROP = 10        -- km/h lost within a quarter of a second: a collision (hard braking loses 5 at the most)
L.BRAKE_DROP = 5         -- km/h lost within a quarter of a second: braking hard (20 km/h a second)
local SAMPLE_MS = 250
local watched = {}       -- vehicle id -> vehicle
local speeds = {}        -- vehicle id -> { t = when it was looked at (ms), v = km/h }

function L.watch(vehicle)
    if not isClient() then
        watched[vehicle:getId()] = vehicle
    end
end

-- Whether anything stands up on a surface (not on the floor).
function L.hasRaised(vehicle)
    local positions = L.positions(vehicle, false)
    if not positions then return false end
    for _, e in pairs(positions) do
        if type(e) == "table" and e.s and e.s ~= 0 then
            return true
        end
    end
    return false
end

-- Everything that stood on a surface lies on the floor, near where it stood. Returns whether anything moved.
function L.tumble(vehicle)
    local profile = M.profileFor(vehicle)
    local positions, part = L.positions(vehicle, false)
    if not profile or not positions or not part then return false end
    local ids = {}
    for k, e in pairs(positions) do
        if type(e) == "table" and e.s and e.s ~= 0 and tonumber(k) then
            ids[#ids + 1] = tonumber(k)
        end
    end
    if #ids == 0 then return false end
    table.sort(ids)
    for _, id in ipairs(ids) do
        local e = positions[key(id)]
        local px, pz = placedPosition(profile, e)
        local x, z = L.dropSpot(vehicle, profile, px, pz, id)
        e.x, e.z, e.y, e.s = x, z, profile.floorY, 0
    end
    local data = part:getModData()
    data.tumbles = (tonumber(data.tumbles) or 0) + 1
    if isServer() then
        vehicle:transmitPartModData(part)
    end
    return true
end

-- Whether the speed lost between two looks was enough to throw things down: lost km/h, the mode (1, 2 or 3).
function L.throws(lost, mode)
    if mode >= 3 then return lost >= L.BRAKE_DROP end
    if mode == 2 then return lost >= L.CRASH_DROP end
    return false
end

-- One look at a vehicle's speed (ms: the time; pace: how many times faster than real time the game runs). Returns
-- whether things were thrown down.
function L.look(id, vehicle, ms, mode, pace)
    local seen = speeds[id]
    if seen and ms >= seen.t and ms - seen.t < SAMPLE_MS then return false end
    local speed = vehicle:getCurrentAbsoluteSpeedKmHour()
    if seen == nil or ms < seen.t or ms - seen.t > 1000 then
        speeds[id] = { t = ms, v = speed }                       -- a first look (or a pause): nothing to compare
        return false
    end
    local lost = (seen.v - speed) / pace
    seen.t, seen.v = ms, speed
    if L.throws(lost, mode) and L.tumble(vehicle) then
        speeds[id] = nil
        return true
    end
    return false
end

-- (Kahlua has no next(): the first turn of pairs says whether there is anything.)
local function anyWatched()
    for _ in pairs(watched) do
        return true
    end
    return false
end

function L.onTick()
    if isClient() or not anyWatched() then return end
    local mode = M.sandbox("LooseWhileDriving", 2)
    if mode <= 1 then return end
    local now = getTimestampMs()
    local pace = 1
    local time = getGameTime and getGameTime()
    if time and time.getTrueMultiplier then pace = math.max(1, time:getTrueMultiplier()) end
    for id, vehicle in pairs(watched) do
        L.look(id, vehicle, now, mode, pace)
    end
end

-- Once a minute: which of the loaded vehicles have something standing up on a surface (a server or single player
-- starts with none, and a vehicle that loads later must be found).
function L.scanWatched()
    if isClient() then return end
    local cell = getCell()
    if not cell then return end
    local now = {}
    local it = cell:getVehicles():iterator()
    while it:hasNext() do
        local vehicle = it:next()
        if M.profileFor(vehicle) and L.hasRaised(vehicle) then
            now[vehicle:getId()] = vehicle
        end
    end
    watched = now
    for id in pairs(speeds) do
        if not now[id] then speeds[id] = nil end
    end
end

------------------------------------------------------------------------------------
-- A server forgets the places of what was taken out of the Floor through the loot window (the vanilla transfer
-- knows nothing of them); once a minute for the vehicles it has loaded. Single player prunes in
-- MELens_LooseView.lua.
------------------------------------------------------------------------------------

function L.pruneLoaded()
    if not isServer() then return end
    local cell = getCell()
    if not cell then return end
    local it = cell:getVehicles():iterator()
    while it:hasNext() do
        local vehicle = it:next()
        if M.profileFor(vehicle) then
            local part = L.prune(vehicle)
            if part then
                vehicle:transmitPartModData(part)
            end
        end
    end
end

if not L.hooked then
    L.hooked = true
    Events.EveryOneMinute.Add(function() L.pruneLoaded() end)
end

if not L.shakeHooked then
    L.shakeHooked = true
    Events.OnTick.Add(function() L.onTick() end)
    Events.EveryOneMinute.Add(function() L.scanWatched() end)
end

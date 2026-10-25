--
-- ME: LENS parts, added to each supported vehicle's script when the scripts load (see
-- MELens.addStandingPositions), so KI5's files stay untouched and vehicles in existing
-- saves get them too (the game creates missing parts on load):
--
--   MELensSpot1..n    furniture spots. The installed RV furniture item's model is drawn
--                     there and the part's container is its storage, in reach when you
--                     stand at it, like any furniture.
--   MELensShell       ME: LENS' inside (floor, walls, wheel wells, utility panel)
--   MELensFloor       the floor inside, a container like the ground outside
--   MELensGenerator   the petrol generator: powers the fridge, stove and heater, and
--                     charges the vehicle's battery, which runs the lights
--   MELensWaterTank   fresh water for the kitchen and washroom taps
--   MELensOven        the kitchen's oven
--
-- Shared: the part functions run wherever the game runs vehicle Lua (single player,
-- or the server in multiplayer).
--
require "MELens_RVKit"
require "MELens_Java"

MELens = MELens or {}
local M = MELens
M.Parts = M.Parts or {}
local P = M.Parts

-- A sandbox option of ME: LENS (media/sandbox-options.txt), or `default` before the sandbox is read.
function M.sandbox(name, default)
    local vars = SandboxVars and SandboxVars.MELens
    local value = vars and vars[name]
    if value == nil then return default end
    return value
end

P.SPOT = "MELensSpot"
P.SHELL = "MELensShell"
P.FLOOR = "MELensFloor"
P.GENERATOR = "MELensGenerator"
P.WATER = "MELensWaterTank"
P.OVEN = "MELensOven"
P.REACH = 0.45        -- tiles between you and a piece's front for its storage and use
P.INITIALIZED_KEY = "MELensInitialized"
P.EMPTY_ITEM = "Base.MELensRV_Seat" -- harmless repair placeholder; keeps empty spots serializable

------------------------------------------------------------------------------------
-- Furniture pieces (tools-src/blender/rv_kit.py makes the models and MELens_RVKit.lua)
------------------------------------------------------------------------------------

P.PIECES = { "bed", "dinette", "kitchen", "fridge", "cabinet", "wardrobe", "washroom", "heater", "shelf",
             "busseat", "busseat2", "box", "stretcher", "metalcase", "safe",
             "parcels", "medlocker", "medbench", "equipmentrack", "workbench" }

-- Cargo spots (a box truck's) take boxes and nothing else, other spots everything but
-- boxes, so a part only declares the models it can show.
local CARGO_PIECES = { "box" }
local FURNITURE = {}
for _, piece in ipairs(P.PIECES) do
    if piece ~= "box" then table.insert(FURNITURE, piece) end
end

function P.piecesFor(spot)
    return spot and (spot.pieces or (spot.cargo and CARGO_PIECES)) or FURNITURE
end

-- Bus seats face the vehicle's front on either wall: on a right-hand wall (whose length
-- runs to the back) their mirrored model stands there.
local MIRRORED = { busseat = true, busseat2 = true }

local itemTypes, pieceOfType = {}, {}
for _, piece in ipairs(P.PIECES) do
    local full = "Base.MELensRV_" .. piece:sub(1, 1):upper() .. piece:sub(2)
    itemTypes[piece] = full
    pieceOfType[full] = piece
end

function P.itemType(piece)
    return itemTypes[piece]
end

function P.pieceOfItem(item)
    return item and pieceOfType[item:getFullType()] or nil
end

function P.kit(piece)
    return piece and M.RVKit and M.RVKit[piece] or nil
end

-- Only new emergency/service conversions receive factory fittings. Cargo vans
-- keep their native trunk distributions; no residential furniture is invented.
P.VEHICLE_USE = {
    ["Base.VanAmbulance"] = { fittings = { [1] = "stretcher", [2] = "metalcase" },
        loot = { metalcase = "MedicalStorageTools" } },
    ["Base.90fordF350ambulance"] = { fittings = { [1] = "stretcher", [3] = "metalcase" },
        loot = { metalcase = "MedicalStorageTools" } },
    ["Base.86fordE150med"] = { fittings = { [1] = "stretcher", [2] = "metalcase" },
        loot = { metalcase = "MedicalStorageTools" } },
    ["Base.90fordF350SWAT"] = { fittings = { [3] = "metalcase" } },
    ["Base.87fordF700swat"] = { fittings = { [3] = "metalcase" } },
    ["Base.87fordF700bank"] = { fittings = { [3] = "metalcase" } },
    ["Base.StepVan_LouisvilleSWAT"] = { fittings = { [3] = "metalcase" } },
    ["Base.85chevyStepVanSWAT"] = { fittings = { [3] = "metalcase" } },
}

function P.vehicleUse(vehicle)
    local script = vehicle and vehicle:getScript()
    local profile = M.profileFor(vehicle)
    return profile and profile.factoryUse or (script and P.VEHICLE_USE[script:getFullName()] or nil)
end

function P.factoryPiece(vehicle, index, spot)
    local profile = M.profileFor(vehicle)
    if profile and profile.factoryLayout then
        return spot and not spot.empty and spot.default or nil
    end
    local use = P.vehicleUse(vehicle)
    return use and use.fittings and use.fittings[index] or (spot and not spot.empty and spot.default or nil)
end

-- The piece standing at a spot part, or nil.
function P.pieceAt(part)
    return part and P.pieceOfItem(part:getInventoryItem()) or nil
end

-- The model file a piece uses at a spot: a mirrored one on a right-hand wall.
function P.modelFile(piece, spot)
    if MIRRORED[piece] and spot.wall == "right" then
        return "MELensRV_" .. piece .. "_r"
    end
    return "MELensRV_" .. piece
end

------------------------------------------------------------------------------------
-- Spot geometry (passenger space)
------------------------------------------------------------------------------------

-- How a piece stands against each wall: the part model's rotation about the vertical
-- axis (degrees), the direction its length runs (the model's +x) and the direction it
-- faces (away from the wall), in passenger space (x, z).
P.WALLS = {
    front = { rotate = 0, along = { -1, 0 }, out = { 0, -1 } },
    back = { rotate = 180, along = { 1, 0 }, out = { 0, 1 } },
    left = { rotate = 90, along = { 0, 1 }, out = { -1, 0 } },
    right = { rotate = -90, along = { 0, -1 }, out = { 1, 0 } },
}
P.ROTATE_SIGN = 1

function P.spotIndex(part)
    local id = part and part:getId()
    return id and tonumber(string.match(id, "^" .. P.SPOT .. "(%d+)$")) or nil
end

function P.spotPart(vehicle, index)
    return vehicle and vehicle:getPartById(P.SPOT .. index) or nil
end

-- The profile's spot for a spot part.
function P.spotOf(vehicle, part)
    local profile = M.profileFor(vehicle)
    local index = P.spotIndex(part)
    return profile and index and profile.spots and profile.spots[index] or nil, profile
end

-- A point on a piece at a spot: `a` along its length from its middle, `d` out from
-- the wall (0 at its back).
function P.spotPoint(spot, a, d)
    local w = P.WALLS[spot.wall]
    return spot.x + w.along[1] * a + w.out[1] * d, spot.z + w.along[2] * a + w.out[2] * d
end

-- (x, z) in a spot's frame: along its length from the middle, and out from the wall.
function P.toSpot(spot, x, z)
    local w = P.WALLS[spot.wall]
    local dx, dz = x - spot.x, z - spot.z
    return dx * w.along[1] + dz * w.along[2], dx * w.out[1] + dz * w.out[2]
end

-- The footprint of what stands at a spot: the piece's own size, or the whole spot.
function P.footprint(spot, piece)
    local kit = P.kit(piece)
    if kit then
        return kit.width, kit.depth, kit.height
    end
    return spot.length, spot.depth, 0.05
end

-- Distance from (x, z) to the footprint (0 on it).
function P.distanceTo(spot, piece, x, z)
    local length, depth = P.footprint(spot, piece)
    local a, d = P.toSpot(spot, x, z)
    local da = math.max(0, math.abs(a) - length / 2)
    local dd = math.max(0, -d, d - depth)
    return math.sqrt(da * da + dd * dd)
end

-- Whether a piece fits a spot: its size; beds, benches and bus seats only where the
-- vehicle has seats for them (you lie and sit on those), bus seats along a side wall.
function P.fits(spot, piece)
    local kit = P.kit(piece)
    if not kit or not spot then return false end
    if spot.pieces then
        local declared = false
        for _, name in ipairs(spot.pieces) do if name == piece then declared = true;break end end
        if not declared then return false end
    end
    if (kit.kind == "box") ~= (spot.cargo == true) then
        return false          -- boxes only at cargo spots, and only boxes there
    end
    if kit.width > spot.length + 0.005 or kit.depth > spot.depth + 0.005 then
        return false
    end
    if kit.kind == "bed" or kit.kind == "seat" then
        if not spot.seats or #spot.seats == 0 then return false end
        if MIRRORED[piece] and spot.wall ~= "left" and spot.wall ~= "right" then return false end
    end
    return true
end

-- What stands in a vehicle now: { [spot index] = piece }.
function P.standing(vehicle, profile)
    local list = {}
    for index = 1, #(profile.spots or {}) do
        local piece = P.pieceAt(P.spotPart(vehicle, index))
        if piece then
            list[index] = piece
        end
    end
    return list
end

-- The floor rectangle (passenger x, z) and the band of height a piece takes at a spot.
local function volume(spot, piece)
    local length, depth, height = P.footprint(spot, piece)
    local x0, x1, z0, z1 = math.huge, -math.huge, math.huge, -math.huge
    for _, a in ipairs({ -length / 2, length / 2 }) do
        for _, d in ipairs({ 0, depth }) do
            local x, z = P.spotPoint(spot, a, d)
            x0, x1 = math.min(x0, x), math.max(x1, x)
            z0, z1 = math.min(z0, z), math.max(z1, z)
        end
    end
    local rise = spot.rise or 0
    return x0, x1, z0, z1, rise, rise + height
end

P.CLEARANCE = 0.005      -- pieces may share this much (they touch), no more

-- Whether a piece placed at a spot would stand clear of everything already standing (from
-- P.standing): the pieces are solid models, two of them must not share room. A spot fits a
-- piece up to its whole room, so neighbouring rooms can meet at a corner.
function P.roomFor(profile, standing, index, piece)
    local spot = profile.spots[index]
    local ax0, ax1, az0, az1, ay0, ay1 = volume(spot, piece)
    local c = P.CLEARANCE
    for other, there in pairs(standing) do
        if other ~= index then
            local bx0, bx1, bz0, bz1, by0, by1 = volume(profile.spots[other], there)
            if ax0 < bx1 - c and bx0 < ax1 - c and az0 < bz1 - c and bz0 < az1 - c
                    and ay0 < by1 - c and by0 < ay1 - c then
                return false
            end
        end
    end
    return true
end

------------------------------------------------------------------------------------
-- Stacked boxes: every box is its own spot; the spot above one in the same column (level
-- + 1, `rise` higher) rests on it.
------------------------------------------------------------------------------------

-- Works out, once per profile, which spot each stacked spot rests on (spot._under) and
-- which rests on it (spot._over).
local function links(profile)
    if profile._linked then return end
    profile._linked = true
    local column = {}
    local function key(spot)
        return string.format("%s|%.3f|%.3f", spot.wall, spot.x, spot.z)
    end
    for index, spot in ipairs(profile.spots or {}) do
        if spot.level then
            local k = key(spot)
            column[k] = column[k] or {}
            column[k][spot.level] = index
        end
    end
    for _, spot in ipairs(profile.spots or {}) do
        if spot.level then
            local levels = column[key(spot)]
            spot._under = levels[spot.level - 1]
            spot._over = levels[spot.level + 1]
        end
    end
end

-- Whether a spot has something to stand on: the floor, or a box at the spot below it.
function P.supported(vehicle, profile, index)
    links(profile)
    local under = profile.spots[index]._under
    return under == nil or P.pieceAt(P.spotPart(vehicle, under)) ~= nil
end

-- Whether another box rests on the one here (so taking this one would leave it floating).
function P.covered(vehicle, profile, index)
    links(profile)
    local over = profile.spots[index]._over
    return over ~= nil and P.pieceAt(P.spotPart(vehicle, over)) ~= nil
end

-- A box with nothing under it (a save from an earlier layout, or the box below taken some other way)
-- falls to the lowest free place of its column and takes what it holds with it. Runs where the game runs
-- vehicle Lua (single player or the server), as the part's init and update.
function P.settleBox(vehicle, part)
    if isClient() or P.pieceAt(part) ~= "box" then return false end
    local profile, index = M.profileFor(vehicle), P.spotIndex(part)
    if not profile or not index then return false end
    links(profile)
    if profile.spots[index]._under == nil or P.supported(vehicle, profile, index) then return false end
    local target = profile.spots[index]._under
    while true do
        local below = profile.spots[target]._under
        local lower = below and P.spotPart(vehicle, below)
        if not lower or lower:getInventoryItem() then break end
        target = below
    end
    local to = P.spotPart(vehicle, target)
    if not to or to:getInventoryItem() then return false end
    local source = part:getItemContainer()
    local held = {}
    for i = 0, (source and source:getItems():size() or 0) - 1 do
        held[#held + 1] = source:getItems():get(i)
    end
    to:setInventoryItem(part:getInventoryItem())
    P.applyPiece(vehicle, to)
    local into = to:getItemContainer()
    for _, item in ipairs(held) do
        source:Remove(item)
        sendRemoveItemFromContainer(source, item)
        into:AddItem(item)
        sendAddItemToContainer(into, item)
    end
    part:setInventoryItem(nil)
    P.applyPiece(vehicle, part)
    vehicle:transmitPartItem(to)
    vehicle:transmitPartItem(part)
    return true
end

------------------------------------------------------------------------------------
-- Lying and sitting on the furniture
--
-- Beds use the game's get-in, awake, asleep and get-out clips. Their mattress
-- contact is near 0.30 above the origin; the engine draws vehicle occupants at
-- 1.5 scale. Align the support surface (not the pelvis) with the mattress.
-- Benches retain damnlib's pose when it is enabled. Otherwise use the vanilla
-- Bob_SatChair clip. Clip placement is measured with dev/xpose.py.
------------------------------------------------------------------------------------

local HEAD = { front = { 0, 1 }, back = { 0, -1 }, left = { 1, 0 }, right = { -1, 0 } }

function P.hasDamnSeats()
    local mods = getActivatedMods and getActivatedMods()
    return mods and mods:contains("damnlib") or false
end

local function benchPose(x, y, z, turn)
    if P.hasDamnSeats() then return { pose = "facingLeft", x = x, y = y, z = z, turn = turn } end
    -- Vanilla's pelvis starts 0.3154 above its origin, and its feet face -Z.
    -- The old pose's pelvis is at the origin with feet facing +X. Vehicle
    -- occupants render at 1.5 scale; compensate without moving saved furniture.
    return { pose = "MELensSeat", x = x, y = y - 0.3154 * 1.5, z = z, turn = turn - math.pi / 2 }
end

-- Which seat of a spot a KI5 seat id is (1, 2, ...), and the spot.
local function seatInSpot(vehicle, profile, id)
    for index, spot in ipairs(profile.spots or {}) do
        for k, sid in ipairs(spot.seats or {}) do
            if sid == id then
                local part = P.spotPart(vehicle, index)
                local piece = P.pieceAt(part) or (not part and P.factoryPiece(vehicle, index, spot))
                if piece then return spot, index, k end
            end
        end
    end
    return nil
end

-- The pose for a KI5 seat on whatever stands at its spot: { pose, x, y, z, turn }, or
-- nil when nothing there is to lie or sit on.
function P.seatPose(vehicle, profile, id)
    local spot, index, k = seatInSpot(vehicle, profile, id)
    if not spot then return nil end
    local piece = P.pieceAt(P.spotPart(vehicle, index))
    if not piece and vehicle:getPartById(P.SPOT .. index) == nil then
        piece = P.factoryPiece(vehicle, index, spot)       -- before the parts exist (the script's first load)
    end
    local floor = profile.floorY
    local kit = P.kit(piece)
    if kit and kit.kind == "bed" and k == 1 then
        local head = HEAD[spot.head or ((spot.wall == "left" or spot.wall == "right") and "front" or "right")]
        local cx, cz = P.spotPoint(spot, 0, 0.272)
        local out = P.WALLS[spot.wall].out
        return { pose = "MELensBed", kind = "bed", x = cx + 0.45 * head[1], y = floor + kit.height - 0.02 - 0.30 * 1.5,
                 z = cz + 0.45 * head[2], turn = math.atan2(head[1], -head[2]),
                 headX = head[1], headZ = head[2], outX = out[1], outZ = out[2] }
    elseif piece == "dinette" and k <= 2 then
        local w = P.WALLS[spot.wall]
        local sign = k == 1 and 1 or -1
        local x, z = P.spotPoint(spot, sign * 0.34, 0.27)
        local fx, fz = -sign * w.along[1], -sign * w.along[2]
        return benchPose(x, floor + 0.395, z, math.atan2(fz, fx))
    elseif piece == "medbench" and k <= 2 then
        local x,z = P.spotPoint(spot, (k - 1.5) * .52, .22)
        local out = P.WALLS[spot.wall].out
        return benchPose(x, floor + .395, z, math.atan2(out[2], out[1]))
    elseif (piece == "busseat" and k == 1) or (piece == "busseat2" and k <= 2) then
        local middle = piece == "busseat" and 0 or (k - 1.5) * 0.75
        local x, z = P.spotPoint(spot, middle, 0.40)
        return benchPose(x, floor + 0.415, z - 0.155, math.pi / 2)
    end
    return nil
end

-- Where a KI5 seat puts you (passenger x, z): its pose, or KI5's own position.
function P.seatPoint(vehicle, profile, id)
    local script = vehicle:getScript()
    local index = script:getPassengerIndex(id)
    if index < 0 then return nil end
    local pose = P.seatPose(vehicle, profile, id)
    local offset = script:getPassenger(index):getPositionById("inside"):getOffset()
    return index, pose and pose.x or offset:x(), pose and pose.z or offset:z()
end

-- What a seat is for with what stands there: "bed", "seat" or nil.
function P.seatKindAt(vehicle, profile, id)
    local pose = P.seatPose(vehicle, profile, id)
    return pose and (pose.kind or "seat") or nil
end

------------------------------------------------------------------------------------
-- Where a character is inside
------------------------------------------------------------------------------------

local tmpVec = nil

-- (x, z) in passenger space of a character inside the vehicle (standing or seated).
function P.characterAt(vehicle, chr)
    if not vehicle or not chr or chr:getVehicle() ~= vehicle then return nil end
    local seat = vehicle:getSeat(chr)
    if seat < 0 then return nil end
    tmpVec = tmpVec or Vector3f.new()
    local pos = vehicle:getPassengerLocalPos(seat, tmpVec)
    if not pos then return nil end
    local offset = vehicle:getScript():getModel():getOffset()
    return pos:x() - offset:x(), pos:z() - offset:z()
end

-- Whether a character can reach a spot's piece: standing close to it, or sitting on it.
function P.canReach(vehicle, part, chr)
    local spot = P.spotOf(vehicle, part)
    if not spot then return false end
    local seat = vehicle:getSeat(chr)
    for _, id in ipairs(spot.seats or {}) do
        local index = vehicle:getScript():getPassengerIndex(id)
        if index >= 0 and index == seat then
            return true
        end
    end
    local x, z = P.characterAt(vehicle, chr)
    return x ~= nil and P.distanceTo(spot, P.pieceAt(part), x, z) <= P.REACH
end

------------------------------------------------------------------------------------
-- Part functions (vehicle script lua / container / install tables)
------------------------------------------------------------------------------------

-- Storage of a piece: in reach. Keep saved contents recoverable even if their
-- furniture item is absent (an old layout or another mod removed the item).
function P.containerTest(vehicle, part, chr)
    local kit = P.kit(P.pieceAt(part))
    local container = part:getItemContainer()
    local hasContents = container ~= nil and not container:isEmpty()
    return ((kit ~= nil and (kit.capacity or 0) > 0) or hasContents) and P.canReach(vehicle, part, chr)
end

-- Whether a stack rule holds for a spot part (no profile or a spot outside any stack: yes).
local function stackRule(vehicle, part, rule)
    local profile = M.profileFor(vehicle)
    local index = P.spotIndex(part)
    return profile == nil or index == nil or rule(vehicle, profile, index)
end

-- Placing and picking up furniture happens from inside; a box needs the one below it, and
-- a box with another on top stays.
function P.placeTest(vehicle, part, chr)
    return P.spotIndex(part) ~= nil and part:getInventoryItem() == nil and chr ~= nil and chr:getVehicle() == vehicle
        and stackRule(vehicle, part, P.supported)
end

local function notCovered(vehicle, profile, index)
    return not P.covered(vehicle, profile, index)
end

-- Nothing lies on the piece (MELens_Loose.lua): it would be left floating.
local function nothingOn(vehicle, profile, index)
    local loose = M.Loose
    return not (loose and loose.itemsOn(vehicle, index))
end

function P.pickUpTest(vehicle, part, chr)
    local container = part:getItemContainer()
    return part:getInventoryItem() ~= nil and (container == nil or container:isEmpty())
        and chr ~= nil and chr:getVehicle() == vehicle and not P.seatTaken(vehicle, part)
        and stackRule(vehicle, part, notCovered) and stackRule(vehicle, part, nothingOn)
end

-- Someone sitting or lying on a piece.
function P.seatTaken(vehicle, part)
    local spot = P.spotOf(vehicle, part)
    for _, id in ipairs(spot and spot.seats or {}) do
        local index = vehicle:getScript():getPassengerIndex(id)
        if index >= 0 and vehicle:getCharacter(index) then
            return true
        end
    end
    return false
end

-- The floor inside, like the ground outside: in reach anywhere inside (not from the
-- vehicle's own seats, which have their own). The loot window also needs one container
-- to list, or it breaks.
function P.floorTest(vehicle, part, chr)
    if not chr or chr:getVehicle() ~= vehicle then return false end
    local profile = M.profileFor(vehicle)
    if not profile then return false end
    local seat = vehicle:getSeat(chr)
    for _, id in ipairs(profile.vanillaSeats or {}) do
        if vehicle:getScript():getPassengerIndex(id) == seat then return false end
    end
    return true
end

-- KI5's own cargo storage in a vehicle whose cargo is ME: LENS' boxes: hidden, unless
-- it still holds something (a save from before), and then only from inside.
function P.ki5StorageTest(vehicle, part, chr)
    local container = part:getItemContainer()
    return container ~= nil and not container:isEmpty()
        and chr ~= nil and chr:getVehicle() == vehicle
end

-- Shows the installed piece's model (each spot declares one model per piece, and a
-- ghost of each for placing furniture) and hides the rest. Only the vehicle you are in
-- draws them, so clients also call this for it (in multiplayer the server changes the
-- furniture). `shown` remembers what each part shows, as changing a vehicle's models
-- rebuilds its model instances. `ghost` sets the piece previewed there (placing
-- furniture; false clears it); without it the preview stays as it is.
P.shown = setmetatable({}, { __mode = "k" })
P.ghosts = setmetatable({}, { __mode = "k" })

-- The engine can rebuild container stats after installing, loading or repairing a part.
-- Repair both the installed item's source capacity and the live container, without replacing either.
function P.syncCapacity(part)
    if not part then return end
    local item = part:getInventoryItem()
    if item and item:getFullType() == P.EMPTY_ITEM and not isClient() then
        -- The engine clears a loaded installed item when the script has no itemType.
        -- A placeholder gives bare slots a save contract without furnishing them on repair().
        part:setInventoryItem(nil)
        item = nil
        if isServer() then part:getVehicle():transmitPartItem(part) end
    end
    local kit = P.kit(P.pieceAt(part))
    local capacity = kit and kit.capacity or 0
    local container = part:getItemContainer()
    if item and item:getMaxCapacity() ~= capacity then item:setMaxCapacity(capacity) end
    if container and container:getCapacity() ~= capacity then part:setContainerCapacity(capacity) end
end

-- Added furniture seats are installed only while an appropriate piece exists at their spot.
function P.syncFurnitureSeats(vehicle)
    local profile = M.profileFor(vehicle)
    if isClient() or not profile then return end
    for _, id in ipairs(profile.extraSeats or {}) do
        local seat = vehicle:getPartById("Seat" .. id)
        if seat then
            local installed = P.seatPose(vehicle, profile, id) ~= nil
            local item = seat:getInventoryItem()
            if installed and not item then
                M.initStandingPart(vehicle, seat)
                if isServer() then vehicle:transmitPartItem(seat) end
            elseif not installed and item then
                seat:setInventoryItem(nil)
                if isServer() then vehicle:transmitPartItem(seat) end
            end
        end
    end
end

function P.showPiece(part, force, ghost)
    if not part then return end
    local rv = M.java()
    if rv then
        local vehicle = part:getVehicle()
        if vehicle:getPartById(part:getId()) ~= part then
            P.shown[part], P.ghosts[part] = nil, nil
            return
        end
    end
    P.syncCapacity(part)
    if not rv then return end
    if ghost ~= nil then
        P.ghosts[part] = ghost or nil
    end
    local piece = P.pieceAt(part) or ""
    local preview = P.ghosts[part]
    local key = piece .. "|" .. (preview or "")
    local stale = rv.clearStalePartModels and rv.clearStalePartModels(part)
    if not force and not stale and P.shown[part] == key then
        -- Engine model lists can be cleared/rebound while the installed item and
        -- this Lua cache survive. Inspect actual current-part ownership as well.
        local valid = not rv.isPartModelVisible
            or ((piece == "" or rv.isPartModelVisible(part, piece))
                and (not preview or rv.isPartModelVisible(part, "ghost_" .. preview)))
        if valid then return end
    end
    -- only the models this spot declares (a cargo spot has just the box)
    for _, name in ipairs(P.piecesFor(P.spotOf(part:getVehicle(), part))) do
        part:setModelVisible(name, name == piece)
        part:setModelVisible("ghost_" .. name, name == preview)
    end
    P.shown[part] = key
end

-- Container size and type follow the piece (the type names it in the loot window).
function P.applyPiece(vehicle, part)
    local piece = P.pieceAt(part)
    P.syncCapacity(part)
    local container = part:getItemContainer()
    if container then
        container:setType(piece and ("MELensRV_" .. piece) or part:getId())
        if piece == "fridge" and M.Utilities then
            M.Utilities.updateFridge(vehicle, part, 0)
        else
            container:setCustomTemperature(0)
        end
    end
    P.showPiece(part, true)
    P.syncFurnitureSeats(vehicle)
end

-- A new vehicle (or one from before ME: LENS) is furnished with its default layout (a spot
-- marked `empty` is sized for its default piece but starts bare, to leave room to walk).
function P.createSpot(vehicle, part)
    -- The server creates furniture and loot. A repeated create callback must not
    -- replace an installed item, refill saved storage or furnish a cleared spot.
    if isClient() then return end
    local data = part:getModData()
    local container = part:getItemContainer()
    local placeholder = part:getInventoryItem()
    if placeholder and placeholder:getFullType() == P.EMPTY_ITEM then part:setInventoryItem(nil) end
    local profile, index = M.profileFor(vehicle), P.spotIndex(part)
    if profile and profile.factoryLayout then
        local stamp = vehicle:getModData()
        -- Only an untouched first released slot identifies a newly created vehicle.
        -- Appending factory slots to a saved/cleared conversion must not refill it.
        if index == 1 and not data[P.INITIALIZED_KEY] and not part:getInventoryItem()
                and (not container or container:isEmpty()) then
            stamp.MELensFactoryLayout = profile.factoryLayout
        end
        local spot = profile.spots[index]
        if spot and spot.factory and stamp.MELensFactoryLayout ~= profile.factoryLayout then
            data[P.INITIALIZED_KEY] = true
            P.applyPiece(vehicle, part)
            return
        end
    end
    if data[P.INITIALIZED_KEY] or part:getInventoryItem() ~= nil
            or (container ~= nil and not container:isEmpty()) then
        data[P.INITIALIZED_KEY] = true
        P.applyPiece(vehicle, part)
        return
    end
    data[P.INITIALIZED_KEY] = true
    local spot = P.spotOf(vehicle, part)
    local piece = P.factoryPiece(vehicle, P.spotIndex(part), spot)
    -- unfurnished by the sandbox option, except a box truck's boxes (they hold its cargo)
    if piece and piece ~= "box" and not M.sandbox("StartFurnished", true) then piece = nil end
    if piece and P.fits(spot, piece) then
        local item = instanceItem(P.itemType(piece))
        if item then
            part:setInventoryItem(item)
        end
    end
    P.applyPiece(vehicle, part)
    if piece and piece ~= "box" and M.sandbox("FurnitureLoot", true) then
        P.fillFurniture(part, piece, vehicle)
    end
end

-- What the furniture of a newly furnished vehicle holds: the game's own loot lists of the house
-- furniture each piece stands in for (ProceduralDistributions), rolled here (the game fills a
-- vehicle's containers from its vehicle tables, which know nothing of these). A list's weight is
-- the chance in percent per roll, as in the game's lists.
P.FURNITURE_LOOT = {
    fridge = "FridgeTrailerPark",
    kitchen = "KitchenRandom",
    cabinet = "KitchenDryFood",
    wardrobe = "LivingRoomWardrobe",
    washroom = "BathroomCabinet",
    dinette = "KitchenDishes",
    bed = "DresserGeneric",
}

function P.fillFurniture(part, piece, vehicle)
    local container = part:getItemContainer()
    local use = vehicle and P.vehicleUse(vehicle)
    local listName = use and use.loot and use.loot[piece] or P.FURNITURE_LOOT[piece]
    local lists = ProceduralDistributions and ProceduralDistributions.list
    local list = lists and listName and lists[listName]
    if not container then return end
    local ok, err = pcall(function()
        local function add(name)
            local item = container:AddItem(string.find(name, "%.") and name or ("Base." .. name))
            if item and container.getCapacityWeight and container:getCapacityWeight() > container:getCapacity() then
                container:Remove(item)
            end
        end
        for _, pack in ipairs(use and use.stock and use.stock[piece] or {}) do
            for _ = 1, pack[2] do add(pack[1]) end
        end
        for _ = 1, math.min(list and list.rolls or 0, 2) do
            for i = 1, #(list.items or {}) - 1, 2 do
                local name, weight = list.items[i], tonumber(list.items[i + 1]) or 0
                if type(name) == "string" and ZombRandFloat(0, 100) < weight then
                    add(name)
                end
            end
        end
    end)
    if not ok then
        print("[ME_LENS] furniture loot failed: " .. tostring(err))
    end
    container:setExplored(true)
end

function P.initSpot(vehicle, part)
    -- Also stamp old saves, including intentionally bare spots, before any later
    -- repair/create callback can mistake them for a newly added interior.
    if not isClient() then part:getModData()[P.INITIALIZED_KEY] = true end
    P.applyPiece(vehicle, part)
end

-- Some freight (full-size gas cylinders) belongs on the floor rather than inside
-- a cupboard. These are ordinary, removable inventory items with saved positions.
-- As with factory fittings, only an untouched new vehicle receives them once.
function P.createFloor(vehicle, part)
    if isClient() then return end
    local data = part:getModData()
    if data[P.INITIALIZED_KEY] then return end
    data[P.INITIALIZED_KEY] = true
    local profile = M.profileFor(vehicle)
    local container = part:getItemContainer()
    if not profile or not profile.factoryFloor or not container or not container:isEmpty()
            or vehicle:getModData().MELensFactoryLayout ~= profile.factoryLayout
            or not M.sandbox("StartFurnished", true) or not M.sandbox("FurnitureLoot", true) then return end
    local loose = M.Loose
    if not loose then return end
    local surface = { kind = "floor", s = 0, y = profile.floorY }
    for _, cargo in ipairs(profile.factoryFloor) do
        if loose.fitsSurface(vehicle, profile, surface, cargo.x, cargo.z, cargo.hx, cargo.hz) then
            local item = container:AddItem(cargo.t)
            if item then
                if container:getCapacityWeight() > container:getCapacity() then
                    container:Remove(item)
                else
                    loose.set(vehicle, item, cargo.x, profile.floorY, cargo.z, cargo.r or 0, 0)
                end
            end
        end
    end
    container:setExplored(true)
end

function P.initFloor(vehicle, part)
    if not isClient() then part:getModData()[P.INITIALIZED_KEY] = true end
end

-- settleBox, where a failure never stops the vehicle from updating. (Not from init: a vehicle's parts
-- are made one after the other, and a box whose lower part is not made yet would look unsupported.)
function P.settle(vehicle, part)
    local ok, err = pcall(P.settleBox, vehicle, part)
    if not ok then
        print("[ME_LENS] settling a box failed: " .. tostring(err))
    end
end

-- Fridges keep cool and heaters warm the inside while the generator gives power; boxes fall
-- when what they rest on is gone.
function P.updateSpot(vehicle, part, elapsedMinutes)
    P.syncCapacity(part)
    local piece = P.pieceAt(part)
    if piece == "fridge" then
        M.Utilities.updateFridge(vehicle, part, elapsedMinutes)
    elseif piece == "heater" then
        M.Utilities.updateHeater(vehicle, part, elapsedMinutes)
    elseif piece == "box" then
        P.settle(vehicle, part)
    end
end

-- Closed cargo doors need their own inside skin: the native leaf can be single-sided.
-- Only change the model when the real door state changes; never persist render state.
P.shellDoorStates = setmetatable({}, { __mode = "k" })
local function shellDoorVisible(vehicle, id)
    local leaf = vehicle:getPartById(id)
    local door = leaf and leaf:getDoor()
    return door ~= nil and leaf:getInventoryItem() ~= nil and not door:isOpen(), leaf
end

local function syncShellDoor(vehicle, part, model, id, cacheKey, force)
    local visible, leaf = shellDoorVisible(vehicle, id)
    cacheKey = cacheKey or leaf
    if force or not cacheKey or P.shellDoorStates[cacheKey] ~= visible then
        part:setModelVisible("MELensShell" .. model, visible)
        if cacheKey then P.shellDoorStates[cacheKey] = visible end
    end
end

function P.syncShellDoors(vehicle, profile, force)
    local shell = profile and profile.shell
    if not shell or not shell.entryModel then return end
    local part = vehicle:getPartById(P.SHELL)
    if not part then return end
    syncShellDoor(vehicle, part, shell.entryModel, shell.entryDoor, vehicle, force)
    for _, lining in ipairs(shell.extraDoors or {}) do
        syncShellDoor(vehicle, part, lining.model, lining.part, nil, force)
    end
end

-- Shells are drawn only in the occupied vehicle; the entry skin follows its door.
function P.initShell(vehicle, part)
    local rv = M.java()
    if not rv or not part or vehicle:getPartById(P.SHELL) ~= part then return end
    if rv.clearStalePartModels then rv.clearStalePartModels(part) end
    local profile = M.profileFor(vehicle)
    for i = 1, profile and profile.shell and #profile.shell.models or 0 do
        part:setModelVisible("MELensShell" .. i, true)
    end
    P.syncShellDoors(vehicle, profile, true)
end

-- Called on the client's existing throttled furniture refresh. Restores render
-- bindings only; never runs create/init loot, replaces a part or writes inventory.
function P.refreshShell(vehicle, profile)
    local rv = M.java()
    local part = vehicle and vehicle:getPartById(P.SHELL)
    if not rv or not rv.isPartModelVisible or not part or not profile.shell then return end
    if rv.clearStalePartModels and rv.clearStalePartModels(part) then
        P.initShell(vehicle, part)
        return
    end
    for i = 1, #profile.shell.models do
        local doorId = i == profile.shell.entryModel and profile.shell.entryDoor or nil
        for _, lining in ipairs(profile.shell.extraDoors or {}) do
            if lining.model == i then doorId = lining.part; break end
        end
        local visible = not doorId or shellDoorVisible(vehicle, doorId)
        if rv.isPartModelVisible(part, "MELensShell" .. i) ~= visible then
            P.initShell(vehicle, part)
            return
        end
    end
end

------------------------------------------------------------------------------------
-- Loot: in a cargo vehicle the cargo is in the boxes. The game rolls a vehicle's loot
-- when the vehicle is made (and for new parts, when it first loads with them), after
-- the parts' create functions, and picks each container's loot by container type. So
-- the boxes' types get the loot of the vehicle's own cargo storage (KI5's) and that
-- storage gets none: it stays empty, and hidden (P.ki5StorageTest).
------------------------------------------------------------------------------------

-- Container types of the pieces that are boxes (P.applyPiece names them). Every box rolls
-- the cargo storage's loot once, the way one trunk does.
local BOXES = { "MELensRV_box" }

-- A copy of a vehicle's distribution with the boxes rolling the cargo storage's loot
-- instead of the storage. A copy, as vehicles share distributions (KI5's three cargo
-- trailers share one whose cargo loot differs by trailer).
local function withBoxes(dist, source)
    local own = {}
    for key, value in pairs(dist) do
        own[key] = value
    end
    for _, box in ipairs(BOXES) do
        own[box] = dist[source]
    end
    own[source] = nil
    return own
end

function P.registerLoot()
    local tables = VehicleDistributions and VehicleDistributions[1]
    if not tables then return end
    for fullName, profile in pairs(M.Profiles or {}) do
        local name = string.match(fullName, "^[^.]+%.(.+)$") or fullName
        local types = tables[name]
        local source = profile.ki5Storage and profile.ki5Storage[1]
        if profile.loot and types and source then
            for key, dist in pairs(types) do
                if type(dist) == "table" and dist[source] then
                    types[key] = withBoxes(dist, source)
                elseif type(dist) == "table" then
                    -- Specific = { distribution, ... }: one is picked per vehicle
                    for i, specific in ipairs(dist) do
                        if type(specific) == "table" and specific[source] then
                            dist[i] = withBoxes(specific, source)
                        end
                    end
                end
            end
        end
    end
end

-- After every mod's distributions are in, before the game reads them into its loot tables.
Events.OnPostDistributionMerge.Add(P.registerLoot)

------------------------------------------------------------------------------------
-- Script extension
------------------------------------------------------------------------------------

local function itemTypeList(pieces)
    local list = {}
    for _, piece in ipairs(pieces) do
        table.insert(list, P.itemType(piece))
    end
    return table.concat(list, ";")
end

-- One model per piece and a ghost of each (the game needs a model file for every part
-- model of a part without a parent), shown by P.showPiece. A spot only declares what can
-- stand there (P.piecesFor), and a stacked one stands `rise` above the floor.
local function spotScript(index, spot, profile, withModels)
    local models = {}
    local pieces = P.piecesFor(spot)
    -- `Vehicle:repair()` installs a part's declared itemType into every empty
    -- compatible part. Bare slots use a harmless placeholder that init/refresh removes;
    -- omitting itemType entirely causes the engine to discard installed furniture on load.
    local installTypes = (" itemType = %s, "):format((spot.empty or spot.factory) and P.EMPTY_ITEM or itemTypeList(pieces))
    if withModels then
        local o = M.modelOffset(spot.x, profile.floorY + (spot.rise or 0), spot.z, profile)
        local modelScale = 0.9 / (profile.vehicleScale or 0.9)
        local rotate = P.WALLS[spot.wall].rotate * P.ROTATE_SIGN
        for _, piece in ipairs(pieces) do
            local file = P.modelFile(piece, spot)
            table.insert(models, string.format(" model %s { file = %s, offset = %.4f %.4f %.4f, rotate = 0 %d 0, scale = %.7f, }",
                piece, file, o[1], o[2], o[3], rotate, modelScale))
            table.insert(models, string.format(" model ghost_%s { file = %s_ghost, offset = %.4f %.4f %.4f, rotate = 0 %d 0, scale = %.7f, }",
                piece, file, o[1], o[2], o[3], rotate, modelScale))
        end
    end
    return string.format("{ part %s%d { category = nodisplay, area = %s,%smechanicRequireKey = false, setAllModelsVisible = false,"
        .. " container { capacity = 1, conditionAffectsCapacity = false, test = MELens.Parts.containerTest, }%s"
        .. " table install { time = 300, test = MELens.Parts.placeTest, }"
        .. " table uninstall { time = 200, test = MELens.Parts.pickUpTest, }"
        .. " lua { create = MELens.Parts.createSpot, init = MELens.Parts.initSpot, update = MELens.Parts.updateSpot, } } }",
        P.SPOT, index, profile.standing.area, installTypes, table.concat(models))
end

-- Adds the parts to a vehicle script. The shell and furniture models are only declared
-- with the Java part, which draws ME: LENS' inside only in the vehicle you are in. The
-- parts themselves are declared everywhere, in the same order: a server runs without the
-- Java part, and the game sends a vehicle's part changes (furniture, storage, what lies
-- there) between server and clients by the part's place in the list.
function P.extendScript(script, profile)
    local area = profile.standing.area
    local java = M.java() ~= nil
    if profile.shell then
        local o = M.modelOffset(0, 0, 0, profile)
        local modelScale = 0.9 / (profile.vehicleScale or 0.9)
        local models = {}
        for i, model in ipairs(java and profile.shell.models or {}) do
            table.insert(models, string.format(" model MELensShell%d { file = %s, offset = %.4f %.4f %.4f, rotate = 0 0 0, scale = %.7f, }",
                i, model, o[1], o[2], o[3], modelScale))
        end
        script:Load(script:getName(), string.format(
            "{ part %s { category = nodisplay, area = %s,%s lua { create = MELens.Parts.initShell, init = MELens.Parts.initShell, } } }",
            P.SHELL, area, table.concat(models)))
    end
    for index, spot in ipairs(profile.spots or {}) do
        script:Load(script:getName(), spotScript(index, spot, profile, java))
    end
    script:Load(script:getName(), string.format(
        "{ part %s { category = nodisplay, area = %s, container { capacity = 100, conditionAffectsCapacity = false, test = MELens.Parts.floorTest, } lua { create = MELens.Parts.createFloor, init = MELens.Parts.initFloor, } } }",
        P.FLOOR, area))
    -- KI5's cargo storage gives way to the boxes (see P.ki5StorageTest)
    for _, id in ipairs(profile.ki5Storage or {}) do
        script:Load(script:getName(), string.format(
            "{ part %s { container { test = MELens.Parts.ki5StorageTest, } } }", id))
    end
    script:Load(script:getName(), string.format(
        "{ part %s { category = nodisplay, area = %s, lua { create = MELens.Utilities.createGenerator, init = MELens.Utilities.initGenerator, update = MELens.Utilities.updateGenerator, } } }",
        P.GENERATOR, area))
    script:Load(script:getName(), string.format(
        "{ part %s { category = nodisplay, area = %s, lua { create = MELens.Utilities.createWaterTank, } } }",
        P.WATER, area))
    script:Load(script:getName(), string.format(
        "{ part %s { category = nodisplay, area = %s,"
        .. " container { capacity = 15, conditionAffectsCapacity = false, test = MELens.Utilities.ovenTest, }"
        .. " lua { create = MELens.Utilities.initOven, init = MELens.Utilities.initOven, update = MELens.Utilities.updateOven, } } }",
        P.OVEN, area))
end

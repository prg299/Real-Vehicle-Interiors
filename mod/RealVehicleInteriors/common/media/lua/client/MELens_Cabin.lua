--
-- ME: LENS walk-in campers (client, single player).
--
-- You become a standing passenger of the camper. Walking moves that passenger's
-- position along the camper floor, so the camper keeps owning your position, your
-- protection from the weather and zombies, and your save state. The Java part draws
-- ME: LENS' inside (shell and furniture) in the camper you are in, cuts its roof away
-- and turns your model to face where you walk. Furniture (MELens_Parts.lua) is used by
-- right-clicking it (MELens_Interact.lua); sitting and lying use KI5's own seats.
--

require "TimedActions/ISBaseTimedAction"
require "TimedActions/ISTimedActionQueue"
require "Vehicles/TimedActions/ISEnterVehicle"
require "Vehicles/ISUI/ISVehicleMenu"
require "Vehicles/ISUI/ISVehicleSeatUI"
require "MELens_Parts"

MELens = MELens or {}
local M = MELens
local P = M.Parts
require "MELens_Bed"
local B = M.Bed

M.VERSION = "2.0.11"

local CABIN_VAR = "MELensCabin"      -- "Idle" / "Walk": the standing poses
local SEAT_VAR = "MELensCabinSeat"   -- "true" while entering, standing in or leaving
local POSITION_KEY = "MELensCabin"   -- vehicle modData: where you were standing
local IDLE_DELAY = 0.15             -- seconds without movement before the idle pose
local RUN_SPEED_MULTIPLIER = 1.65   -- Shift/Run moves faster within the same walkable floor
local MAX_MOVE_STEP = 0.05          -- small collision steps also when running or after a slow frame

local TURN_SPEED = 18.0              -- radians per second
local TURN_FIRST = 1.2               -- turn on the spot first when the new direction is further off (radians)
local PUSH_TO_LEAVE = 0.35           -- seconds of walking into the door that take you out
local ARRIVE_DISTANCE = 0.04

local session = nil
local armedVehicle = nil
local lastMs = nil
local placeVec, localA, localB

local function java()
    return MELensRV
end

local function say(player, key, ...)
    if player then
        HaloTextHelper.addBadText(player, getText(key, ...))
    end
end

------------------------------------------------------------------------------------
-- Profiles and seats
------------------------------------------------------------------------------------

function M.seatIndex(vehicle, seatId)
    local script = vehicle and vehicle:getScript()
    return script and script:getPassengerIndex(seatId) or -1
end

function M.cabinSeat(vehicle, profile)
    profile = profile or M.profileFor(vehicle)
    if not profile then return -1 end
    return M.seatIndex(vehicle, profile.seatId)
end

-- The places to stand (several, for multiplayer; MELens.standingIds).
function M.isStandingSeat(vehicle, profile, seat)
    profile = profile or M.profileFor(vehicle)
    if not profile or not seat or seat < 0 then return false end
    for _, id in ipairs(M.standingIds(profile)) do
        if M.seatIndex(vehicle, id) == seat then return true end
    end
    return false
end

-- The first place to stand that nobody uses, or -1.
function M.freeStandingSeat(vehicle, profile)
    profile = profile or M.profileFor(vehicle)
    if not profile then return -1 end
    for _, id in ipairs(M.standingIds(profile)) do
        local index = M.seatIndex(vehicle, id)
        if index >= 0 and not vehicle:getCharacter(index) then return index end
    end
    return -1
end

-- The vehicle's own seats that keep the game's entry, exit and driving (a bus driver's
-- seat, a box truck's cab): being in one is not being inside.
function M.isVanillaSeat(vehicle, profile, seat)
    if not profile or not profile.vanillaSeats or not seat or seat < 0 then return false end
    local id = vehicle:getScript():getPassenger(seat):getId()
    for _, vid in ipairs(profile.vanillaSeats) do
        if vid == id then return true end
    end
    return false
end

function M.inVanillaSeat(player, vehicle, profile)
    return vehicle ~= nil and M.isVanillaSeat(vehicle, profile, vehicle:getSeat(player))
end

-- The driver's seat you can walk to from inside (a bus): { seat, x1, x2, z1, z2 }.
function M.driverSpot(profile)
    return profile and profile.driver or nil
end

-- Where you stand beside the driver's seat, on the aisle side.
function M.driverStandPoint(profile)
    local d = M.driverSpot(profile)
    if not d then return nil end
    local x = d.x1 > 0 and d.x1 - 0.18 or d.x2 + 0.18
    return x, (d.z1 + d.z2) / 2
end

-- Where you stand to use (or after leaving) one of KI5's seats: in front of the
-- furniture spot it belongs to, level with the seat.
function M.seatStandPoint(vehicle, profile, seat)
    local driver = M.driverSpot(profile)
    if driver and seat == M.seatIndex(vehicle, driver.seat) then
        return M.driverStandPoint(profile)
    end
    local script = vehicle:getScript()
    for index, spot in ipairs(profile.spots or {}) do
        for _, id in ipairs(spot.seats or {}) do
            if script:getPassengerIndex(id) == seat then
                local _, sx, sz = P.seatPoint(vehicle, profile, id)
                local piece = P.pieceAt(P.spotPart(vehicle, index))
                local length, depth = P.footprint(spot, piece)
                local a = P.toSpot(spot, sx, sz)
                a = math.max(-length / 2 + 0.1, math.min(length / 2 - 0.1, a))
                return P.spotPoint(spot, a, depth + 0.17)
            end
        end
    end
    return nil
end

function M.isStanding(player)
    player = player or getSpecificPlayer(0)
    local vehicle = player and player:getVehicle()
    return vehicle ~= nil and M.isStandingSeat(vehicle, nil, vehicle:getSeat(player))
end

-- A seat you only reach from inside a walk-in vehicle: a bed's, a dinette's or a bus seat's (not a place to stand,
-- not one of the seats that keep the game's own entry such as a bus driver's or a box truck's cab). Without the
-- Java part nobody walks in, and every seat keeps the game's own entry.
function M.isInsideSeat(vehicle, profile, seat)
    profile = profile or M.profileFor(vehicle)
    if not profile or not java() or not seat or seat < 0 or M.cabinSeat(vehicle, profile) < 0 then return false end
    return not M.isStandingSeat(vehicle, profile, seat) and not M.isVanillaSeat(vehicle, profile, seat)
end

-- Sitting or lying on one of those inside the vehicle (getting up leaves you standing inside).
function M.seatedInside(player, vehicle)
    return player ~= nil and vehicle ~= nil and player:getVehicle() == vehicle
        and M.isInsideSeat(vehicle, nil, vehicle:getSeat(player))
end

function M.isInside(player)
    player = player or getSpecificPlayer(0)
    local vehicle = player and player:getVehicle()
    return M.profileFor(vehicle) ~= nil
end

------------------------------------------------------------------------------------
-- Floor geometry
------------------------------------------------------------------------------------

-- The walk grid of the empty shell, made with the shell (tools-src/blender/rv_kit.py):
-- one string per row along z, '1' where the centre of your character may be. In the
-- camper you are in, the installed furniture is blocked out of it (rebuilt when the
-- furniture changes).
local CHARACTER_RADIUS = 0.15      -- the body is about 0.2 wide: 0.10 put arms into counters
local furnished = { vehicle = nil, key = nil, grid = nil }

local function baseGrid(profile)
    return profile.walkGrid and M.WalkGrids and M.WalkGrids[profile.walkGrid] or nil
end

local function furnitureKey(vehicle, profile)
    local pieces = {}
    for index = 1, #(profile.spots or {}) do
        pieces[index] = P.pieceAt(P.spotPart(vehicle, index)) or "-"
    end
    return table.concat(pieces, ",")
end

-- The shell's walk grid with the furniture standing now (and the vehicle's own blocked areas) closed. Each piece only
-- visits the cells under its own rectangle: testing every cell against every piece took 0.4 s in a box truck full of
-- boxes (a 87 x 224 grid, 46 boxes), a freeze each time a box or a piece was picked up or put down.
local function furnishGrid(base, vehicle, profile)
    local cell, cols, count = base.cell, base.cols, #base.rows
    local open = {}
    for r = 1, count do
        local row, flags = base.rows[r], {}
        for c = 1, cols do
            flags[c] = string.byte(row, c) == 49
        end
        open[r] = flags
    end
    -- the cells whose middles lie in a rectangle of passenger space (one more all round, against rounding at its
    -- edges: the exact test below decides), clipped to the grid
    local function cellRange(x1, x2, z1, z2)
        return math.max(1, math.ceil((x1 - base.x0) / cell + 0.5) - 1), math.min(cols, math.floor((x2 - base.x0) / cell + 0.5) + 1),
            math.max(1, math.ceil((z1 - base.z0) / cell + 0.5) - 1), math.min(count, math.floor((z2 - base.z0) / cell + 0.5) + 1)
    end
    local behind = (cols + count) * cell      -- behind a piece is its wall, closed anyway: as far as the grid reaches
    for index, spot in ipairs(profile.spots or {}) do
        local piece = P.pieceAt(P.spotPart(vehicle, index))
        if piece then
            local length, depth = P.footprint(spot, piece)
            local half, reach = length / 2 + CHARACTER_RADIUS, depth + CHARACTER_RADIUS
            local x1, x2, z1, z2 = math.huge, -math.huge, math.huge, -math.huge
            for _, a in ipairs({ -half, half }) do
                for _, d in ipairs({ -behind, reach }) do
                    local x, z = P.spotPoint(spot, a, d)
                    x1, x2, z1, z2 = math.min(x1, x), math.max(x2, x), math.min(z1, z), math.max(z2, z)
                end
            end
            local c1, c2, r1, r2 = cellRange(x1, x2, z1, z2)
            for r = r1, r2 do
                local flags, z = open[r], base.z0 + (r - 0.5) * cell
                for c = c1, c2 do
                    if flags[c] then
                        local a, d = P.toSpot(spot, base.x0 + (c - 0.5) * cell, z)
                        if math.abs(a) <= half and d <= reach then
                            flags[c] = false
                        end
                    end
                end
            end
        end
    end
    -- the vehicle's own things standing inside (a bus driver's seat and dashboard)
    for _, b in ipairs(profile.blocked or {}) do
        local x1, x2 = b.x1 - CHARACTER_RADIUS, b.x2 + CHARACTER_RADIUS
        local z1, z2 = b.z1 - CHARACTER_RADIUS, b.z2 + CHARACTER_RADIUS
        local c1, c2, r1, r2 = cellRange(x1, x2, z1, z2)
        for r = r1, r2 do
            local flags, z = open[r], base.z0 + (r - 0.5) * cell
            for c = c1, c2 do
                local x = base.x0 + (c - 0.5) * cell
                if x >= x1 and x <= x2 and z >= z1 and z <= z2 then
                    flags[c] = false
                end
            end
        end
    end
    local rows = {}
    for r = 1, count do
        local flags, cells = open[r], {}
        for c = 1, cols do
            cells[c] = flags[c] and "1" or "0"
        end
        rows[r] = table.concat(cells)
    end
    return { x0 = base.x0, z0 = base.z0, cell = base.cell, cols = base.cols, rows = rows }
end

-- Rebuilds the furnished grid when the camper or its furniture changed.
local function refreshFurnished(vehicle, profile)
    local base = baseGrid(profile)
    if not base then return end
    local key = furnitureKey(vehicle, profile)
    if furnished.vehicle ~= vehicle or furnished.key ~= key then
        furnished.vehicle, furnished.key = vehicle, key
        furnished.profile = profile
        furnished.grid = furnishGrid(base, vehicle, profile)
    end
end

local function gridFor(profile)
    if furnished.grid and furnished.profile == profile then
        return furnished.grid
    end
    return baseGrid(profile)
end

local function gridOpen(grid, c, r)
    local row = grid.rows[r + 1]
    return row ~= nil and c >= 0 and c < grid.cols and string.byte(row, c + 1) == 49
end

local function walkable(profile, x, z)
    local grid = gridFor(profile)
    if grid then
        return gridOpen(grid, math.floor((x - grid.x0) / grid.cell), math.floor((z - grid.z0) / grid.cell))
    end
    for _, r in ipairs(profile.walkable) do
        if x >= r.x1 and x <= r.x2 and z >= r.z1 and z <= r.z2 then
            return true
        end
    end
    return false
end

-- Whether a point inside is open floor (furniture blocked out): for the other client files.
function M.walkableAt(profile, x, z)
    return walkable(profile, x, z)
end

local function nearestWalkable(profile, x, z)
    if walkable(profile, x, z) then
        return x, z
    end
    local grid = gridFor(profile)
    if grid then
        -- Search outwards ring by ring for the closest open cell.
        for ring = 1, 40 do
            local best, bx, bz = nil, x, z
            for dr = -ring, ring do
                for dc = -ring, ring do
                    if math.max(math.abs(dr), math.abs(dc)) == ring then
                        local cx, cz = x + dc * grid.cell, z + dr * grid.cell
                        local d = dr * dr + dc * dc
                        if (not best or d < best) and walkable(profile, cx, cz) then
                            best, bx, bz = d, cx, cz
                        end
                    end
                end
            end
            if best then
                return bx, bz
            end
        end
        return x, z
    end
    local bx, bz, best = x, z, nil
    for _, r in ipairs(profile.walkable) do
        local cx = math.max(r.x1, math.min(r.x2, x))
        local cz = math.max(r.z1, math.min(r.z2, z))
        local d = (cx - x) * (cx - x) + (cz - z) * (cz - z)
        if not best or d < best then
            bx, bz, best = cx, cz, d
        end
    end
    return bx, bz
end

-- The open floor nearest to a point (furniture blocked out): where to stand to reach it.
function M.nearestWalkableAt(profile, x, z)
    return nearestWalkable(profile, x, z)
end

local function clearLine(profile, x1, z1, x2, z2)
    local dist = math.sqrt((x2 - x1) ^ 2 + (z2 - z1) ^ 2)
    local steps = math.max(1, math.ceil(dist / 0.04))
    for i = 0, steps do
        local t = i / steps
        if not walkable(profile, x1 + (x2 - x1) * t, z1 + (z2 - z1) * t) then
            return false
        end
    end
    return true
end

local NEIGHBOURS = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 }, { 1, 1 }, { 1, -1 }, { -1, 1 }, { -1, -1 } }

-- Shortest route over the walk grid (breadth first), then straightened: from each point
-- go to the farthest later point that is in a clear line.
local function gridPath(profile, grid, fromX, fromZ, toX, toZ)
    local cell, cols = grid.cell, grid.cols
    local sc, sr = math.floor((fromX - grid.x0) / cell), math.floor((fromZ - grid.z0) / cell)
    local tc, tr = math.floor((toX - grid.x0) / cell), math.floor((toZ - grid.z0) / cell)
    local start, target = sr * cols + sc, tr * cols + tc
    local prev = { [start] = -1 }
    local queue, head = { start }, 1
    while head <= #queue and prev[target] == nil do
        local k = queue[head]
        head = head + 1
        local c, r = k % cols, math.floor(k / cols)
        for _, d in ipairs(NEIGHBOURS) do
            local nc, nr = c + d[1], r + d[2]
            local nk = nr * cols + nc
            if prev[nk] == nil and gridOpen(grid, nc, nr)
                    and (d[1] == 0 or d[2] == 0 or (gridOpen(grid, c + d[1], r) and gridOpen(grid, c, r + d[2]))) then
                prev[nk] = k
                queue[#queue + 1] = nk
            end
        end
    end
    if prev[target] == nil then
        return nil
    end
    local points = {}
    local k = target
    while k ~= -1 do
        table.insert(points, 1, { x = grid.x0 + (k % cols + 0.5) * cell, z = grid.z0 + (math.floor(k / cols) + 0.5) * cell })
        k = prev[k]
    end
    points[#points] = { x = toX, z = toZ }
    local path, cx, cz, i = {}, fromX, fromZ, 1
    while i <= #points do
        local j = #points
        while j > i and not clearLine(profile, cx, cz, points[j].x, points[j].z) do
            j = j - 1
        end
        path[#path + 1] = points[j]
        cx, cz = points[j].x, points[j].z
        i = j + 1
    end
    return path
end

-- Straight line when possible, otherwise around the furniture.
local function planPath(profile, fromX, fromZ, toX, toZ)
    toX, toZ = nearestWalkable(profile, toX, toZ)
    if clearLine(profile, fromX, fromZ, toX, toZ) then
        return { { x = toX, z = toZ } }
    end
    local grid = gridFor(profile)
    if grid then
        local sx, sz = nearestWalkable(profile, fromX, fromZ)
        return gridPath(profile, grid, sx, sz, toX, toZ) or { { x = toX, z = toZ } }
    end
    local ax = profile.aisleX or 0
    local path = {}
    if clearLine(profile, fromX, fromZ, ax, fromZ) then
        table.insert(path, { x = ax, z = fromZ })
    end
    table.insert(path, { x = ax, z = toZ })
    table.insert(path, { x = toX, z = toZ })
    return path
end

------------------------------------------------------------------------------------
-- Passenger placement
------------------------------------------------------------------------------------

local function place(s)
    placeVec = placeVec or Vector3f.new()
    placeVec:set(s.x, s.profile.floorY, s.z)
    s.vehicle:setPassenger(s.seat, s.player, placeVec)
end

-- World direction (tiles) to a direction in the camper's passenger space.
local function toCamperDirection(vehicle, px, py, wx, wy)
    localA = localA or Vector3f.new()
    localB = localB or Vector3f.new()
    vehicle:getLocalPos(px, py, 0, localA)
    vehicle:getLocalPos(px + wx, py + wy, 0, localB)
    return localB:x() - localA:x(), localB:z() - localA:z()
end

-- Facing for the render hook: 0 looks towards the hitch, turning towards -x first.
local function facingFor(dx, dz)
    return math.atan2(-dx, dz)
end

-- The signed difference target - current in (-pi, pi]. Written out: the game's Lua keeps
-- the sign of a negative number in `%`, which turned some turns the long way round.
local function angleDiff(target, current)
    local d = target - current
    while d > math.pi do d = d - 2 * math.pi end
    while d <= -math.pi do d = d + 2 * math.pi end
    return d
end

local function turnTowards(current, target, maxStep)
    local delta = angleDiff(target, current)
    if math.abs(delta) <= maxStep then
        return target
    end
    return angleDiff(current + (delta > 0 and maxStep or -maxStep), 0)
end

-- Where you stand, per place to stand (the first keeps the key of single-player saves).
local function positionKey(vehicle, profile, seat)
    return seat == M.cabinSeat(vehicle, profile) and POSITION_KEY or (POSITION_KEY .. seat)
end

local function savePosition(s)
    local data = s.vehicle:getModData()
    data[positionKey(s.vehicle, s.profile, s.seat)] = { x = s.x, z = s.z, f = s.facing }
end

------------------------------------------------------------------------------------
-- Cutaway (Java render state)
------------------------------------------------------------------------------------

-- Mod options: wall height while inside (Low / Medium / High) and lower walls on the
-- camera's side.
local wallHeight, cameraWalls, itemNames, itemLimit = nil, nil, nil, nil
if PZAPI and PZAPI.ModOptions then
    local options = PZAPI.ModOptions:create("RealVehicleInteriors", getText("IGUI_MELens_OptionsTitle"))
    wallHeight = options:addComboBox("wallHeight", getText("IGUI_MELens_WallHeight"), getText("IGUI_MELens_WallHeightTooltip"))
    wallHeight:addItem(getText("IGUI_MELens_WallLow"))
    wallHeight:addItem(getText("IGUI_MELens_WallMedium"), true)
    wallHeight:addItem(getText("IGUI_MELens_WallHigh"))
    cameraWalls = options:addTickBox("cameraWalls", getText("IGUI_MELens_CameraWalls"), true, getText("IGUI_MELens_CameraWallsTooltip"))
    itemNames = options:addTickBox("itemNames", getText("IGUI_MELens_ItemNames"), true, getText("IGUI_MELens_ItemNamesTooltip"))
    itemLimit = options:addSlider("itemLimit", getText("IGUI_MELens_ItemLimit"), 16, 64, 8, 64, getText("IGUI_MELens_ItemLimitTooltip"))
    options.apply = function()
        armedVehicle = nil -- re-arm with the new height on the next tick
    end
end

-- Whether the name of the item under the mouse shows (a mod option), and how many items are drawn inside.
function M.itemNamesOn()
    return itemNames == nil or itemNames:getValue() ~= false
end

function M.itemLimit()
    return itemLimit and math.floor(itemLimit:getValue()) or 64
end

local function cutPlaneFor(profile)
    local choice = wallHeight and wallHeight:getValue() or 2
    return profile.cutPlanes[choice] or profile.cutPlanes[2]
end

-- Passenger space (tiles) to the body's mesh space (see the profiles).
local function toMesh(profile, x, y, z)
    local m = profile.mesh
    return -x / m.scale, z / m.scale, m.lift - y / m.scale
end

local function applyLamps(rv, profile, on)
    local light = profile.light
    local values = {}
    for i = 1, 2 do
        local lamp = on and light and light.lamps[i]
        if lamp then
            local mx, my, mz = toMesh(profile, lamp.x, lamp.y, lamp.z)
            table.insert(values, mx)
            table.insert(values, my)
            table.insert(values, mz)
            table.insert(values, light.lampReach / profile.mesh.scale)
        else
            for _ = 1, 4 do table.insert(values, 0) end
        end
    end
    local c = light and light.lampColour or { 0, 0, 0 }
    rv.setLamps(values[1], values[2], values[3], values[4], values[5], values[6], values[7], values[8], c[1], c[2], c[3])
end

local armedLamps = nil
local nearCutDir = nil
local nearCutTimer = 0
local WELL_CUT_ABOVE_FLOOR = 0.03     -- wheel-well boxes on the camera's side are cut down to this
local WELL_FLOOR_SLACK = 0.002          -- ... and are not drawn below the floor less this
local ROOM_MIN_ABOVE, ROOM_MAX_ABOVE = 0.012, 0.30   -- KI5 body details inside the lining, between these heights, are not drawn

-- Walls facing the camera are cut lower. The direction towards the camera (screen down,
-- world +x +y) depends on how the camper is parked, so it is refreshed while inside.
local function applyNearCut(rv, vehicle, profile)
    if not profile.nearCutY or (cameraWalls and not cameraWalls:getValue()) then
        if nearCutDir then
            rv.clearNearCut()
            nearCutDir = nil
        end
        return
    end
    local dx, dz = toCamperDirection(vehicle, vehicle:getX(), vehicle:getY(), 0.7071, 0.7071)
    local mx, my = -dx, dz -- passenger space to the body's mesh space
    local len = math.sqrt(mx * mx + my * my)
    if len < 1e-6 then return end
    mx, my = mx / len, my / len
    if nearCutDir and math.abs(nearCutDir[1] - mx) < 0.01 and math.abs(nearCutDir[2] - my) < 0.01 then
        return
    end
    nearCutDir = { mx, my }
    rv.setNearCut(mx, my, profile.mesh.lift - profile.nearCutY / profile.mesh.scale)
    -- the wheel-well boxes on that side go down to the floor (they would show over the wall)
    if rv.setWellCut then
        rv.setWellCut(profile.mesh.lift - (profile.floorY + WELL_CUT_ABOVE_FLOOR) / profile.mesh.scale)
    end
    -- and nothing of them below the floor on that side (their liner would show through the arch beside the tyre)
    if rv.setWellFloor then
        rv.setWellFloor(profile.mesh.lift - (profile.floorY - WELL_FLOOR_SLACK) / profile.mesh.scale)
    end
end

-- The inside models are shaded like the game's furniture sprites: lit from the screen's
-- lower left (world +y, a little -x), so of the two sides you see, the left one is
-- lighter. Kept in step with how the camper is parked.
local SHADE_FROM = { -0.3, 1.0 }
local SHADE_CONTRAST = 0.08

local function applyShade(rv, vehicle)
    if not rv.setShade then return end
    local dx, dz = toCamperDirection(vehicle, vehicle:getX(), vehicle:getY(), SHADE_FROM[1], SHADE_FROM[2])
    local mx, my = -dx, dz -- passenger space to the body's mesh space
    local len = math.sqrt(mx * mx + my * my)
    if len < 1e-6 then return end
    rv.setShade(mx / len, my / len, SHADE_CONTRAST)
end

-- The paint on the walls (MELens_Home.lua), for the shell shader.
local function applyPaint(rv, vehicle)
    if not rv.setWallTint then return end
    local r, g, b = M.Home.paint(vehicle)
    if r then
        rv.setWallTint(r, g, b)
    else
        rv.clearWallTint()
    end
end

local function armCutaway(vehicle, profile, dt)
    local rv = java()
    if not rv then return end
    local lamps = vehicle ~= nil and M.lightsOn(vehicle)
    if vehicle == armedVehicle then
        if vehicle and lamps ~= armedLamps then
            applyLamps(rv, profile, lamps)
            armedLamps = lamps
        end
        if vehicle then
            nearCutTimer = nearCutTimer + (dt or 0)
            if nearCutTimer > 0.25 then
                nearCutTimer = 0
                applyNearCut(rv, vehicle, profile)
                applyShade(rv, vehicle)
                applyPaint(rv, vehicle)
            end
        end
        return
    end
    nearCutDir = nil
    if vehicle then
        local p = cutPlaneFor(profile)
        rv.setCutaway(vehicle, p[1], p[2], p[3], p[4])
        if rv.setWeatherRoom then
            local ring = M.RoomRings and M.RoomRings[profile.walkGrid]
            local points = {}
            for _, corner in ipairs(ring or {}) do
                points[#points + 1] = string.format("%.5f,%.5f", corner[1], corner[2])
            end
            local top = profile.mesh and math.abs(p[3]) > 0.0001
                and (profile.mesh.lift + p[4] / p[3]) * profile.mesh.scale or profile.floorY + 1
            rv.setWeatherRoom(table.concat(points, ";"), profile.floorY, top)
        end
        -- nothing ahead of the compartment is cut (a bus's hood)
        if rv.setCutFront then
            if profile.cutFront then
                rv.setCutFront(profile.cutFront / profile.mesh.scale)
                -- ... but only as high as the cab goes: its mirrors and roof lights stand higher
                if profile.cutFrontTop and rv.setCutFrontTop then
                    rv.setCutFrontTop(profile.mesh.lift - profile.cutFrontTop / profile.mesh.scale)
                end
            else
                rv.clearCutFront()
            end
        end
        local light = profile.light
        if light then
            rv.setInterior(table.concat(light.interiorModels or {}, ","), light.daylight or 0, light.minimum or 0, light.topDown or 0)
            applyLamps(rv, profile, lamps)
        end
        applyNearCut(rv, vehicle, profile)
        applyShade(rv, vehicle)
        applyPaint(rv, vehicle)
        if rv.setClipBox then
            rv.clearClipBoxes()
            for i, well in ipairs(profile.wheelWells or {}) do
                local ax, ay, az = toMesh(profile, well.x[1], well.y[1], well.z[1])
                local bx, by, bz = toMesh(profile, well.x[2], well.y[2], well.z[2])
                rv.setClipBox(i - 1, ax, ay, az, bx, by, bz)
            end
        end
        -- KI5's windows: the glass is hidden and the walls have no openings, and what black the
        -- hull keeps of a window (the seal round its opening, a pillar's inside) is not drawn
        if rv.setWindowBoxes then
            local boxes = {}
            for _, w in ipairs(profile.windowBoxes or {}) do
                local ax, ay, az = toMesh(profile, w.x[1], w.y[1], w.z[1])
                local bx, by, bz = toMesh(profile, w.x[2], w.y[2], w.z[2])
                boxes[#boxes + 1] = string.format("%.3f,%.3f,%.3f,%.3f,%.3f,%.3f", math.min(ax, bx), math.min(ay, by),
                    math.min(az, bz), math.max(ax, bx), math.max(ay, by), math.max(az, bz))
            end
            if #boxes > 0 then
                rv.setWindowBoxes(table.concat(boxes, ";"))
            else
                rv.clearWindowBoxes()
            end
        end
        -- the jambs of the doors' frames (black) between the lining and the leaf: painted like the room too
        if rv.setJambBoxes then
            local boxes = {}
            for _, w in ipairs(profile.jambBoxes or {}) do
                local ax, ay, az = toMesh(profile, w.x[1], w.y[1], w.z[1])
                local bx, by, bz = toMesh(profile, w.x[2], w.y[2], w.z[2])
                boxes[#boxes + 1] = string.format("%.3f,%.3f,%.3f,%.3f,%.3f,%.3f", math.min(ax, bx), math.min(ay, by),
                    math.min(az, bz), math.max(ax, bx), math.max(ay, by), math.max(az, bz))
            end
            if #boxes > 0 then
                rv.setJambBoxes(table.concat(boxes, ";"))
            else
                rv.clearJambBoxes()
            end
        end
        -- the inside of a door leaf is bare black: painted like the room's walls
        if rv.setDoorPaint then
            local paint = profile.doorPaint
            if paint then
                rv.setDoorPaint(paint[1], paint[2], paint[3])
            else
                rv.clearDoorPaint()
            end
        end
        -- KI5's body details standing inside the lining (a tongue's arm tips) are not drawn
        if rv.setRoom then
            local ring = profile.clipBody and M.RoomRings and M.RoomRings[profile.walkGrid]
            if ring and #ring >= 3 then
                local points = {}
                for _, corner in ipairs(ring) do
                    local mx, my = toMesh(profile, corner[1], profile.floorY, corner[2])
                    points[#points + 1] = string.format("%.3f,%.3f", mx, my)
                end
                local normal = math.sqrt(p[1] * p[1] + p[2] * p[2] + p[3] * p[3])
                local floorDot = p[3] * (profile.mesh.lift - profile.floorY / profile.mesh.scale) / normal
                rv.setRoom(table.concat(points, ";"), floorDot, ROOM_MIN_ABOVE / profile.mesh.scale,
                           ROOM_MAX_ABOVE / profile.mesh.scale)
            else
                rv.clearRoom()
            end
        end
    else
        rv.clearCutaway()
    end
    armedVehicle = vehicle
    armedLamps = lamps
end

------------------------------------------------------------------------------------
-- Lamps: the camper's ceiling lights run on its battery (a running generator charges
-- it). They are on while someone is inside (unless switched off at the utility panel)
-- and off when it is empty, so a camper never drains its battery unattended.
------------------------------------------------------------------------------------

local LIGHTS_KEY = "MELensLightsOff"     -- vehicle modData: true when switched off in this camper
local lightVehicle = nil                 -- the camper you are in
local worldLight = nil                   -- { vehicle, light, x, y, z }
local lightTimer = 0

local function batteryCharge(vehicle)
    local battery = vehicle and vehicle:getBattery()
    local item = battery and battery:getInventoryItem()
    return item and item:getCurrentUsesFloat() or 0
end
M.batteryCharge = batteryCharge

-- The switch position in this camper (on unless someone switched them off).
function M.lightsSwitchedOn(vehicle)
    return vehicle ~= nil and vehicle:getModData()[LIGHTS_KEY] ~= true
end

-- Actually lit: switched on, someone inside, and power in the battery.
function M.lightsOn(vehicle)
    local player = getSpecificPlayer(0)
    return M.lightsSwitchedOn(vehicle) and player ~= nil and player:getVehicle() == vehicle
        and batteryCharge(vehicle) > 0
end

local function removeWorldLight()
    if worldLight then
        getCell():removeLamppost(worldLight.light)
        worldLight = nil
    end
end

-- A real light source at the camper, so you and its surroundings are lit too.
local function updateWorldLight(vehicle, profile)
    local on = vehicle ~= nil and profile.light ~= nil and M.lightsOn(vehicle)
    local x, y, z
    if on then
        x, y, z = math.floor(vehicle:getX()), math.floor(vehicle:getY()), math.floor(vehicle:getZ())
    end
    local w = worldLight
    if w and (not on or w.vehicle ~= vehicle or w.x ~= x or w.y ~= y or w.z ~= z) then
        removeWorldLight()
    end
    if on and not worldLight then
        local c = profile.light.worldColour or profile.light.lampColour
        local light = getCell():addLamppost(x, y, z, c[1], c[2], c[3], profile.light.worldRadius or 3)
        worldLight = { vehicle = vehicle, light = light, x = x, y = y, z = z }
    end
end

-- Twice a second: keep the local world light in place. Battery use belongs to the
-- shared server/single-player utility clock, once per occupied vehicle.
local function updateLamps(player, dt)
    lightTimer = lightTimer + dt
    if lightTimer < 0.5 then return end
    lightTimer = 0
    local vehicle = player:getVehicle()
    local profile = M.profileFor(vehicle)
    if profile then
        lightVehicle = vehicle
        updateWorldLight(vehicle, profile)
    else
        lightVehicle = nil
        removeWorldLight()
    end
end

------------------------------------------------------------------------------------
-- Standing session
------------------------------------------------------------------------------------

local function setPoseVars(player, pose)
    player:setVariable(SEAT_VAR, "true")
    player:setVariable(CABIN_VAR, pose)
    -- damnlib's seat poses (used when you sit or lie down) need its vehicle flag.
    player:setVariable("damnVehicle", "True")
end

local function clearPoseVars(player)
    player:clearVariable(CABIN_VAR)
    player:clearVariable(SEAT_VAR)
end

local function beginSession(player, vehicle, profile, seat)
    local s = {
        player = player, vehicle = vehicle, profile = profile, seat = seat,
        x = profile.door.x, z = profile.door.z, facing = 0, targetFacing = 0,
        moving = false, running = false, pose = "Idle", stillTime = IDLE_DELAY,
        path = nil, onArrive = nil, saveTimer = 0,
    }
    -- The floor as this camper is furnished, before choosing where you stand.
    refreshFurnished(vehicle, profile)
    local stand = M.pendingStand
    M.pendingStand = nil
    local saved = vehicle:getModData()[positionKey(vehicle, profile, seat)]
    if stand and stand.vehicle == vehicle then
        s.x, s.z = nearestWalkable(profile, stand.x, stand.z)
        s.facing = stand.facing or facingFor(1, 0)
    elseif type(saved) == "table" and tonumber(saved.x) and tonumber(saved.z) then
        -- Where you stood, or the nearest free floor if furniture stands there now.
        s.x, s.z = nearestWalkable(profile, saved.x, saved.z)
        s.facing = tonumber(saved.f) or 0
    else
        -- Just inside the door, looking into the camper.
        s.x, s.z = nearestWalkable(profile, s.x, s.z)
        s.facing = facingFor(1, 0)
    end
    s.targetFacing = s.facing
    session = s
    setPoseVars(player, "Idle")
    place(s)
    if java() then
        java().setFacing(player, s.facing)
        java().setStanding(player, true) -- normal standing animations (aim, eat, read...)
        if java().shaderError() and not M.warnedShader then
            M.warnedShader = true
            say(player, "IGUI_MELens_ShaderFailed")
        end
    end
    savePosition(s)
    -- Something to do once standing (getting up to use a piece of furniture).
    local after = M.afterStanding
    M.afterStanding = nil
    if after and after.vehicle == vehicle then
        after.fn()
    end
end

local function endSession()
    if session then
        clearPoseVars(session.player)
        if java() then java().setStanding(session.player, false) end
    end
    session = nil
    if java() then
        java().clearFacing()
        java().clearMarker()
    end
end

local function keyDown(bind)
    local core = getCore()
    local key = core:getKey(bind)
    if key and key > 0 and isKeyDown(key) then
        return true
    end
    if core.getAltKey then
        local alt = core:getAltKey(bind)
        if alt and alt > 0 and isKeyDown(alt) then
            return true
        end
    end
    return false
end

local JOYPAD_DEADZONE = 0.3

local function inputAxes()
    if M.testInput then
        -- Scripted test runs: { ix = -1..1, iy = -1..1 } in screen directions.
        return M.testInput.ix or 0, M.testInput.iy or 0
    end
    local ix, iy = 0, 0
    if keyDown("Forward") then iy = iy - 1 end
    if keyDown("Backward") then iy = iy + 1 end
    if keyDown("Left") then ix = ix - 1 end
    if keyDown("Right") then ix = ix + 1 end
    -- a controller's left stick (screen directions too: up is negative)
    local joypad = JoypadState and JoypadState.players[1]
    if joypad and joypad.id ~= nil and not joypad.focus then
        local jx, jy = getJoypadMovementAxisX(joypad.id) or 0, getJoypadMovementAxisY(joypad.id) or 0
        if jx * jx + jy * jy > JOYPAD_DEADZONE * JOYPAD_DEADZONE then
            ix, iy = ix + jx, iy + jy
        end
    end
    return math.max(-1, math.min(1, ix)), math.max(-1, math.min(1, iy))
end

local function followPath(s)
    while s.path and #s.path > 0 do
        local wp = s.path[1]
        local dx, dz = wp.x - s.x, wp.z - s.z
        local dist = math.sqrt(dx * dx + dz * dz)
        if dist > ARRIVE_DISTANCE then
            return dx, dz, dist
        end
        s.x, s.z = wp.x, wp.z
        table.remove(s.path, 1)
    end
    s.path = nil
    local arrive = s.onArrive
    s.onArrive = nil
    if arrive then
        arrive(s)
    end
    return 0, 0, 0
end

local MARKER_RANGE = 1.3     -- tiles; the exit marker shows (dimmed) this close to it

-- 1 standing on the exit marker, dimmed when close to it, 0 otherwise.
local function markerStrength(s)
    local m = s.profile.exitMarker
    if not m then return 0 end
    local dx, dz = s.x - m.x, s.z - m.z
    if math.abs(dx) <= m.halfX and math.abs(dz) <= m.halfZ then
        return 1.0
    end
    if dx * dx + dz * dz < MARKER_RANGE * MARKER_RANGE then
        return 0.45
    end
    return 0
end

-- Tiles between you and the exit marker's square (0 on it), or nil without a marker.
local function markerDistance(s)
    local m = s.profile.exitMarker
    if not m then return nil end
    local dx = math.max(0, math.abs(s.x - m.x) - m.halfX)
    local dz = math.max(0, math.abs(s.z - m.z) - m.halfZ)
    return math.sqrt(dx * dx + dz * dz)
end

local function updateMarker(s)
    local rv = java()
    local strength = markerStrength(s)
    if not rv or strength == s.markerStrength then return end
    s.markerStrength = strength
    if strength <= 0 then
        rv.clearMarker()
        return
    end
    local profile, m = s.profile, s.profile.exitMarker
    local scale = profile.mesh.scale
    local mx, my, mz = toMesh(profile, m.x, profile.floorY, m.z)
    local c = getCore():getGoodHighlitedColor()
    rv.setMarker(mx, my, mz, m.halfX / scale, m.halfZ / scale, 0.12 / scale, c:getR(), c:getG(), c:getB(), strength)
end

local function step(s, dt)
    local player, vehicle, profile = s.player, s.vehicle, s.profile
    -- Never stuck: if furniture now stands where you are, step onto the nearest free floor.
    if not walkable(profile, s.x, s.z) then
        s.x, s.z = nearestWalkable(profile, s.x, s.z)
    end
    local busy = player:isAsleep() or player:isPerformingAnAction() or getCore():isDoingTextEntry()
        or (isGamePaused and isGamePaused())
    local dx, dz, limit = 0, 0, nil
    if not busy then
        local ix, iy = inputAxes()
        if ix ~= 0 or iy ~= 0 then
            s.path, s.onArrive = nil, nil
            -- Walking by hand ends fast-forward, as it does everywhere else (the game checks its own walking,
            -- IsoPlayer isJustMoved, which the cabin's walking never sets). Walking to furniture does not.
            local speed = UIManager.getSpeedControls and UIManager.getSpeedControls()
            if speed and not isServer() and speed:getCurrentGameSpeed() > 1 then
                speed:SetCurrentGameSpeed(1)
            end
            local wx, wy = iy + ix, iy - ix
            local len = math.sqrt(wx * wx + wy * wy)
            dx, dz = toCamperDirection(vehicle, player:getX(), player:getY(), wx / len, wy / len)
        elseif s.path then
            dx, dz, limit = followPath(s)
            if session ~= s then
                return -- the arrival action left the standing position
            end
        end
    end

    local moving = false
    local len = math.sqrt(dx * dx + dz * dz)
    -- Use the player's Run binding, including a rebound/alternate key. Automatic
    -- approaches to furniture keep walking; aiming and sneaking do not become runs.
    local runHeld = not busy and not limit and not player:isAiming() and not player:isSneaking()
        and ((M.testInput and M.testInput.run == true) or keyDown(KeybindId and KeybindId.RUN or "Run"))
    local pushingDoor = false
    if len > 1e-6 and dt > 0 then
        dx, dz = dx / len, dz / len
        -- Face where you steer (steady while sliding along a wall). Turning round: turn on
        -- the spot first, then walk, instead of sliding backwards while you turn.
        s.targetFacing = facingFor(dx, dz)
        if math.abs(angleDiff(s.targetFacing, s.facing)) <= TURN_FIRST or limit then
            local distance = profile.walkSpeed * (runHeld and RUN_SPEED_MULTIPLIER or 1) * dt
            if limit then
                distance = math.min(distance, limit)
            end
            local ox, oz = s.x, s.z
            local remaining = distance
            while remaining > 1e-6 do
                local stride = math.min(remaining, MAX_MOVE_STEP)
                local nx, nz = s.x + dx * stride, s.z + dz * stride
                if walkable(profile, nx, nz) then
                    s.x, s.z = nx, nz
                elseif walkable(profile, nx, s.z) then
                    s.x = nx
                elseif walkable(profile, s.x, nz) then
                    s.z = nz
                else
                    if s.path then s.path, s.onArrive = nil, nil end
                    break -- blocked; running must not skip narrow furniture/walls
                end
                remaining = remaining - stride
            end
            moving = s.x ~= ox or s.z ~= oz
            -- Walking into the door from the exit marker takes you out, like a doorway.
            local out = profile.exitMarker and profile.exitMarker.outward
            if out and not limit and markerStrength(s) >= 1 and dx * out[1] + dz * out[2] > 0.6 then
                local stepped = (s.x - ox) * out[1] + (s.z - oz) * out[2]
                pushingDoor = stepped < distance * 0.3
            end
        end
    end
    s.pushTime = pushingDoor and (s.pushTime or 0) + dt or 0
    if s.pushTime > PUSH_TO_LEAVE then
        s.pushTime = 0
        M.leave(player)
        return
    end
    -- Aiming: face the point under the mouse, like aiming anywhere else.
    if player:isAiming() and not busy then
        local wx, wy = ISCoordConversion.ToWorld(getMouseXScaled(), getMouseYScaled(), player:getZ())
        local ax, az = toCamperDirection(vehicle, player:getX(), player:getY(), wx - player:getX(), wy - player:getY())
        if ax * ax + az * az > 1e-6 then
            s.targetFacing = facingFor(ax, az)
        end
    end
    s.facing = turnTowards(s.facing, s.targetFacing, TURN_SPEED * math.max(dt, 0.001))

    -- A short delay before the idle pose, so stop-and-go at a wall edge doesn't flicker.
    s.stillTime = moving and 0 or (s.stillTime or 0) + dt
    local walking = moving or s.stillTime < IDLE_DELAY
    s.moving, s.running = walking, moving and runHeld or false
    local pose = s.running and "Run" or walking and "Walk" or "Idle"
    if pose ~= s.pose then
        s.pose = pose
        player:setVariable(CABIN_VAR, pose)
    end
    place(s)
    if java() then java().setFacing(player, s.facing) end
    if M.Sync then M.Sync.send(s, dt) end
    updateMarker(s)

    s.saveTimer = s.saveTimer + dt
    if s.saveTimer > 0.5 then
        s.saveTimer = 0
        savePosition(s)
    end
end

local seatedSince = nil
local furnishTimer = 0
local placeTimer = 0

-- Walking is the default: a movement key gets you up from a seat or bed.
local function standUpOnMove(player, now)
    seatedSince = seatedSince or now
    if now - seatedSince < 500 then
        return -- just sat down; a key still held from walking there must not undo it
    end
    if player:isAsleep() or player:isPerformingAnAction() or getCore():isDoingTextEntry()
            or player:getVariableBoolean("bEnteringVehicle") or player:getVariableBoolean("bExitingVehicle")
            or player:getVariableBoolean("bSwitchingSeat") then
        return
    end
    local ix, iy = inputAxes()
    if ix ~= 0 or iy ~= 0 then
        M.standUp(player)
    end
end

local function update()
    local now = getTimestampMs()
    local dt = lastMs and math.min(0.1, math.max(0, (now - lastMs) / 1000)) or 0
    lastMs = now

    local player = getSpecificPlayer(0)
    if not player or player:isDead() then
        armCutaway(nil)
        if session then endSession() end
        removeWorldLight()
        lightVehicle = nil
        return
    end
    updateLamps(player, dt)
    if M.Interact then
        M.Interact.updateReach(player, dt)
        M.Interact.updateHum(player, dt)
    end
    local vehicle = player:getVehicle()
    local profile = M.profileFor(vehicle)
    if profile and M.inVanillaSeat(player, vehicle, profile) then
        profile = nil        -- driving (or in the cab): the vehicle as the game draws it
    end
    armCutaway(profile and vehicle or nil, profile, dt)
    if not profile then
        if session then endSession() end
        -- left a camper from a turned seat: no turn in the next vehicle
        if M.seatedFacing and java() then
            java().clearFacing()
            M.seatedFacing = nil
        end
        seatedSince = nil
        return
    end
    furnishTimer = furnishTimer + dt
    if furnishTimer > 0.5 then
        furnishTimer = 0
        refreshFurnished(vehicle, profile)
    end
    local seat = vehicle:getSeat(player)
    local cabin = M.cabinSeat(vehicle, profile)
    if cabin < 0 or not M.isStandingSeat(vehicle, profile, seat) then
        if session then endSession() end
        if cabin >= 0 then
            standUpOnMove(player, now)
            -- keep a seated character on our furniture (also after loading a save)
            placeTimer = placeTimer + dt
            if placeTimer > 0.5 or B.states[player] then
                placeTimer = 0
                M.placeSeated(player, vehicle, profile)
            end
        end
        return
    end
    seatedSince = nil
    if not session or session.vehicle ~= vehicle or session.player ~= player or session.seat ~= seat then
        beginSession(player, vehicle, profile, seat)
    end
    if player:getVariableBoolean("bEnteringVehicle") or player:getVariableBoolean("bExitingVehicle") then
        return
    end
    step(session, dt)
end

------------------------------------------------------------------------------------
-- Actions from inside
------------------------------------------------------------------------------------

local function walkTo(x, z, onArrive)
    local s = session
    if not s then return end
    s.path = planPath(s.profile, s.x, s.z, x, z)
    s.onArrive = onArrive
end

-- Walk to a point inside the camper (passenger space), around the furniture.
function M.walkTo(player, x, z, onArrive)
    if session and session.player == player then
        walkTo(x, z, onArrive)
    end
end

-- Which way you face while standing (radians; 0 looks to the vehicle's front, turning towards its left), or nil.
function M.facingOf(player)
    if session and session.player == player then return session.facing end
    return nil
end

-- Whether you are walking to a point now (M.walkTo) or about to do something on arrival.
function M.pathing(player)
    return session ~= nil and session.player == player and (session.path ~= nil or session.onArrive ~= nil)
end

function M.leave(player)
    local s = session
    if not s or s.player ~= player then
        return
    end
    if not s.vehicle:isStopped() then
        say(player, "IGUI_PlayerText_CanNotExitFromMovingCar")
        return
    end
    walkTo(s.profile.door.x, s.profile.door.z, function(arrived)
        local vehicle, seat = arrived.vehicle, arrived.seat
        if vehicle:isExitBlocked(player, seat) then
            say(player, "IGUI_MELens_ExitBlocked")
            return
        end
        arrived.targetFacing = facingFor(-1, 0)
        ISVehicleMenu.onExitAux(player, seat)
    end)
end

-- Seated or lying on one of KI5's seats: put the character on ME: LENS' furniture
-- (where the piece standing at its spot has you lie or sit, MELens.Parts.seatPose) and
-- turn the pose where it needs turning.
local seatVec = nil
function M.placeSeated(player, vehicle, profile)
    local seat = vehicle:getSeat(player)
    if seat < 0 or M.isStandingSeat(vehicle, profile, seat) or M.isVanillaSeat(vehicle, profile, seat) then return end
    -- damnlib's seat poses (lying in a bed, sitting on a bench) need its vehicle flag,
    -- which it only sets when you get in by the game's own enter action.
    if player:getVariableString("damnVehicle") ~= "True" then
        player:setVariable("damnVehicle", "True")
        if DAMN and DAMN.EnterAnimations and DAMN.EnterAnimations.checkSeatPositionVar then
            DAMN.EnterAnimations:checkSeatPositionVar(player, vehicle, seat)
        end
    end
    local script = vehicle:getScript()
    local id = script:getPassenger(seat):getId()
    local place = P.seatPose(vehicle, profile, id)
    if not place then return end
    if place.kind == "bed" then place = B.placement(player, vehicle, seat, place) end
    -- our pose, over the one KI5 registered for its own furniture
    if place.pose and player:getVariableString("damnPosition") ~= place.pose then
        player:setVariable("damnPosition", place.pose)
    end
    local base = script:getPassenger(seat):getPositionById("inside"):getOffset()
    seatVec = seatVec or Vector3f.new()
    seatVec:set(place.x or base:x(), place.y or base:y(), place.z or base:z())
    vehicle:setPassenger(seat, player, seatVec)
    if java() then
        if place.turn then
            java().setFacing(player, place.turn)
            M.seatedFacing = true
        else
            java().clearFacing()
        end
    end
end

-- A seat switch the server and the other players hear about, as the game's own seat switch sends it
-- (ISSwitchVehicleSeat:perform). A bare switchSeat only moves you on your own screen in multiplayer: the server kept
-- you standing while you lay in the bed (found 2026-10-04, dev/mp_seats.ps1).
-- Between standing and a bed or seat the character's animation takes a frame or two to reach its new pose: it stood
-- upright on the bed for those frames before lying down (reported as flickering while it turns into place). It is
-- not drawn for them on this screen and then fades in.
local POSE_HIDE_TICKS = 4
local poseHidden = {}       -- player -> ticks left

local function hideForPoseChange(player)
    for i = 0, getNumActivePlayers() - 1 do
        player:setAlphaAndTarget(i, 0)
    end
    poseHidden[player] = POSE_HIDE_TICKS
end

Events.OnTick.Add(function()
    local done = nil
    for player, left in pairs(poseHidden) do
        if left <= 1 then
            done = done or {}
            done[#done + 1] = player
        else
            poseHidden[player] = left - 1
        end
    end
    for _, player in ipairs(done or {}) do
        poseHidden[player] = nil
        for i = 0, getNumActivePlayers() - 1 do
            player:setTargetAlpha(i, 1)
        end
    end
end)

local function switchSeat(vehicle, player, seatTo, animated)
    local seatFrom = vehicle:getSeat(player)
    if seatFrom ~= seatTo and not animated then
        hideForPoseChange(player)
    end
    vehicle:switchSeat(player, seatTo)
    if isClient() and sendSwitchSeat then
        sendSwitchSeat(vehicle, player, seatFrom, seatTo)
    end
end

-- Sit or lie down on one of KI5's seats (a piece of furniture's): walk to (standX,
-- standZ) in front of it first, then take the seat; `sleep` then goes to sleep.
local vanillaSleepMenu = ISVehicleMenu.onSleep

function M.confirmBedSleep(player, seatId, standX, standZ)
    local vehicle = player:getVehicle()
    if not vehicle or M.sleepBlocker(player, vehicle) then return end
    local state = B.states[player]
    if state and state.phase ~= "Awake" then return end
    local data = getPlayerData(player:getPlayerNum())
    if data and data.vehicleSleepModal then return end
    vanillaSleepMenu(player, vehicle)
    local dialog = data and data.vehicleSleepModal
    if not dialog then return end
    dialog.onclick = function(target, button, playerNum)
        if data.vehicleSleepModal ~= dialog then return end
        data.vehicleSleepModal = nil
        if button.internal ~= "YES" or player:getVehicle() ~= vehicle or M.sleepBlocker(player, vehicle) then return end
        local function sleepAfterAnimation()
            if player:getVehicle() == vehicle and not M.sleepBlocker(player, vehicle) then
                ISVehicleMenu.onConfirmSleep(target, button, playerNum, nil)
            end
        end
        if vehicle:getSeat(player) == M.seatIndex(vehicle, seatId) and B.sleep(player, sleepAfterAnimation) then return end
        M.useSeat(player, seatId, standX, standZ, false, sleepAfterAnimation)
    end
end

function M.useSeat(player, seatId, standX, standZ, sleep, onSleep)
    if sleep then
        return M.confirmBedSleep(player, seatId, standX, standZ)
    end
    M.standingThen(player, function()
        walkTo(standX, standZ, function(arrived)
            local vehicle = arrived.vehicle
            local index = M.seatIndex(vehicle, seatId)
            if index < 0 or not vehicle:isSeatInstalled(index) then
                say(player, "IGUI_PlayerText_VehicleSeatRemoved")
                return
            end
            if vehicle:isSeatOccupied(index) then
                say(player, vehicle:getCharacter(index) and "IGUI_PlayerText_VehicleSomeoneInSeat" or "IGUI_PlayerText_VehicleItemInSeat")
                return
            end
            M.lastStand = { vehicle = vehicle, x = arrived.x, z = arrived.z }
            savePosition(arrived)
            local place = P.seatPose(vehicle, arrived.profile, seatId)
            if place and place.kind == "bed" then
                B.begin(player, vehicle, index, place, onSleep, arrived.x, arrived.z, arrived.profile.floorY)
            end
            switchSeat(vehicle, player, index, place and place.kind == "bed")
            endSession()
            local vanilla = M.isVanillaSeat(vehicle, arrived.profile, index)
            if vanilla then
                vehicle:playPassengerAnim(index, "idle")   -- as the game's own seat switch
            end
            triggerEvent("OnSwitchVehicleSeat", player)
            M.placeSeated(player, vehicle, arrived.profile)   -- after damnlib set KI5's pose
            if vanilla then
                -- the seat's own containers (the glove box) in the loot window
                local pdata = getPlayerData(player:getPlayerNum())
                if pdata then
                    pdata.playerInventory:refreshBackpacks()
                    pdata.lootInventory:refreshBackpacks()
                end
            end
        end)
    end)
end

function M.standUp(player, bedFinished, facing)
    local vehicle = player:getVehicle()
    local profile = M.profileFor(vehicle)
    if not profile then return end
    if M.cabinSeat(vehicle, profile) < 0 or M.isStandingSeat(vehicle, profile, vehicle:getSeat(player)) then return end
    local cabin = M.freeStandingSeat(vehicle, profile)
    if cabin < 0 then
        say(player, "IGUI_MELens_Full")
        return
    end
    if not bedFinished and B.getUp(player, function(turn) M.standUp(player, true, turn) end) then return end
    -- Stand in front of the furniture you were using.
    local seat = vehicle:getSeat(player)
    local x, z = M.seatStandPoint(vehicle, profile, seat)
    if not x and M.lastStand and M.lastStand.vehicle == vehicle then
        x, z = M.lastStand.x, M.lastStand.z
    end
    if not x then
        x, z = profile.door.x, profile.door.z
    end
    M.pendingStand = { vehicle = vehicle, x = x, z = z, facing = facing }
    switchSeat(vehicle, player, cabin, bedFinished)
    triggerEvent("OnSwitchVehicleSeat", player)
end

-- Gets you up from a bed, a dinette or a bus seat inside (E or "Exit" there). True when you are getting up; false
-- when you are not on one of those, or no place to stand is free (then the game's own exit is left to run).
function M.standUpInside(player)
    local vehicle = player and player:getVehicle()
    if not M.seatedInside(player, vehicle) then return false end
    if M.freeStandingSeat(vehicle, nil) < 0 then return false end
    M.standUp(player)
    return true
end

-- Runs fn once you are standing in the camper: now, or after getting up.
function M.standingThen(player, fn)
    if session and session.player == player then
        fn()
        return
    end
    local vehicle = player:getVehicle()
    if not M.profileFor(vehicle) then return end
    M.afterStanding = { vehicle = vehicle, fn = fn }
    M.standUp(player)
end

------------------------------------------------------------------------------------
-- Entering from outside
------------------------------------------------------------------------------------

MELensEnterCabin = ISEnterVehicle:derive("MELensEnterCabin")

function MELensEnterCabin:isValid()
    if self.started then
        return self.vehicle:getCharacter(self.seat) == self.character and self.character:getVehicle() == self.vehicle
    end
    return self.character:getVehicle() == nil and self.vehicle:getCharacter(self.seat) == nil
end

function MELensEnterCabin:update()
    -- Walk-in passengers have no seated get-in animation. Waiting for vanilla's
    -- EnterAnimationFinished can hang forever when another animation node wins.
    -- It also blocks the standing-position packet that seats us on a Lua-only
    -- server. Complete after native entry succeeds; keep vanilla perform/stop.
    if self.vehicle:getCharacter(self.seat) ~= self.character or self.character:getVehicle() ~= self.vehicle then return end
    self.character:ClearVariable("EnterAnimationFinished")
    self.character:ClearVariable("bEnteringVehicle")
    self:forceComplete()
end

function MELensEnterCabin:start()
    local playerNum = self.character:getPlayerNum()
    getCell():setDrag(nil, playerNum)
    local contextMenu = getPlayerContextMenu(playerNum)
    if contextMenu and contextMenu:isAnyVisible() then
        contextMenu:hideAndChildren()
    end
    self.started = true

    local outside = self.vehicle:getPassengerPosition(self.seat, "outside")
    local worldPos = Vector3f.new()
    self.vehicle:getPassengerPositionWorldPos(outside, worldPos)
    if self.character:DistToSquared(worldPos:x(), worldPos:y()) > 2 * 2 then
        return -- not at the door; isValid() ends the action
    end

    self.action:setBlockMovementEtc(true)
    self.character:ClearVariable("EnterAnimationFinished")
    local inside = self.vehicle:getPassengerPosition(self.seat, "inside")
    if not self.vehicle:enter(self.seat, self.character, inside:getOffset()) then return end
    self.character:setVariable(SEAT_VAR, "true")
    self.character:setVariable(CABIN_VAR, "Idle")
    -- A fresh entry starts just inside the door; the saved spot is only for loading a save.
    local door = M.profileFor(self.vehicle).door
    M.pendingStand = { vehicle = self.vehicle, x = door.x, z = door.z }
    self.vehicle:playPassengerSound(self.seat, "enter")
    self.character:SetVariable("bEnteringVehicle", "true")
    self.character:triggerMusicIntensityEvent("VehicleEnter")
end

function MELensEnterCabin:new(character, vehicle, seat)
    local o = ISEnterVehicle.new(self, character, vehicle, seat)
    o.maxTime = -1
    return o
end

function M.canWalkIn(player, vehicle)
    local profile = M.profileFor(vehicle)
    if not profile then return false, nil end
    -- Without the Java part the roof stays on and you would walk around unseen.
    if not java() then return false, "IGUI_MELens_NoJava" end
    local seat = M.cabinSeat(vehicle, profile)
    if seat < 0 then return false, "IGUI_MELens_NotLoaded" end
    if M.freeStandingSeat(vehicle, profile) < 0 then return false, "IGUI_MELens_Full" end
    if not vehicle:isStopped() then return false, "IGUI_MELens_Moving" end
    if player:getVehicle() then return false, nil end
    return true, nil
end

function M.walkIn(player, vehicle)
    local ok, reason = M.canWalkIn(player, vehicle)
    if not ok then
        if reason then say(player, reason) end
        return false
    end
    M.pendingUse = nil
    local seat = M.freeStandingSeat(vehicle, M.profileFor(vehicle))
    ISTimedActionQueue.add(ISPathFindAction:pathToVehicleSeat(player, vehicle, seat))
    local doorPart = vehicle:getPassengerDoor(seat)
    if doorPart and doorPart:getDoor() and doorPart:getInventoryItem() then
        local door = doorPart:getDoor()
        if door:isLocked() then
            if vehicle:isKeyIsOnDoor() then
                local key = vehicle:getCurrentKey()
                vehicle:setKeyIsOnDoor(false)
                vehicle:setCurrentKey(nil)
                player:getInventory():AddItem(key)
            else
                ISTimedActionQueue.add(ISUnlockVehicleDoor:new(player, doorPart))
            end
        end
        if not door:isOpen() then
            ISTimedActionQueue.add(ISOpenVehicleDoor:new(player, vehicle, doorPart))
        end
        ISTimedActionQueue.add(MELensEnterCabin:new(player, vehicle, seat))
        ISTimedActionQueue.add(ISCloseVehicleDoor:new(player, vehicle, doorPart))
    else
        ISTimedActionQueue.add(MELensEnterCabin:new(player, vehicle, seat))
    end
    return true
end

-- Walking is the default way in: entering a walk-in camper by any route (E at the door,
-- seat picker, radial menu, controller prompt) walks you in and leaves you standing.
-- Without the Java part, seats other than the standing position keep the game's own entry.
-- The beds, benches and bus seats inside are not entered from outside: you walk in and use them. When walking in
-- is not possible right now (moving), you are told why instead of being put on a bed through the wall. When every
-- place to stand is taken (multiplayer: a bus has room for one), the seats are entered as the game does it, so
-- the others can still get on.
local function routeEntry(playerObj, vehicle, seat)
    local profile = M.profileFor(vehicle)
    if not profile or not playerObj or playerObj:getVehicle() or not seat or M.isVanillaSeat(vehicle, profile, seat) then
        return false
    end
    if M.cabinSeat(vehicle, profile) < 0 then return false end
    if M.isInsideSeat(vehicle, profile, seat) and M.freeStandingSeat(vehicle, profile) < 0 then return false end
    if M.isStandingSeat(vehicle, profile, seat) or M.isInsideSeat(vehicle, profile, seat) then
        M.walkIn(playerObj, vehicle)
        return true
    end
    return false
end

local vanillaOnEnter = ISVehicleMenu.onEnter
function ISVehicleMenu.onEnter(playerObj, vehicle, seat, ...)
    if routeEntry(playerObj, vehicle, seat) then return end
    return vanillaOnEnter(playerObj, vehicle, seat, ...)
end

-- (a seat's second door: the game's E at a door picks this one for some vehicles)
local vanillaOnEnter2 = ISVehicleMenu.onEnter2
function ISVehicleMenu.onEnter2(playerObj, vehicle, seat, ...)
    if routeEntry(playerObj, vehicle, seat) then return end
    return vanillaOnEnter2(playerObj, vehicle, seat, ...)
end

-- Any other way in (another mod queueing the game's enter action itself) is refused for those seats, while a place
-- to stand is free.
local vanillaEnterValid = ISEnterVehicle.isValid
function ISEnterVehicle:isValid()
    if not self.started and self.character and self.character:getVehicle() == nil and self.vehicle
            and M.isInsideSeat(self.vehicle, nil, self.seat) and M.freeStandingSeat(self.vehicle, nil) >= 0 then
        return false
    end
    return vanillaEnterValid(self)
end

-- Leaving from the standing position always walks to the door first. Leaving a bed, a dinette or a bus seat
-- inside gets you up, standing in front of it (the game would put you outside through the door); only when there
-- is no free place to stand does the game's own exit run.
local vanillaOnExit = ISVehicleMenu.onExit
function ISVehicleMenu.onExit(playerObj, seatFrom, ...)
    if session and session.player == playerObj and not seatFrom then
        return M.leave(playerObj)
    end
    if not seatFrom and M.standUpInside(playerObj) then
        return
    end
    return vanillaOnExit(playerObj, seatFrom, ...)
end

-- Instant "exit" pose for the standing position (no car-seat climb-out).
local vanillaExitStart = ISExitVehicle.start
function ISExitVehicle:start()
    if M.isStanding(self.character) then
        self.character:setVariable(SEAT_VAR, "true")
    end
    return vanillaExitStart(self)
end

------------------------------------------------------------------------------------
-- Context menu: inside, what is under the mouse (MELens_Interact.lua); outside, the
-- way in.
------------------------------------------------------------------------------------

-- The game's own rules for sleeping in a vehicle (the checks of its vehicle radial menu).
function M.sleepBlocker(player, vehicle)
    local stats = player:getStats()
    if stats:get(CharacterStat.FATIGUE) <= 0.3 then
        return "IGUI_Sleep_NotTiredEnough"
    end
    if not vehicle:isStopped() then
        return "IGUI_PlayerText_CanNotSleepInMovingCar"
    end
    if stats:getNumVisibleZombies() > 0 or stats:getNumChasingZombies() > 0 or stats:getNumVeryCloseZombies() > 0 then
        return "IGUI_Sleep_NotSafe"
    end
    if player:getHoursSurvived() - player:getLastHourSleeped() <= 1 then
        return "ContextMenu_NoSleepTooEarly"
    end
    if player:getSleepingTabletEffect() < 2000 then
        local moodles = player:getMoodles()
        if moodles:getMoodleLevel(MoodleType.PAIN) >= 2 and stats:get(CharacterStat.FATIGUE) <= 0.85 then
            return "ContextMenu_PainNoSleep"
        end
        if moodles:getMoodleLevel(MoodleType.PANIC) >= 1 then
            return "ContextMenu_PanicNoSleep"
        end
    end
    return nil
end

local function onFillWorldObjectContextMenu(playerNum, context, worldobjects, test)
    if test then return end
    local player = getSpecificPlayer(playerNum)
    if not player or playerNum ~= 0 then return end
    if player:getVehicle() then
        if M.Interact then
            M.Interact.fillMenu(player, context)
        end
        return
    end
    local vehicle = ISVehicleMenu.getVehicleToInteractWith(player)
    local profile = M.profileFor(vehicle)
    if not profile then return end
    -- The dashboard from outside too: filling the generator and the water tank.
    if M.Interact and M.cabinSeat(vehicle) >= 0 then
        M.Interact.addDashboardOption(player, vehicle, context)
    end
    local text = profile.kind == "bus" and "ContextMenu_MELens_WalkInBus"
        or profile.kind == "cargo" and "ContextMenu_MELens_WalkInCargo" or "ContextMenu_MELens_WalkIn"
    local option = context:addOptionOnTop(getText(text), player, M.walkIn, vehicle)
    local ok, reason = M.canWalkIn(player, vehicle)
    if not ok then
        option.notAvailable = true
        if reason then
            local tip = ISWorldObjectContextMenu.addToolTip()
            tip.description = getText(reason)
            option.toolTip = tip
        end
    end
end

------------------------------------------------------------------------------------
-- The game's vehicle radial menu, seat picker and seat switching. Inside a walk-in
-- camper you use the furniture instead of picking seats, so the radial menu has the
-- camper's dashboard where "Switch seat" was.
------------------------------------------------------------------------------------

local function walkInCamper(playerObj)
    local vehicle = playerObj and playerObj:getVehicle()
    local profile = M.profileFor(vehicle)
    if vehicle and java() and M.cabinSeat(vehicle, profile) >= 0 and not M.inVanillaSeat(playerObj, vehicle, profile) then
        return vehicle
    end
    return nil
end

-- From the driver's seat of a vehicle you can walk inside (a bus): get up.
function M.getUpInside(playerObj)
    local vehicle = playerObj and playerObj:getVehicle()
    local profile = M.profileFor(vehicle)
    if not profile or not vehicle:isStopped() then
        say(playerObj, "IGUI_MELens_Moving")
        return
    end
    M.standUp(playerObj)
end

local vanillaShowRadialMenu = ISVehicleMenu.showRadialMenu
function ISVehicleMenu.showRadialMenu(playerObj, ...)
    local result = vanillaShowRadialMenu(playerObj, ...)
    local seated = playerObj and playerObj:getVehicle()
    local seatedProfile = M.profileFor(seated)
    if seated and java() and M.driverSpot(seatedProfile) and M.inVanillaSeat(playerObj, seated, seatedProfile)
            and seated:getSeat(playerObj) == M.seatIndex(seated, seatedProfile.driver.seat) then
        local menu = getPlayerRadialMenu(playerObj:getPlayerNum())
        if menu and menu:isReallyVisible() then
            menu:addSlice(getText("ContextMenu_MELens_GetUp"), getTexture("media/ui/vehicles/vehicle_exit.png"),
                M.getUpInside, playerObj)
        end
        return result
    end
    local vehicle = walkInCamper(playerObj)
    local menu = vehicle and getPlayerRadialMenu(playerObj:getPlayerNum())
    if menu and menu:isReallyVisible() and menu.slices then
        local slices = menu.slices
        local switchSeat = getText("IGUI_SwitchSeat")
        menu:clear()
        menu:addSlice(getText("ContextMenu_MELens_Dashboard"), getTexture("media/ui/vehicles/vehicle_lightsON.png"),
            function() M.Dashboard.open(playerObj, vehicle) end)
        -- without a mouse (a controller): the menu of the nearest furniture
        menu:addSlice(getText("ContextMenu_MELens_UseNearby"), getTexture("media/ui/vehicles/vehicle_changeseats.png"),
            function() M.Interact.nearbyMenu(playerObj) end)
        for _, slice in ipairs(slices) do
            if slice.text ~= switchSeat then
                local c = slice.command or {}
                menu:addSlice(slice.text, slice.texture, c[1], c[2], c[3], c[4], c[5], c[6], c[7])
            end
        end
    end
    return result
end

-- Inside, seats are chosen by using the furniture; the seat picker stays closed. Outside a camper (whose seats are
-- all inside) "Enter vehicle" walks you in instead of offering beds and benches you cannot get to from outside; a bus
-- or a box truck still shows the picker for its driver's seat and cab.
local vanillaShowSeatUI = ISVehicleMenu.onShowSeatUI
function ISVehicleMenu.onShowSeatUI(playerObj, vehicle, ...)
    if walkInCamper(playerObj) == vehicle and vehicle then
        return
    end
    local profile = vehicle and M.profileFor(vehicle)
    if profile and playerObj and not playerObj:getVehicle() and java() and M.cabinSeat(vehicle, profile) >= 0
            and not (profile.vanillaSeats and #profile.vanillaSeats > 0) and M.freeStandingSeat(vehicle, profile) >= 0 then
        M.walkIn(playerObj, vehicle)
        return
    end
    return vanillaShowSeatUI(playerObj, vehicle, ...)
end

-- Outside, the picker lists the standing position like a seat; choosing it walks you in
-- (ISVehicleMenu.onEnter above). Vanilla would call it uninstalled.
local vanillaSeatInstalled = ISVehicleSeatUI.isSeatInstalled
function ISVehicleSeatUI:isSeatInstalled(seat)
    if self.vehicle and seat and seat >= 0 and M.isStandingSeat(self.vehicle, nil, seat) then
        return true
    end
    return vanillaSeatInstalled(self, seat)
end

-- Switching to the standing position is getting up; from standing to a seat, walk there.
local vanillaSwitchSeat = ISVehicleMenu.onSwitchSeat
function ISVehicleMenu.onSwitchSeat(playerObj, seatTo, ...)
    local vehicle = playerObj and playerObj:getVehicle()
    local profile = M.profileFor(vehicle)
    local cabin = M.cabinSeat(vehicle, profile)
    if cabin >= 0 then
        if M.isStandingSeat(vehicle, profile, seatTo) then
            return M.standUp(playerObj)
        end
        if session and session.player == playerObj then
            local x, z = M.seatStandPoint(vehicle, profile, seatTo)
            local id = seatTo and seatTo >= 0 and vehicle:getScript():getPassenger(seatTo):getId()
            if x and id then
                M.useSeat(playerObj, id, x, z, false)
            end
            return
        end
    end
    return vanillaSwitchSeat(playerObj, seatTo, ...)
end

-- "Sleep" from the vehicle radial menu while standing: the nearest free bed.
local vanillaOnSleep = ISVehicleMenu.onSleep
function ISVehicleMenu.onSleep(playerObj, vehicle, ...)
    local profile = M.profileFor(vehicle)
    local seat = vehicle and vehicle:getSeat(playerObj)
    if profile and seat and seat >= 0 then
        local id = vehicle:getScript():getPassenger(seat):getId()
        if P.seatKindAt(vehicle, profile, id) == "bed" then
            local x, z = M.seatStandPoint(vehicle, profile, seat)
            return M.confirmBedSleep(playerObj, id, x, z)
        end
    end
    local s = session
    if s and s.player == playerObj and s.vehicle == vehicle and M.Interact then
        return M.Interact.sleepInCamper(playerObj, vehicle)
    end
    return vanillaOnSleep(playerObj, vehicle, ...)
end

------------------------------------------------------------------------------------
-- Interact key (the game's "use vehicle", E): standing on the green exit marker it leaves,
-- like E at a car door; next to a bed, a dinette or a bus seat (or a bus's driver's seat)
-- it sits or lies you down there; on one of those, it gets you up, standing inside.
------------------------------------------------------------------------------------

local vanillaUseVehicle = nil

-- The game's use key at a walk-in vehicle's way in walks in. At a camper's door the game
-- already enters (see ISVehicleMenu.onEnter above), but at a box truck's rear door it would
-- only open the door.
function M.enterOnUse(character, vehicle)
    local profile = M.profileFor(vehicle)
    if not profile or not java() or character:getVehicle() then return false end
    if M.freeStandingSeat(vehicle, profile) < 0 then return false end      -- full: the game's own door (a seat)
    local part = vehicle:getUseablePart(character)
    if part and part:getId() == profile.standing.door then
        M.walkIn(character, vehicle)
        return true
    end
    return false
end

M.DOOR_REACH = 1.6      -- tiles from the way in (the standing place's "outside" point) within which E outside walks in

local doorVec = nil

-- Whether you stand close to the way in of a walk-in vehicle, outside.
function M.nearWayIn(character, vehicle, profile)
    local seat = M.cabinSeat(vehicle, profile)
    local outside = seat >= 0 and vehicle:getPassengerPosition(seat, "outside")
    if not outside then return true end
    doorVec = doorVec or Vector3f.new()
    vehicle:getPassengerPositionWorldPos(outside, doorVec)
    return character:DistToSquared(doorVec:x(), doorVec:y()) <= M.DOOR_REACH * M.DOOR_REACH
end

-- The seats of a vehicle that a door of it lets in (the game's Vehicles.Use.Door takes the first).
local function seatsOfDoor(vehicle, part)
    local seats = {}
    for seat = 0, vehicle:getMaxPassengers() - 1 do
        if vehicle:getPassengerDoor(seat) == part or vehicle:getPassengerDoor2(seat) == part then
            seats[#seats + 1] = seat
        end
    end
    return seats
end

-- E outside a walk-in vehicle at a door other than its way in (a bus's rear door), with a place to stand free: the
-- game would take a bed, a bench or a bus seat behind that door, which the mod turns into walking in, and you would
-- run round to the way in. Nothing happens instead, unless you stand close to the way in anyway. E at the way in
-- still walks in, and the menus still offer "Walk into". (In Build 42.21 BaseVehicle.getBestSeat always answers -1,
-- so E away from any door does nothing by itself; another mod's entry key is handled at ISVehicleMenu.onEnterAux.)
function M.ignoreUseOutside(character, vehicle)
    local profile = M.profileFor(vehicle)
    if not profile or not java() or character:getVehicle() or M.cabinSeat(vehicle, profile) < 0 then return false end
    if M.freeStandingSeat(vehicle, profile) < 0 then return false end      -- full: the game's own doors
    local part = vehicle:getUseablePart(character)
    if not part or not part:getDoor() or part:getId() == profile.standing.door then return false end
    local seats = seatsOfDoor(vehicle, part)
    if #seats == 0 or not M.isInsideSeat(vehicle, profile, seats[1]) then return false end
    return not M.nearWayIn(character, vehicle, profile)
end

-- Another mod that queues the game's way to a seat itself (Get In The Damn Car! takes the nearest free seat of any
-- vehicle within ten tiles when you press its key: a camper's bed or bench, through the camper's door) would send you
-- running round to the door for a seat you do not get from outside. For a walk-in vehicle with a free place to stand:
-- close to its way in you walk in; further away nothing happens. Full, or a seat that keeps the game's entry (a bus
-- driver's, a box truck's cab): the game's way as before.
local function routeAux(playerObj, vehicle, seat)
    local profile = vehicle and M.profileFor(vehicle)
    if not profile or not playerObj or playerObj:getVehicle() or not seat or not java() then return false end
    if M.cabinSeat(vehicle, profile) < 0 or M.isVanillaSeat(vehicle, profile, seat) then return false end
    if not (M.isStandingSeat(vehicle, profile, seat) or M.isInsideSeat(vehicle, profile, seat)) then return false end
    if M.freeStandingSeat(vehicle, profile) < 0 then return false end
    if M.nearWayIn(playerObj, vehicle, profile) then
        M.walkIn(playerObj, vehicle)
    end
    return true
end

local vanillaEnterAux = ISVehicleMenu.onEnterAux
function ISVehicleMenu.onEnterAux(playerObj, vehicle, seat, ...)
    if routeAux(playerObj, vehicle, seat) then return end
    return vanillaEnterAux(playerObj, vehicle, seat, ...)
end

local vanillaEnterAux2 = ISVehicleMenu.onEnterAux2
function ISVehicleMenu.onEnterAux2(playerObj, vehicle, seat, ...)
    if routeAux(playerObj, vehicle, seat) then return end
    return vanillaEnterAux2(playerObj, vehicle, seat, ...)
end

-- E while standing inside: on the exit marker it leaves; otherwise the nearer of a seat within reach and the door
-- (the marker showing) wins, so E by the door still gets you out.
local function useInside(character, vehicle)
    local s = session
    if markerStrength(s) >= 1 then
        M.leave(character)
        return
    end
    local seat, why
    if M.Interact then
        seat, why = M.Interact.seatNear(character, vehicle, s.profile)
    end
    local door = markerDistance(s)
    if seat and (not door or seat.d <= door) then
        M.useSeat(character, seat.seatId, seat.x, seat.z, false)
    elseif markerStrength(s) > 0 then
        M.leave(character)
    elseif why then
        say(character, why)
    end
end

local function onUseVehicle(character, vehicle, ...)
    if session and session.player == character and session.vehicle == vehicle then
        useInside(character, vehicle)
    elseif M.standUpInside(character) then
        return
    elseif M.enterOnUse(character, vehicle) then
        return
    elseif M.ignoreUseOutside(character, vehicle) then
        return
    elseif vanillaUseVehicle then
        vanillaUseVehicle(character, vehicle, ...)
    end
end

-- The game's handler is registered by server Lua, which loads after this file.
local function hookUseVehicle()
    if vanillaUseVehicle or not (VehicleUtils and VehicleUtils.OnUseVehicle) then
        return
    end
    vanillaUseVehicle = VehicleUtils.OnUseVehicle
    Events.OnUseVehicle.Remove(vanillaUseVehicle)
    Events.OnUseVehicle.Add(onUseVehicle)
end

local function onGameStart()
    armedVehicle = nil
    armedLamps = nil
    session = nil
    lastMs = nil
    seatedSince = nil
    furnished.vehicle, furnished.key, furnished.grid = nil, nil, nil
    M.afterStanding = nil
    if M.Interact then M.Interact.reset() end
    lightVehicle = nil
    worldLight = nil -- a new cell; the old one's light sources are gone
    hookUseVehicle()
    if not java() then
        print("[ME_LENS] Java part not loaded (ZombieBuddy approval?); the roof cutaway is disabled.")
    end
end

local function onMainMenuEnter()
    if java() then
        java().clearCutaway()
        java().clearFacing()
        java().clearMarker()
        java().clearStanding()
    end
    armedVehicle = nil
    armedLamps = nil
    session = nil
    lightVehicle = nil
    worldLight = nil
    furnished.vehicle, furnished.key, furnished.grid = nil, nil, nil
    M.afterStanding = nil
    if M.Interact then M.Interact.reset() end
end

function M.debugState()
    local player = getSpecificPlayer(0)
    local vehicle = player and player:getVehicle()
    return {
        version = M.VERSION,
        java = java() and java().status() or "missing",
        inVehicle = vehicle ~= nil,
        script = vehicle and vehicle:getScript():getFullName() or nil,
        seat = vehicle and vehicle:getSeat(player) or -1,
        cabinSeat = vehicle and M.cabinSeat(vehicle) or -1,
        standing = session ~= nil,
        x = session and session.x, z = session and session.z,
        facing = session and session.facing,
        moving = session and session.moving,
        running = session and session.running,
        pose = session and session.pose,
        pathing = session and session.path ~= nil,
    }
end

Events.OnGameStart.Add(onGameStart)
Events.OnMainMenuEnter.Add(onMainMenuEnter)
Events.OnTick.Add(update)
Events.OnFillWorldObjectContextMenu.Add(onFillWorldObjectContextMenu)

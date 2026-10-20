--
-- ME: LENS camper profiles.
--
-- Coordinates are in the vehicle's runtime passenger space: the space the game uses
-- for a passenger's offset once the vehicle script is loaded (x = left/right with +x
-- on the camper's left, z = back/front with +z towards the hitch, y = height). Units
-- are world tiles. For KI5's Flying Cloud this is 0.09 x the body mesh coordinates.
--
-- cutPlanes are in the body mesh's own space as the game loads it: FBX units with the
-- importer's left-handed flip, so height runs along -z (raw FBX z = -mesh z).
-- Fragments with a*x + b*y + c*z + d > 0 are not drawn while you are inside, which
-- removes the roof and the upper walls. { 0, 0, -1, -7 } cuts 7 FBX units above the
-- mesh origin (about 0.8 tiles above the Flying Cloud's floor).
--

MELens = MELens or {}
MELens.Profiles = MELens.Profiles or {}

MELens.Profiles["Base.Trailer54FlyingCloud22"] = {
    name = "Flying Cloud 22",
    kind = "camper",
    seatId = "MELensCabin",
    floorY = -0.14,

    -- Passenger space (tiles) to the body's mesh space, for lamp positions:
    -- mesh x = -px / scale, mesh y = pz / scale, mesh z = lift - py / scale.
    mesh = { scale = 0.09, lift = 0.666 },

    -- The inside shell (floor, inside walls, wheel-well boxes and the utility panel) that
    -- replaces KI5's furnished interior in the camper you are in. Every other camper is
    -- drawn exactly as KI5 made it.
    shell = { models = { "MELensShell_cloud22_floor", "MELensShell_cloud22_walls" } },
    -- KI5 models the Java part hides in the camper you are in: a number keeps only what is
    -- above that height (KI5's interior model also carries the ceiling and part of the
    -- roof), true hides the whole model (KI5's seat and bed cushions).
    hideKI5 = {
        TrailerKI5camperFlyingCloud22Interior = 1.45,
        ["54CloudCamperSeatfl"] = true,
        ["54CloudCamperSeatfr"] = true,
        ["54CloudCamperSeatrl"] = true,
        ["54CloudCamperSeatrr"] = true,
        ["54CloudCamperBed1"] = true,
        ["54CloudCamperBed2"] = true,
        -- the window glass (cut down with the walls it shows as black slabs on the wall
        -- tops): the shell's openings show the outside. The door leaf stays, painted inside.
        ["mesh:cloud22_window_fl"] = true, ["mesh:cloud22_window_fl_a"] = true,
        ["mesh:cloud22_window_fr"] = true, ["mesh:cloud22_window_fr_a"] = true,
        ["mesh:cloud22_window_ml"] = true, ["mesh:cloud22_window_ml_a"] = true,
        ["mesh:cloud22_window_rl"] = true, ["mesh:cloud22_window_rl_a"] = true,
        ["mesh:cloud22_window_rr"] = true, ["mesh:cloud22_window_rr_a"] = true,
        ["mesh:cloud22_windshield_front"] = true, ["mesh:cloud22_windshield_front_a"] = true,
        ["mesh:cloud22_windshield_rear"] = true, ["mesh:cloud22_windshield_rear_a"] = true,
    },

    -- Light inside while the roof is cut away (see the cutaway shaders).
    light = {
        interiorModels = { "MELensShell_cloud22_floor", "MELensShell_cloud22_walls" },
        daylight = 1.0,    -- share of the outside ambient light that reaches the inside
        minimum = 0.18,    -- constant light: the inside of a camper is never pitch black
        topDown = 0.5,     -- surfaces facing up (floor, tables, beds) get more light
        lamps = {          -- ceiling lamps, passenger space; reach in tiles
            { x = 0.0, y = 0.5, z = 1.3 },
            { x = 0.0, y = 0.5, z = -0.9 },
        },
        lampReach = 1.9,
        lampColour = { 1.0, 0.94, 0.82 },
        -- The game light placed at the camper while the lamps are on: lights you and
        -- spills softly outside. Kept dim; the vehicle takes its brightness from it.
        worldColour = { 0.8, 0.75, 0.65 },
        worldRadius = 3,
    },
    -- KI5's own body details inside the shell's lining (a tongue's arm tips at the front
    -- corners) are not drawn while you are inside; the outline comes with the walk grid.
    clipBody = true,
    -- The hull keeps bits of its windows (the seal round each opening, a pillar between two
    -- panes) that would stand on the cut walls' ramps as thin black posts: the body is not
    -- drawn inside these boxes (the windows', passenger space). The shell's walls close them.
    windowBoxes = {
        { x = {  0.55, 1.0 },  y = { 0.52, 1.2 },  z = {  1.53, 2.13 } },
        { x = { -1.0, -0.55 }, y = { 0.52, 1.2 },  z = {  1.53, 2.13 } },
        { x = {  0.55, 1.0 },  y = { 0.88, 1.21 }, z = {  0.85, 1.45 } },
        { x = {  0.55, 1.0 },  y = { 0.9, 1.2 },   z = { -1.0, -0.61 } },
        { x = { -1.0, -0.55 }, y = { 0.9, 1.2 },   z = { -1.0, -0.61 } },
        { x = { -0.45, 0.45 }, y = { 0.64, 1.09 }, z = {  2.4, 3.2 } },
        { x = { -0.4, 0.4 },   y = { 0.56, 0.94 }, z = { -2.6, -1.9 } },
    },
    -- the black rubber jambs of the door's opening between the lining and the leaf: painted like the room too
    -- (the door's extent z 0.79 .. 1.45, y -0.27 .. 1.36, a hand wider; make_vehicles.py writes these for the others)
    jambBoxes = {
        { x = { -1.4, -0.6 }, y = { -0.32, 1.46 }, z = { 0.65, 1.59 } },
    },
    -- the inside of the door leaf is bare black: painted like the room's walls
    doorPaint = { 0.80, 0.78, 0.72 },

    -- Low / Medium / High walls (mod options). Medium keeps the window sills.
    cutPlanes = {
        { 0.0, 0.0, -1.0, -4.5 },
        { 0.0, 0.0, -1.0, -7.0 },
        { 0.0, 0.0, -1.0, -9.5 },
    },
    -- Walls facing the camera are cut down to this height (passenger space, tiles),
    -- like the game's cutaway of building walls. The floor is at floorY.
    nearCutY = 0.24,
    walkSpeed = 1.35,
    aisleX = 0.02,

    -- The standing passenger position ME: LENS appends to KI5's script (see below).
    standing = {
        door = "DoorFrontRight",
        area = "SeatFrontRight",
        inside = { -0.675, -0.14, 1.10 },
        outside = { -1.25, -0.71, 1.02 },
    },

    -- Where you stand just inside the door; leaving walks you here first.
    door = { x = -0.675, z = 1.10 },

    -- The green exit marker on the floor by the door (half sizes in tiles): the whole
    -- entrance. Standing on it, the interact key leaves the camper, like E at a car door,
    -- and so does walking into the door (outward: the door's direction, passenger x/z).
    exitMarker = { x = -0.63, z = 1.12, halfX = 0.30, halfZ = 0.38, outward = { -1, 0 } },

    -- Where the centre of your character may be: the empty shell's grid, generated with
    -- the shell (MELens_WalkGrid_FlyingCloud22_Shell.lua); installed furniture is
    -- blocked out on top of it. Hand-made rectangles if the grid is missing.
    walkGrid = "Base.Trailer54FlyingCloud22.shell",
    walkable = {
        { x1 = -0.19, x2 = 0.23, z1 = -1.64, z2 = 2.09 }, -- aisle, rear to front
        { x1 = -0.72, x2 = -0.18, z1 = 0.78, z2 = 1.40 }, -- entrance by the door
    },

    -- Furniture spots: where RV furniture stands, its back against a wall. x, z: the
    -- middle of the piece's back edge (passenger space); wall: front / back / left /
    -- right; length and depth: the room there. seats: KI5's passenger seats a bed (for
    -- lying) or a bench (for sitting) there lets you use; where you lie or sit on the
    -- piece comes from its shape (MELens.Parts.seatPose). head: which way a bed's head
    -- lies (default: the front along a side wall, the right across the front or back).
    -- default: the piece a camper comes with.
    spots = {
        { x = 0.0, z = 2.68, wall = "front", length = 1.50, depth = 0.62, default = "bed", seats = { "FrontB" } },
        { x = 0.844, z = 1.36, wall = "left", length = 1.50, depth = 0.55, default = "bed", seats = { "SideB" } },
        { x = 0.844, z = -0.555, wall = "left", length = 1.12, depth = 0.55, default = "dinette", seats = { "FrontL", "FrontR" } },
        { x = -0.834, z = -1.10, wall = "right", length = 1.12, depth = 0.55, default = "dinette", seats = { "RearL", "RearR" } },
        { x = -0.844, z = 0.02, wall = "right", length = 1.00, depth = 0.52, default = "kitchen" },
        { x = -0.854, z = 1.78, wall = "right", length = 0.52, depth = 0.52, default = "fridge" },
        { x = 0.844, z = 0.31, wall = "left", length = 0.52, depth = 0.52, default = "cabinet" },
        { x = 0.0, z = -2.14, wall = "back", length = 0.52, depth = 0.32, default = "heater" },
    },

    -- The wheel wells (passenger space; the shell's wooden boxes over the tyres). They are
    -- open to the outside through the wheel arches, so furniture standing over them is
    -- not drawn inside them.
    wheelWells = {
        { x = { 0.59, 0.90 }, y = { -0.45, 0.10 }, z = { -0.37, 0.31 } },
        { x = { -0.90, -0.59 }, y = { -0.45, 0.10 }, z = { -0.37, 0.31 } },
    },

    -- The utility panel on the wall behind the door (part of the shell model): the
    -- lights switch and the camper's dashboard. Centre and half sizes, passenger space.
    panel = { x = -0.854, y = 0.155, z = 0.67, halfX = 0.05, halfY = 0.075, halfZ = 0.09 },

    -- Tanks: litres of fresh water, litres of petrol in the generator.
    waterTank = 60,
    fuelTank = 20,
}

function MELens.profileFor(vehicle)
    local script = vehicle and vehicle:getScript()
    return script and MELens.Profiles[script:getFullName()] or nil
end

--
-- The part model offset that puts an ME: LENS model's origin at passenger position
-- (px, py, pz). Checked in game with a calibration box: a part offset moves a model by
-- 0.9 x offset, and KI5's campers carry a 0.06 tile shift in height and length.
--
function MELens.modelOffset(px, py, pz)
    return { px / 0.9, (py - 0.06) / 0.9, (pz + 0.06) / 0.9 }
end

--
-- Extend each supported camper script once the scripts are loaded: the standing
-- passenger, the inside shell, and ME: LENS' parts (MELens_Parts.lua). Appending at
-- runtime (the same way damnlib adds skins) guarantees it comes after KI5's own seats
-- and parts, so KI5's seat numbers and saved seats never shift. Offsets are set
-- explicitly in runtime units after the merge.
--
-- Places to stand in one camper (multiplayer: one per player inside): the profile's seatId,
-- then seatId .. "2", "3", ... appended after it, so the first keeps its index in old saves.
MELens.STANDING_SEATS = 4

-- The game's multiplayer seat bookkeeping (zombie.network.PassengerMap, MAX_PASSENGERS) holds 16 seats per vehicle:
-- every client inside a vehicle with more reads past its table each frame, throws and is disconnected. The school
-- bus has 15 seats of its own, so four places to stand made it 19, and a hosted world in which a player was saved
-- in the bus could no longer be joined (2026-10-06). A vehicle gets as many places to stand as fit under 16
-- (MELens.addStandingPositions works it out per profile: profile.standingCount).
MELens.MAX_SEATS = 16

function MELens.standingIds(profile)
    local count = profile.standingCount or MELens.STANDING_SEATS
    local ids = {}
    for i = 1, count do
        ids[i] = i == 1 and profile.seatId or (profile.seatId .. i)
    end
    return ids
end

-- How many places to stand fit in a profile's vehicles: the fewest over its scripts (they share the ids), the
-- script's own seats counted without ours (an earlier call may have merged them already).
local function standingCounts(manager)
    local counts = {}
    for fullName, profile in pairs(MELens.Profiles) do
        local script = manager:getVehicle(fullName)
        if script and profile.standing then
            local own = script:getPassengerCount()
            for i = 1, MELens.STANDING_SEATS do
                local id = i == 1 and profile.seatId or (profile.seatId .. i)
                if script:getPassengerIndex(id) >= 0 then own = own - 1 end
            end
            local fit = math.max(0, math.min(MELens.STANDING_SEATS, MELens.MAX_SEATS - own))
            counts[profile] = math.min(counts[profile] or fit, fit)
        end
    end
    for profile, n in pairs(counts) do
        if profile.standingCount ~= n then
            profile.standingCount = n
            if n < MELens.STANDING_SEATS then
                print("[ME_LENS] " .. tostring(profile.name or profile.seatId) .. ": " .. n .. " place(s) to stand (16 seats at most)")
            end
        end
    end
end

-- Standing passengers still need a seat-container part: BaseVehicle.getAllSeatParts()
-- indexes those parts by passenger, and other vehicle mods use that lookup on entry
-- and when changing seats. CombatManager also reads its ItemContainer when aiming
-- from a vehicle, even for a standing passenger. It must stay present and empty.
function MELens.standingContainerTest(vehicle, part, chr)
    return false
end

function MELens.initStandingPart(vehicle, part)
    -- Repair old saves whose init hook removed this container. Never replace an
    -- existing container or discard its contents; native combat requires it.
    local container = part:getItemContainer()
    if not container then
        container = ItemContainer.new()
        container:setType(part:getId())
        part:setItemContainer(container)
    end
    -- A server enters a player into a seat with BaseVehicle.enter(seat, character) when the client's enter packet
    -- arrives, and that refuses a seat whose part holds no item: the server never knew a standing player was in the
    -- vehicle (no walking sync, no presence for the actions, zombies treat the player as outside). An item that
    -- nothing else uses stands in; a client gets it from the server with the vehicle.
    if part:getInventoryItem() == nil and not isClient() then
        local item = instanceItem("Base.MELensRV_Seat")
        if item then
            part:setInventoryItem(item)
        end
    end
    container:setCapacity(0)
    container:setExplored(true)
    container:setAcceptItemFunction("MELens.standingContainerTest")
end

function MELens.addStandingPositions()
    local manager = getScriptManager()
    if not manager then return end
    standingCounts(manager)
    for fullName, profile in pairs(MELens.Profiles) do
        local script = manager:getVehicle(fullName)
        local s = profile.standing
        if script and s then
            -- Merging is idempotent: an existing passenger is updated, not duplicated.
            for _, id in ipairs(MELens.standingIds(profile)) do
                script:Load(script:getName(), table.concat({
                    "{ passenger ", id, " {",
                    " door = ", s.door, ",",
                    " area = ", s.area, ",",
                    " showPassenger = true,",
                    " hasRoof = true,",
                    " position inside { offset = 0 0 0, rotate = 0 0 0, }",
                    " position outside { offset = 0 0 0, rotate = 0 0 0, }",
                    " } }",
                }))
            end
            -- Only with the Java part, which hides what the shell replaces (the shell
            -- itself is ME: LENS' own part, see MELens_Parts.lua); without it KI5's own
            -- interior stays as it is.
            if profile.shell and MELensRV then
                local m = profile.mesh
                for model, keep in pairs(profile.hideKI5 or {}) do
                    if keep == true then
                        MELensRV.setKeepPlane(model, 0, 0, 0, 1)
                    elseif type(keep) == "table" and keep.plane then
                        -- any plane in the model's mesh space: a*x + b*y + c*z + d > 0 is hidden
                        local p = keep.plane
                        MELensRV.setKeepPlane(model, p[1], p[2], p[3], p[4])
                    else
                        -- remove below passenger height `keep`: mesh z > lift - keep / scale
                        MELensRV.setKeepPlane(model, 0, 0, 1, keep / m.scale - m.lift)
                    end
                end
            end
            if MELens.Parts and MELens.Parts.extendScript then
                MELens.Parts.extendScript(script, profile)
            end
            for _, id in ipairs(MELens.standingIds(profile)) do
                -- Append after the existing parts so their order and all passenger IDs
                -- remain stable. Load merges by ID, including on later boot/world events.
                script:Load(script:getName(), table.concat({
                    "{ part Seat", id, " {",
                    " category = nodisplay, area = ", s.area, ", itemType = Base.MELensRV_Seat,",
                    " container { seat = ", id, ", capacity = 0,",
                    " conditionAffectsCapacity = false, test = MELens.standingContainerTest, }",
                    " lua { create = MELens.initStandingPart, init = MELens.initStandingPart, }",
                    " } }",
                }))
                local index = script:getPassengerIndex(id)
                if index >= 0 then
                    -- Runtime Load records seatId but leaves the resolved index at -1.
                    -- Loaded() cannot be repeated: it rescales KI5 geometry and item IDs.
                    -- The client bridge resolves just this binding. A server runs without
                    -- it, so the game there finds no part for the seat and turns a walk-in
                    -- down; MELens_Sync.lua seats the player on their first position.
                    if MELensRV then
                        MELensRV.bindSeatContainer(script, "Seat" .. id, id)
                    end
                    local passenger = script:getPassenger(index)
                    passenger:getPositionById("inside"):getOffset():set(s.inside[1], s.inside[2], s.inside[3])
                    passenger:getPositionById("outside"):getOffset():set(s.outside[1], s.outside[2], s.outside[3])
                else
                    print("[ME_LENS] could not add the standing position " .. id .. " to " .. fullName)
                end
            end
        end
    end
end

MELens.addStandingPositions()
Events.OnGameBoot.Add(MELens.addStandingPositions)
Events.OnInitWorld.Add(MELens.addStandingPositions)

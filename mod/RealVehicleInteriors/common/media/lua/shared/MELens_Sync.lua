--
-- ME: LENS multiplayer: where everyone stands inside a camper. Walking is a passenger offset the
-- game does not send to other players, so each client sends its own (a few times a second while
-- it changes), the server keeps it (timed actions check reach against it) and passes it on, and
-- every other client places that player there, facing the same way, with the walking or idle pose.
-- Single player sends nothing.
--
MELens = MELens or {}
local M = MELens
M.Sync = M.Sync or {}
local S = M.Sync

local MODULE, POS = "MELens", "pos"
local SEND_EVERY = 0.1      -- seconds between sends while moving
local KEEPALIVE = 2.0       -- seconds between sends while still (a late joiner sees you too)
local INTERPOLATE_MS = SEND_EVERY * 1000
local SNAP_DISTANCE = 1.0   -- a correction this large or a route change should not glide
local CABIN_VAR, SEAT_VAR = "MELensCabin", "MELensCabinSeat"

local vec, worldVec
local PENDING_MS = 5000     -- allow vehicle/player replication to arrive after our position packet

local function finite(value)
    local n = tonumber(value)
    return n and n == n and math.abs(n) < math.huge and n or nil
end

local function normalizeAngle(angle)
    angle = math.fmod(angle, 2 * math.pi)
    while angle > math.pi do angle = angle - 2 * math.pi end
    while angle <= -math.pi do angle = angle + 2 * math.pi end
    return angle
end

local function angleDelta(from, to)
    local delta = normalizeAngle(to) - normalizeAngle(from)
    while delta > math.pi do delta = delta - 2 * math.pi end
    while delta <= -math.pi do delta = delta + 2 * math.pi end
    return delta
end

-- r.x/r.z/r.f remain the latest authoritative server target. These are only
-- presentation coordinates for a remote passenger, interpolated over one send
-- interval between server snapshots.
local function presentationAt(r, now)
    if r.snap or r.fromX == nil then return r.x, r.z, r.f end
    local t = math.max(0, math.min(1, (now - r.fromAt) / INTERPOLATE_MS))
    if t >= 1 then return r.x, r.z, r.f end
    return r.fromX + (r.x - r.fromX) * t,
        r.fromZ + (r.z - r.fromZ) * t,
        r.fromF + angleDelta(r.fromF, r.f) * t
end

-- setPassenger changes the local offset, not the character's world position. Match the
-- game's vehicle update here too, so a remote network update cannot leave the model at
-- the door while the vehicle moves (including an occupant who stands completely still).
local function place(vehicle, seat, player, x, y, z)
    vec = vec or Vector3f.new()
    vec:set(x, y, z)
    vehicle:setPassenger(seat, player, vec)
    worldVec = worldVec or Vector3f.new()
    local world = vehicle:getPassengerWorldPos(seat, worldVec)
    if world then
        player:setX(world:x())
        player:setY(world:y())
        player:setZ(world:z())
    end
end

------------------------------------------------------------------------------------
-- Client: sending your own position
------------------------------------------------------------------------------------

local last = { t = 0, beat = KEEPALIVE, x = 0, z = 0, f = 0, w = false, running = false }

-- Called by the standing session every step (MELens_Cabin.lua).
function S.send(s, dt)
    if not isClient() then return end
    if last.vehicle ~= s.vehicle or last.seat ~= s.seat or last.session ~= s then
        last.vehicle, last.seat, last.session = s.vehicle, s.seat, s
        last.t, last.beat = SEND_EVERY, KEEPALIVE
    end
    last.t = last.t + dt
    last.beat = last.beat + dt
    if last.t < SEND_EVERY then return end
    last.t = 0
    local changed = math.abs(s.x - last.x) > 0.005 or math.abs(s.z - last.z) > 0.005
        or math.abs(s.facing - last.f) > 0.03 or s.moving ~= last.w or (s.running == true) ~= last.running
    if not changed and last.beat < KEEPALIVE then return end
    last.x, last.z, last.f, last.w, last.running, last.beat = s.x, s.z, s.facing, s.moving, s.running == true, 0
    sendClientCommand(s.player, MODULE, POS, {
        v = s.vehicle:getId(), s = s.seat, x = s.x, z = s.z, f = s.facing,
        w = s.moving and 1 or 0, r = s.running and 1 or 0,
    })
end

------------------------------------------------------------------------------------
-- Server: keep it and pass it on
------------------------------------------------------------------------------------

S.SEAT_REACH = 12      -- tiles between the player and the vehicle for the server to seat them (below)

local function standingSeat(vehicle, profile, seat)
    for _, id in ipairs(M.standingIds(profile)) do
        if vehicle:getScript():getPassengerIndex(id) == seat then return true end
    end
    return false
end

-- The game takes a seat on the server only when it finds the seat's part, and for a place to stand only ME: LENS'
-- Java part tells it which that is (MELensRV.bindSeatContainer, on clients; a server, a hosted world's included,
-- runs without it). So the server turns the walk-in down, keeps the player outside and tells the others they went
-- in. The first position from inside seats them here the way the game puts a saved passenger back (no part asked).
-- True when the player is in that place now.
local function seated(vehicle, profile, seat, player, offset)
    local here = vehicle:getCharacter(seat)
    if here == player then return player:getVehicle() == vehicle end
    if here ~= nil or player:getVehicle() ~= nil or not standingSeat(vehicle, profile, seat)
            or player:DistToSquared(vehicle:getX(), vehicle:getY()) > S.SEAT_REACH * S.SEAT_REACH then
        return false
    end
    vehicle:enter(seat, player, offset)
    return vehicle:getCharacter(seat) == player
end

local function onClientCommand(module, command, player, args)
    if module ~= MODULE or command ~= POS or type(args) ~= "table" or not player then return end
    local vehicleId = finite(args.v)
    if not vehicleId then return end
    local vehicle = getVehicleById(vehicleId)
    local seat = finite(args.s)
    if not vehicle or not seat or seat ~= math.floor(seat) then return end
    local profile = M.profileFor(vehicle)
    if not profile or not standingSeat(vehicle, profile, seat) then return end
    local x, z = finite(args.x), finite(args.z)
    if not x or not z then return end
    local grid = profile.walkGrid and M.WalkGrids and M.WalkGrids[profile.walkGrid]
    if grid and (x < grid.x0 or x > grid.x0 + grid.cols * grid.cell
            or z < grid.z0 or z > grid.z0 + #grid.rows * grid.cell) then return end
    vec = vec or Vector3f.new()
    vec:set(x, profile.floorY, z)
    if not seated(vehicle, profile, seat, player, vec) then return end
    place(vehicle, seat, player, x, profile.floorY, z)
    if M.Utilities and M.Utilities.primeLamps then M.Utilities.primeLamps(vehicle) end
    sendServerCommand(MODULE, POS, {
        v = vehicle:getId(), s = seat, x = x, z = z, f = finite(args.f) or 0,
        w = args.w == 1 and 1 or 0, r = args.w == 1 and args.r == 1 and 1 or 0,
        p = player:getOnlineID(),
    })
end

------------------------------------------------------------------------------------
-- Client: the others
------------------------------------------------------------------------------------

S.remote = S.remote or {}   -- online ID -> authoritative target plus remote presentation state

local function onServerCommand(module, command, args)
    if module ~= MODULE or command ~= POS or type(args) ~= "table" then return end
    local me = getSpecificPlayer(0)
    local id, vid, seat = finite(args.p), finite(args.v), finite(args.s)
    if not id or (me and me:getOnlineID() == id) then return end
    local x, z = finite(args.x), finite(args.z)
    if not vid or not seat or seat ~= math.floor(seat) or not x or not z then return end
    local r = S.remote[id] or {}
    local now = getTimestampMs()
    local routeChanged = r.v ~= vid or r.s ~= seat
    local currentX, currentZ, currentF
    if r.x ~= nil and not routeChanged then
        currentX, currentZ, currentF = presentationAt(r, now)
    end
    local f = normalizeAngle(finite(args.f) or 0)
    local correction = currentX == nil or math.sqrt((x - currentX)^2 + (z - currentZ)^2) > SNAP_DISTANCE
    if routeChanged then r.bound = false end
    r.v, r.s = vid, seat
    r.x, r.z, r.f = x, z, f
    r.w = args.w == 1
    r.running = r.w and args.r == 1
    if routeChanged or not r.bound or correction then
        r.snap = true
        r.fromX, r.fromZ, r.fromF, r.fromAt = x, z, f, now
    else
        r.snap = false
        r.fromX, r.fromZ, r.fromF, r.fromAt = currentX, currentZ, currentF, now
    end
    r.received = now
    S.remote[id] = r
end

local function release(r)
    local chr = r.chr
    if not chr then return end
    if MELensRV then
        MELensRV.setStanding(chr, false)
        MELensRV.clearFacingOf(chr)
    end
    -- These variables belong to RVI and must not leak into an ordinary vehicle
    -- seat. Keep unrelated flags such as damnlib's damnVehicle untouched.
    chr:clearVariable(CABIN_VAR)
    chr:clearVariable(SEAT_VAR)
end

-- Every tick (the game's own vehicle updates set passengers back to their seat's position).
local function applyRemote()
    for id, r in pairs(S.remote) do
        local vehicle = r.v and getVehicleById(r.v)
        local profile = vehicle and M.profileFor(vehicle)
        local validSeat = profile and standingSeat(vehicle, profile, r.s)
        local chr = validSeat and vehicle:getCharacter(r.s)
        -- Our server has already authenticated this passenger. Repair missing client
        -- membership with the game's receive-side entry (it sends no new enter packet).
        -- Never overwrite another passenger or move someone out of a different vehicle.
        if validSeat and not r.bound and (not chr or (chr:getOnlineID() == id and not chr:getVehicle())) then
            local remote = getPlayerByOnlineID(id)
            if remote and not remote:isLocalPlayer() and (not remote:getVehicle()
                    or remote:getVehicle() == vehicle) and (vehicle:getSeat(remote) < 0
                    or vehicle:getSeat(remote) == r.s) then
                vehicle:enterRSync(r.s, remote, vehicle)
                chr = vehicle:getCharacter(r.s)
            end
        end
        if chr and validSeat and chr:getOnlineID() == id and chr:getVehicle() == vehicle then
            if r.chr and r.chr ~= chr then release(r) end
            r.chr, r.bound = chr, true
            local now = getTimestampMs()
            local x, z, f = presentationAt(r, now)
            r.renderX, r.renderZ, r.renderF = x, z, f
            place(vehicle, r.s, chr, x, profile.floorY, z)
            if not chr:getVariableBoolean(SEAT_VAR) then chr:setVariable(SEAT_VAR, "true") end
            local pose = r.running and "Run" or r.w and "Walk" or "Idle"
            if chr:getVariableString(CABIN_VAR) ~= pose then chr:setVariable(CABIN_VAR, pose) end
            if MELensRV then
                MELensRV.setStanding(chr, true)
                MELensRV.setFacing(chr, f)
            end
        elseif r.bound or (vehicle and not validSeat) or (chr and chr:getOnlineID() ~= id)
                or getTimestampMs() - r.received > PENDING_MS then
            release(r)
            S.remote[id] = nil
        end
    end
end

-- Keep the existing sync tick as the single dispatch point. Clients render remote
-- passengers; server/single player accounts for occupied-vehicle lamps.
if not S.hooked then
    S.hooked = true
    if isServer() then Events.OnClientCommand.Add(onClientCommand) end
    if isClient() then Events.OnServerCommand.Add(onServerCommand) end
    Events.OnTick.Add(function()
        if isClient() then
            applyRemote()
        elseif M.Utilities and M.Utilities.lampTick then
            M.Utilities.lampTick()
        end
    end)
end

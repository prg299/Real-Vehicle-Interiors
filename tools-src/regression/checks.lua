local M, P = MELens, MELens.Parts
local profile = M.Profiles["Base.87fordF700box"]
local function newScript()
    local s = { ids = {}, parts = {} }
    function s:getName() return "87fordF700box" end
    function s:getFullName() return "Base.87fordF700box" end
    function s:Load(_, text)
        local id = string.match(text, "{ part ([%w_]+)")
        if not self.parts[id] then self.ids[#self.ids + 1] = id end
        self.parts[id] = text
    end
    function s:getPassengerIndex(id)
        for i, name in ipairs(M.standingIds(profile)) do if name == id then return i + 1 end end
        return -1
    end
    function s:getModel() return { getOffset = function() return Vector3f.new() end } end
    return s
end

-- The real script generator must emit an identical network part order without Java.
local serverScript, clientScript = newScript(), newScript()
MELensRV = nil
P.extendScript(serverScript, profile)
MELensRV = {}
P.extendScript(clientScript, profile)
check(#serverScript.ids == #clientScript.ids, "part counts differ with/without Java")
for i, id in ipairs(serverScript.ids) do check(id == clientScript.ids[i], "network part index differs: " .. id) end
P.extendScript(serverScript, profile)
check(#serverScript.ids == #clientScript.ids, "repeated script extension appends parts")
check(serverScript.ids[1] == "MELensShell", "server shell is absent before storage")
for i, spot in ipairs(profile.spots) do
    local declaration = serverScript.parts[P.SPOT .. i]
    local advertisesBox = string.find(declaration, "itemType = Base.MELensRV_Box", 1, true) ~= nil
    check(advertisesBox == (not spot.empty), "wrong repair itemType for F700 spot " .. i)
    if spot.empty and spot.cargo then
        check(string.find(declaration, "model box {", 1, true) ~= nil,
            "empty F700 spot lost its buildable box model " .. i)
    end
    if not spot.cargo then
        -- furniture places along the walls (2.0.8): bare, after every box place, so a saved truck keeps its boxes
        check(spot.empty == true and spot.default == nil, "F700 furniture spot " .. i .. " does not start bare")
        check(string.find(declaration, "itemType = Base.MELensRV_Seat", 1, true) ~= nil,
            "F700 furniture spot " .. i .. " has no serializable empty-slot placeholder")
        check(string.find(declaration, "model cabinet {", 1, true) ~= nil and string.find(declaration, "model box {", 1, true) == nil,
            "F700 furniture spot " .. i .. " declares the wrong models")
        check(i > 63, "F700 furniture spot " .. i .. " moved a box place's number")
    end
end
local furnitureSpots = 0
for i, spot in ipairs(profile.spots) do
    if i <= 63 then check(spot.cargo == true, "F700 box place " .. i .. " is no longer a box place") end
    if not spot.cargo then furnitureSpots = furnitureSpots + 1 end
end
check(furnitureSpots == 20, "F700 furniture spots: " .. furnitureSpots)

local function truck(id)
    local v = { id = id, xx = 100, yy = 100, parts = {}, passengers = {}, offsets = {}, script = newScript(), resyncs = 0 }
    function v:getId() return self.id end
    function v:getScript() return self.script end
    function v:getX() return self.xx end
    function v:getY() return self.yy end
    function v:getPartById(name) return self.parts[name] end
    function v:getCharacter(seat) return self.passengers[seat] end
    function v:getSeat(chr) for seat, p in pairs(self.passengers) do if p == chr then return seat end end; return -1 end
    function v:setPassenger(seat, chr, vec)
        self.passengers[seat] = chr
        self.offsets[seat] = { vec:x(), vec:y(), vec:z() }
        return true
    end
    function v:enter(seat, chr, vec) self:setPassenger(seat, chr, vec); chr.vehicle = self; return true end
    function v:enterRSync(seat, chr, vehicle)
        self.resyncs = self.resyncs + 1
        return self:enter(seat, chr, Vector3f.new())
    end
    function v:getPassengerWorldPos(seat, vec)
        local o = self.offsets[seat]
        return vec:set(self.xx + o[1], self.yy + o[3], 0)
    end
    function v:getPassengerLocalPos(seat, vec) local o = self.offsets[seat]; return o and vec:set(o[1], o[2], o[3]) end
    function v:transmitPartItem(_) end
    function v:getWorldPos(x, y, z, vec) return vec:set(x, z, y) end
    function v:getLocalPos(x, y, z, vec) return vec:set(x, z, y) end
    for i, spot in ipairs(profile.spots) do
        local part = { id = P.SPOT .. i, item = spot.default == "box" and not spot.empty and {} or nil, container = { empty = true } }
        function part:getId() return self.id end
        function part:getInventoryItem() return self.item end
        function part:setInventoryItem(item) self.item = item end
        function part:getItemContainer() return self.container end
        function part.container:isEmpty() return self.empty end
        v.parts[part.id] = part
    end
    vehicles[id] = v
    return v
end
-- Mark test items with the same save-facing full type production pieceAt reads.
local originalTruck = truck
truck = function(id)
    local v = originalTruck(id)
    for _, part in pairs(v.parts) do
        if part.item then part.item.getFullType = function() return "Base.MELensRV_Box" end end
    end
    return v
end
local v, p = truck(10), character(2)
p.vehicle = v
v:enter(2, p, Vector3f.new())
P.applyPiece = function() end -- rendering/container sizing is outside this regression

-- Omitting the repair itemType must not make a deliberately bare upper level
-- unavailable to ordinary in-vehicle box placement.
local emptyUpper
for i, spot in ipairs(profile.spots) do
    if spot.empty and spot.level == 2 then emptyUpper = P.spotPart(v, i); break end
end
check(emptyUpper ~= nil and P.placeTest(v, emptyUpper, p),
    "initially empty supported upper box spot cannot accept a player-placed box")

-- All 46 default boxes, including levels two and three, can be removed top down.
local removed, upper = 0, 0
for level = 3, 1, -1 do
    for i, spot in ipairs(profile.spots) do
        local part = P.spotPart(v, i)
        if spot.level == level and part.item then
            check(P.pickUpTest(v, part, p), "empty top box refused at spot " .. i)
            local action = MELensPickUpFurniture:new(p, v, part)
            check(action:complete(), "box pickup failed at spot " .. i)
            check(not part.item, "picked box remains installed")
            check(not action:complete(), "duplicate pickup succeeds")
            removed = removed + 1
            if level > 1 then upper = upper + 1 end
        end
    end
end
check(removed == 46 and upper > 0, "default/upper boxes not covered: " .. removed)
check(#p.inventory == removed, "box duplication or loss")

v = truck(11); p.vehicle = v; v:enter(2, p, Vector3f.new())
local lower = P.spotPart(v, 1)
check(not P.pickUpTest(v, lower, p), "lower box removed beneath a stack")
local top
for i, spot in ipairs(profile.spots) do if P.pickUpTest(v, P.spotPart(v, i), p) then top = P.spotPart(v, i); break end end
local action = MELensPickUpFurniture:new(p, v, top)
local above = profile.spots[P.spotIndex(top)]._over
if above then
    local upperPart = P.spotPart(v, above)
    upperPart.item = { getFullType = function() return "Base.MELensRV_Box" end }
    check(not action:complete() and top.item, "newly supported upper box lost to stale pickup")
    upperPart.item = nil
end
top.container.empty = false
check(not action:complete() and top.item, "newly filled box removed")
top.container.empty = true
p.vehicle = nil
check(not action:complete() and top.item, "pickup completes after leaving")
check(not P.containerTest(v, top, p), "outside player can loot interior storage")

-- Real picker resolves a visible point in every default upper box, across the full stack height.
ISCoordConversion = { ToWorld = function(sx, sy, level) return sx, sy + level * 2.44949 end }
for i, spot in ipairs(profile.spots) do
    if (spot.level or 1) > 1 and P.spotPart(v, i).item and not P.covered(v, profile, i) then
        local length, depth, height = P.footprint(spot, "box")
        local hit
        for _, a in ipairs({ 0, -0.2, 0.2 }) do
            for _, d in ipairs({ 0.05, depth / 2, depth - 0.05 }) do
                local x, z = P.spotPoint(spot, a, d)
                local y = profile.floorY + spot.rise + height - 0.01
                local picked = M.Interact.pick(v, profile, x, z - y)
                if picked and picked.index == i then hit = picked end
            end
        end
        check(hit ~= nil, "upper box cannot be picked at spot " .. i)
    end
end

-- A no-Java server accepts the standing passenger and makes storage reachable there.
MELensRV = nil
p = character(3); v = truck(12)
emit("OnClientCommand", "MELens", "pos", p, { v = 12, s = 2, x = 0.6, z = 0.6, f = 0, w = 0, r = 1 })
check(p:getVehicle() == v and v:getCharacter(2) == p, "no-Java server did not seat passenger")
check(#broadcasts == 1 and broadcasts[1].r == 0, "server did not clear run when walking flag is off")
emit("OnClientCommand", "MELens", "pos", p, { v = 12, s = 2, x = 0.7, z = 0.6, f = 0, w = 1, r = 1 })
check(#broadcasts == 2 and broadcasts[2].w == 1 and broadcasts[2].r == 1,
    "server did not preserve a valid run state")
check(P.containerTest(v, P.spotPart(v, 1), p), "server rejects reachable box storage")
local before = #broadcasts
for _, bad in ipairs({ { s = -1, x = 0, z = 0 }, { s = 2.5, x = 0, z = 0 }, { s = 0, x = 0, z = 0 },
        { s = 2, x = math.huge, z = 0 }, { s = 2, x = 0/0, z = 0 }, { s = 2, x = 200, z = 0 } }) do
    bad.v = 12
    emit("OnClientCommand", "MELens", "pos", p, bad)
end
check(#broadcasts == before, "invalid position accepted")
local outsider = character(4); outsider.xx = 200
emit("OnClientCommand", "MELens", "pos", outsider, { v = 12, s = 3, x = 0, z = 0 })
check(not outsider.vehicle, "distant player seated")
emit("OnClientCommand", "MELens", "pos", outsider, { v = 12, s = 2, x = 0, z = 0 })
check(v:getCharacter(2) == p, "occupied seat overwritten")

-- A snapshot can precede native seat replication. Receive-side repair and world placement
-- follow a moving truck without another position packet (unchanged-input control).
local facing = {}
local savedLensJava = MELensRV
MELensRV = {
    setStanding = function() end,
    clearFacingOf = function(chr) facing[chr:getOnlineID()] = nil end,
    setFacing = function(chr, angle) facing[chr:getOnlineID()] = angle end,
}
local remote = character(5)
emit("OnServerCommand", "MELens", "pos", { p = 5, v = 12, s = 3, x = 0.2, z = -2, f = 1, w = 0, r = 1 })
emit("OnTick")
check(remote.vehicle == v and v:getCharacter(3) == remote and v.resyncs == 1, "remote membership not repaired")
check(v.offsets[3][1] == 0.2 and v.offsets[3][3] == -2, "first remote snapshot did not snap to its target")
check(remote.vars.MELensCabin == "Idle", "run flag was not normalized when walking was off")
local targetState = M.Sync.remote[5]
check(targetState.x == 0.2 and targetState.z == -2, "remote authoritative target was not retained")

-- Small remote deltas interpolate over one 100 ms send interval, then settle exactly.
emit("OnServerCommand", "MELens", "pos", { p = 5, v = 12, s = 3, x = 0.6, z = -1.6,
    f = 1.2, w = 1, r = 1 })
now = now + 50; emit("OnTick")
check(math.abs(v.offsets[3][1] - 0.4) < 0.0001 and math.abs(v.offsets[3][3] + 1.8) < 0.0001,
    "remote midpoint was not interpolated")
check(remote.vars.MELensCabin == "Run", "remote run state was not applied")
local cabinWrites = remote.variableWrites.MELensCabin
local seatWrites = remote.variableWrites.MELensCabinSeat
now = now + 50; emit("OnTick")
check(v.offsets[3][1] == 0.6 and v.offsets[3][3] == -1.6, "remote interpolation did not settle at target")
local settled = { v.offsets[3][1], v.offsets[3][3] }
emit("OnTick")
check(v.offsets[3][1] == settled[1] and v.offsets[3][3] == settled[2],
    "unchanged remote packet control drifted after settling")
check(remote.variableWrites.MELensCabin == cabinWrites and remote.variableWrites.MELensCabinSeat == seatWrites,
    "unchanged remote animation variables were rewritten")

-- Facing crosses zero by the short arc rather than turning almost a full revolution.
local angleVehicle, angleRemote = truck(101), character(10)
emit("OnServerCommand", "MELens", "pos", { p = 10, v = 101, s = 2, x = 0, z = 0,
    f = math.rad(359), w = 0, r = 0 })
emit("OnTick")
emit("OnServerCommand", "MELens", "pos", { p = 10, v = 101, s = 2, x = 0, z = 0,
    f = math.rad(1), w = 0, r = 0 })
now = now + 50; emit("OnTick")
check(math.min(math.abs(facing[10]), math.abs(facing[10] - 2 * math.pi)) < 0.0001,
    "facing interpolation took the long arc across 360 degrees")
now = now + 50; emit("OnTick")
check(math.abs(facing[10] - math.rad(1)) < 0.0001, "facing interpolation did not settle exactly")
check(angleVehicle.resyncs == 1, "angle fixture remote seated repeatedly")

-- A large correction or route/seat change must snap instead of gliding through space.
emit("OnServerCommand", "MELens", "pos", { p = 5, v = 12, s = 3, x = 3, z = -1.6,
    f = 1.2, w = 1, r = 1 })
emit("OnTick")
check(v.offsets[3][1] == 3, "large remote correction was smoothed")
v.passengers[3] = nil; remote.vehicle = nil
emit("OnServerCommand", "MELens", "pos", { p = 5, v = 12, s = 4, x = -0.4, z = -2,
    f = -1, w = 1, r = 0 })
emit("OnTick")
check(v:getCharacter(4) == remote and v.offsets[4][1] == -0.4,
    "seat change did not rebind and snap to the new target")
check(remote.vars.MELensCabin == "Walk", "run-off walking state was not applied after seat change")

local x, y = remote.xx, remote.yy
emit("OnTick")
check(remote.xx == x and remote.yy == y, "unchanged vehicle moved remote")
v.xx, v.yy = v.xx + 40, v.yy - 30
emit("OnTick")
check(remote.xx == x + 40 and remote.yy == y - 30, "stationary passenger left behind by moving vehicle")
check(v.resyncs == 2, "seat change did not perform exactly one additional bind")
remote.vehicle = nil; v.passengers[4] = nil
emit("OnTick")
check(not M.Sync.remote[5] and not remote.vehicle, "exited passenger pulled back in")
check(remote.vars.MELensCabin == nil and remote.vars.MELensCabinSeat == nil,
    "released passenger animation variables were not cleared")

-- Leaving the standing passenger for an ordinary driver seat must release RVI's
-- animation variables even though the character remains in the same vehicle.
local driverVehicle, driver = truck(102), character(11)
emit("OnServerCommand", "MELens", "pos", { p = 11, v = 102, s = 2, x = 0, z = 0,
    f = 0, w = 1, r = 1 })
emit("OnTick")
check(driver.vehicle == driverVehicle and driver.vars.MELensCabin == "Run"
    and driver.vars.MELensCabinSeat == "true", "driver-seat cleanup fixture did not bind")
driver:setVariable("damnVehicle", "True")
driverVehicle.passengers[2] = nil
driverVehicle.passengers[0] = driver
driver.vehicle = driverVehicle
emit("OnTick")
check(not M.Sync.remote[11] and driver:getVehicle() == driverVehicle
    and driverVehicle:getCharacter(0) == driver, "standing release displaced driver-seat membership")
check(driver.vars.MELensCabin == nil and driver.vars.MELensCabinSeat == nil,
    "RVI pose variables survived a switch to an ordinary vehicle seat")
check(driver.vars.damnVehicle == "True", "standing release cleared the unrelated damnlib vehicle flag")
driverVehicle.passengers[0] = nil; driver.vehicle = nil
emit("OnTick")
check(driver.vars.MELensCabin == nil and driver.vars.MELensCabinSeat == nil,
    "RVI pose variables returned after later vehicle exit")

emit("OnServerCommand", "MELens", "pos", { p = 6, v = 99, s = 2, x = 0, z = 0 })
emit("OnTick")
check(M.Sync.remote[6] ~= nil, "early snapshot dropped before vehicle replication")
local late = character(6); local lateVehicle = truck(99)
emit("OnTick")
check(late.vehicle == lateVehicle, "pending snapshot not retried")
emit("OnServerCommand", "MELens", "pos", { p = 7, v = 98, s = 2, x = 0, z = 0 })
now = now + 5001; emit("OnTick")
check(not M.Sync.remote[7], "unresolved snapshot never expires")

local ghost = character(8)
lateVehicle.passengers[3] = ghost -- packet populated the seat but not the character's membership
emit("OnServerCommand", "MELens", "pos", { p = 8, v = 99, s = 3, x = 0, z = 0 })
emit("OnTick")
check(ghost.vehicle == lateVehicle, "partial native passenger membership not repaired")
local occupied = character(9)
emit("OnServerCommand", "MELens", "pos", { p = 9, v = 99, s = 3, x = 0, z = 0 })
emit("OnTick")
check(not occupied.vehicle and lateVehicle:getCharacter(3) == ghost, "remote snapshot overwrote another passenger")
MELensRV = savedLensJava

local session = { player = localPlayer, vehicle = v, seat = 4, x = 0, z = 0, facing = 0, moving = false }
M.Sync.send(session, 0)
check(#sent == 1, "first stationary position not sent immediately")
M.Sync.send(session, 0.1)
check(#sent == 1, "unchanged position sends every frame")
M.Sync.send(session, 2)
check(#sent == 2, "stationary keepalive missing")
session.moving, session.running = true, true
M.Sync.send(session, 0.1)
check(#sent == 3 and sent[3].args.w == 1 and sent[3].args.r == 1, "running state was not broadcast")
M.Sync.send(session, 0.1)
check(#sent == 3, "unchanged running state sent every frame")
session.running = false
M.Sync.send(session, 0.1)
check(#sent == 4 and sent[4].args.w == 1 and sent[4].args.r == 0,
    "run-to-walk state change was not broadcast")

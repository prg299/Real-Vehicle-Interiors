-- Loaded before Cabin to capture its real callbacks, then after it to exercise
-- production registration, arming and lifecycle transitions with an RV double.
if not ProfileKeepPlaneRegression then
    local fixture = { events = {}, oldEvents = {}, tickAdd = Events.OnTick.Add }
    ProfileKeepPlaneRegression = fixture
    for _, name in ipairs({ "OnGameStart", "OnMainMenuEnter", "OnExitVehicle" }) do
        fixture.oldEvents[name] = Events[name]
        local event = { callbacks = {} }
        event.Add = function(fn) event.callbacks[#event.callbacks + 1] = fn end
        Events[name], fixture.events[name] = event, event
    end
    Events.OnTick.Add = function(fn)
        fixture.tick = fn
        fixture.tickAdd(fn)
    end
    return
end

local fixture, M = ProfileKeepPlaneRegression, MELens
local old = { rv = MELensRV, profiles = M.Profiles, manager = getScriptManager,
    player = getSpecificPlayer, interact = M.Interact, extend = M.Parts.extendScript,
    doors = M.Parts.syncShellDoors }
local planes, writes = {}, {}
local function noop() end
MELensRV = {
    setKeepPlane = function(model, a, b, c, d)
        planes[model] = { a, b, c, d }
        writes[#writes + 1] = model
    end,
    setCutaway = noop, clearCutaway = noop, clearNearCut = noop,
    clearFacing = noop, clearMarker = noop, clearStanding = noop,
}
local function plane(model, a, b, c, d, message)
    local p = planes[model]
    check(p and p[1] == a and p[2] == b and p[3] == c and p[4] == d, message)
end
local function event(name, player)
    for _, fn in ipairs(fixture.events[name].callbacks) do fn(player) end
end
local script = { getPassengerCount = function() return 16 end,
    getPassengerIndex = function() return -1 end, getName = function() return "KeepFixture" end }
local baseline = { name = "keep plane fixture", seatId = "MELensCabin", standing = {}, shell = {},
    mesh = { scale = .1, lift = 2 }, hideKI5 = {
        FixtureSpare = { plane = { 0, 1, 0, 99 } },
        ["mesh:fixture_height"] = .5, FixtureUnrelated = true,
    } }
M.Profiles = { ["Base.KeepFixture"] = baseline }
getScriptManager = function() return { getVehicle = function() return script end } end
M.Parts.extendScript, M.Parts.syncShellDoors, M.Interact = nil, noop, nil
M.addStandingPositions()
plane("FixtureSpare", 0, 1, 0, 99, "explicit global baseline not registered")
plane("mesh:fixture_height", 0, 0, 1, 3, "height baseline conversion changed")
plane("FixtureUnrelated", 0, 0, 0, 1, "whole-model baseline changed")

local function profile(depth)
    return { seatId = "MELensCabin", kind = "camper", floorY = 0,
        cutPlanes = { { 0, 0, -1, -4 }, { 0, 0, -1, -7 } },
        bodyKeepPlanes = { FixtureSpare = { 0, 1, 0, depth },
            ["mesh:fixture_height"] = { 1, 0, 0, -5 }, FixtureNoDefault = { 0, -1, 0, 4 } } }
end
local p13, p16, ordinary = profile(7.2), profile(16.2), profile(0)
ordinary.bodyKeepPlanes = nil
local currentProfile = p13
local vehicle = {
    getScript = function() return { getFullName = function() return "Base.KeepActive" end,
        getPassengerIndex = function() return -1 end } end,
    getSeat = function() return -1 end,
    getModData = function() return { MELensLightsOff = true } end,
}
local player = { vehicle = vehicle, isDead = function() return false end }
function player:getVehicle() return self.vehicle end
getSpecificPlayer = function() return player end
M.Profiles["Base.KeepActive"] = currentProfile
fixture.tick()
plane("FixtureSpare", 0, 1, 0, 7.2, "Scamp13 override not applied by production tick")
local count = #writes
fixture.tick()
check(#writes == count, "unchanged armed vehicle rewrites all keep planes each tick")

-- Same vehicle/alias, new profile: do not let the vehicle cache retain13's plane.
M.Profiles["Base.KeepActive"] = p16
fixture.tick()
plane("FixtureSpare", 0, 1, 0, 16.2, "same-vehicle profile transition retained old plane")
plane("FixtureUnrelated", 0, 0, 0, 1, "profile transition touched unrelated global rule")
M.Profiles["Base.KeepActive"] = ordinary
fixture.tick()
plane("FixtureSpare", 0, 1, 0, 99, "ordinary profile did not restore explicit baseline")
plane("mesh:fixture_height", 0, 0, 1, 3, "ordinary profile did not restore height alias")
plane("FixtureNoDefault", 0, 0, 0, -1, "alias without baseline did not become no-op")

M.Profiles["Base.KeepActive"] = p13
fixture.tick()
event("OnExitVehicle", {})
plane("FixtureSpare", 0, 1, 0, 7.2, "another player's exit cleared local override")
event("OnExitVehicle", player)
plane("FixtureSpare", 0, 1, 0, 99, "local exit did not restore global plane")
fixture.tick() -- still in the fixture vehicle: re-arm after exit callback
plane("FixtureSpare", 0, 1, 0, 7.2, "re-arm did not reapply profile override")
player.vehicle = nil
fixture.tick()
plane("FixtureSpare", 0, 1, 0, 99, "nil-vehicle tick leaked profile plane")

player.vehicle = vehicle
fixture.tick()
event("OnMainMenuEnter")
plane("FixtureSpare", 0, 1, 0, 99, "main menu leaked profile plane")
fixture.tick()
event("OnGameStart")
plane("FixtureSpare", 0, 1, 0, 99, "game start leaked profile plane")

-- A later registration is the true default, even while its alias is overridden.
fixture.tick()
M.Profiles = { ["Base.KeepFixture"] = baseline }
baseline.hideKI5.FixtureSpare.plane = { 0, 1, 0, 101 }
M.addStandingPositions()
plane("FixtureSpare", 0, 1, 0, 7.2, "late global registration displaced active override")
M.applyBodyKeepPlanes(nil)
plane("FixtureSpare", 0, 1, 0, 101, "restore guessed earlier registration order")
plane("FixtureUnrelated", 0, 0, 0, 1, "restoration cleared unrelated model")

M.applyBodyKeepPlanes(p13)
local bridge = MELensRV
MELensRV = nil
local ok = pcall(function() M.applyBodyKeepPlanes(p16); M.applyBodyKeepPlanes(nil); event("OnGameStart") end)
check(ok, "missing Java bridge breaks profile keep-plane lifecycle")
MELensRV = bridge
M.applyBodyKeepPlanes(nil)
plane("FixtureSpare", 0, 1, 0, 101, "missing bridge discarded pending restoration")
event("OnMainMenuEnter")

MELensRV, M.Profiles, getScriptManager, getSpecificPlayer = old.rv, old.profiles, old.manager, old.player
M.Interact, M.Parts.extendScript, M.Parts.syncShellDoors = old.interact, old.extend, old.doors
Events.OnTick.Add = fixture.tickAdd
for name in pairs(fixture.events) do Events[name] = fixture.oldEvents[name] end
ProfileKeepPlaneRegression = nil

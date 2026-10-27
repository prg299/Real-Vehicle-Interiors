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
MELensRV = completeJava({
    setKeepPlane = function(model, a, b, c, d)
        planes[model] = { a, b, c, d }
        writes[#writes + 1] = model
    end,
    setCutaway = noop, clearCutaway = noop, clearNearCut = noop,
    clearFacing = noop, clearMarker = noop, clearStanding = noop,
})
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
local player = { vehicle = vehicle, isDead = function() return false end,
    getVariableString = function() return "" end }
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
event("OnExitVehicle", { getVariableString = function() return "" end })
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
-- Whole-pane High must not expose the fallback ceiling's detached rails.
-- Reuse the profile override lifecycle and restore it when leaving native mode.
local nativeSet = bridge.setNativeBodyWalls
bridge.setNativeBodyWalls = noop
p13.nativeBodyWalls = true
p13.nativeBodyKeepPlanes = { ["mesh:fixture_height"] = { 0, 0, 0, 1 } }
M.applyBodyKeepPlanes(p13)
plane("mesh:fixture_height", 0, 0, 0, 1, "native ceiling remnant remained visible")
M.applyBodyKeepPlanes(ordinary)
plane("mesh:fixture_height", 0, 0, 1, 3, "native ceiling hide leaked to another vehicle")
bridge.setNativeBodyWalls = nil
M.applyBodyKeepPlanes(p13)
plane("mesh:fixture_height", 1, 0, 0, -5, "older bridge lost its fallback ceiling plane")
bridge.setNativeBodyWalls = nativeSet
M.applyBodyKeepPlanes(nil)
event("OnMainMenuEnter")

-- Exercise the intermediate bridge: native wall/body APIs exist but the newer
-- cab-material API does not. Its structural exemptions must survive adoption.
local bodyModels, cabModels
bridge.setNativeBodyWalls = noop
bridge.setNativeBodyModels = function(value) bodyModels = value end
p13.nativeBodyModels = { "FixtureRearLeaf" }
p13.nativeCabModels = { "FixtureCab" }
p13.nativeCabFallbackBodyModels = { "FixtureEngine" }
M.Profiles["Base.KeepActive"] = p13
fixture.tick()
check(bodyModels == "FixtureRearLeaf,FixtureEngine", "intermediate native bridge clips its cab fittings")
bridge.setNativeCabModels = function(value) cabModels = value end
event("OnMainMenuEnter")
fixture.tick()
check(bodyModels == "FixtureRearLeaf" and cabModels == "FixtureCab",
    "new bridge repaints cab fittings through legacy body aliases")
M.Profiles["Base.KeepActive"] = ordinary
fixture.tick()
check(bodyModels == "" and cabModels == "", "cab/body aliases leak into another vehicle")
event("OnMainMenuEnter")

-- Source-qualified fitting cuts share the roof evaluator, including AS bridges
-- exposing only the older method names. Missing evaluators use the legacy shell.
local calls, surfaceClears = {}, 0
p13.mesh = { scale = .1, lift = 2 }
bridge.setNativeSurfaceCut = function(...) calls[#calls + 1] = { ... } end
bridge.clearNativeSurfaceCuts = function() calls = {}; surfaceClears = surfaceClears + 1 end
p13.nativeSurfaceCuts = { { models = { "FixtureBody", "mesh:fixture_body" },
    box = { x = { -1, 1 }, y = { -2, 2 }, z = { -3, 3 } }, uv = { .6, .8, .99, .99 } } }
M.Profiles["Base.KeepActive"] = p13
fixture.tick()
check(#calls == 1 and calls[1][1] == "FixtureBody,mesh:fixture_body" and calls[1][2] == -1,
    "fitting list not armed by production tick")
check(calls[1][3] == 10 and calls[1][4] == -30 and calls[1][5] == 22
    and calls[1][6] == -10 and calls[1][7] == 30 and calls[1][8] == -18,
    "fitting bounds not transformed from passenger to body coordinates")
M.Profiles["Base.KeepActive"] = ordinary
fixture.tick()
check(#calls == 0 and surfaceClears > 0, "fitting list survived profile transition")
bridge.setNativeRoofCut, bridge.clearNativeRoofCuts = bridge.setNativeSurfaceCut, bridge.clearNativeSurfaceCuts
bridge.setNativeSurfaceCut, bridge.clearNativeSurfaceCuts = nil, nil
M.Profiles["Base.KeepActive"] = p13
fixture.tick()
check(#calls == 1, "AS bridge cannot use shared bounded evaluator for fittings")
-- The native side-door protection is independent of the saved room boundary.
local cutFront, cutTop, fullCab
bridge.setCutFront = function(value) cutFront = value; cutTop = nil end
bridge.setCutFrontTop = function(value) cutTop = value end
bridge.setCutFrontCab = function(value) fullCab = value end
p13.cutFront, p13.cutFrontTop = .3, .63
p13.nativeCabCutFront, p13.nativeCabCutFrontTop = -.585, .612146418
p13.nativeRoofCuts = { { models = { "FixtureRoof" },
    box = { x = { -1, 1 }, y = { -2, 2 }, z = { -3, 3 } } } }
event("OnMainMenuEnter")
fixture.tick()
check(math.abs(cutFront + 5.85) < 1e-8 and math.abs(cutTop - (2 - .612146418 / .1)) < 1e-8,
    "native protection cuts through the complete side door")
check(math.abs(fullCab - 3) < 1e-8, "lower door bay cut away original full cab roof")
check(#calls == 2 and calls[1][7] == 30 and calls[2][7] == 30,
    "side-door protection moved measured roof or fitting bounds")
check(p13.cutFront == .3 and p13.nativeRoofCuts[1].box.z[2] == 3,
    "render-only side-door protection mutated room or source bounds")
bridge.setNativeBodyWalls = nil
event("OnMainMenuEnter")
fixture.tick()
check(math.abs(cutFront - 3) < 1e-8 and math.abs(cutTop + 4.3) < 1e-8,
    "legacy shell inherited the native side-door protection")
check(calls[1][7] == 30, "legacy shell inherited the native roof bound")
bridge.setNativeBodyWalls = noop
bridge.setCutFrontCab = nil
event("OnMainMenuEnter")
fixture.tick()
check(math.abs(cutFront - 3) < 1e-8 and math.abs(cutTop + 4.3) < 1e-8,
    "older native bridge cut the original cab roof without a separate bay boundary")
p13.cutFront, p13.cutFrontTop, p13.nativeCabCutFront, p13.nativeCabCutFrontTop = nil, nil, nil, nil
p13.nativeRoofCuts = nil
bridge.setCutFront, bridge.setCutFrontTop = nil, nil
bridge.setNativeRoofCut, bridge.clearNativeRoofCuts = nil, nil
check(not M.nativeWallsAvailable(p13, bridge), "missing fitting evaluator enables overlapping native interior")
M.applyBodyKeepPlanes(p13)
plane("mesh:fixture_height", 1, 0, 0, -5, "missing fitting evaluator applies native-only ceiling override")
event("OnMainMenuEnter")

-- Curved paths exercise production arming, retaining both source sides.
bridge.setNativeSurfaceCut, bridge.clearNativeSurfaceCuts = noop, noop
local curvedCalls, legacyCalls, curveArgs = 0, 0, nil
bridge.setFlatWheelArch = function() legacyCalls = legacyCalls + 1 end
bridge.setCurvedWheelArches = function(...) curvedCalls = curvedCalls + 1; curveArgs = { ... } end
p13.floorY = -.2
p13.nativeWheelArch = { sides = {
    { side = 1, contour = { { .2, -.3, -1 }, { .3, -.1, 0 }, { .25, -.3, 1 } } },
    { side = -1, contour = { { -.4, -.3, -1 }, { -.45, -.05, 0 }, { -.5, -.3, 1 } } },
} }
fixture.tick()
check(curvedCalls == 1 and legacyCalls == 0, "curved arming discarded measured side paths")
check(curveArgs[1] == "-10,5,-2;0,3,-3;10,5,-2.5"
    and curveArgs[2] == "-10,5,4;0,2.5,4.5;10,5,5" and curveArgs[3] == 4,
    "curved passenger paths not transformed to signed body axes")
bridge.setCurvedWheelArches = nil
event("OnMainMenuEnter")
fixture.tick()
check(curvedCalls == 1 and legacyCalls == 0, "older bridge guessed a planar arch for curved data")
event("OnMainMenuEnter")

local stockCalls, stockArgs = 0, nil
bridge.setCurvedWheelArches = function() curvedCalls = curvedCalls + 1; return true end
bridge.setNativeWheelWellTrim = function(...) stockCalls = stockCalls + 1; stockArgs = { ... }; return true end
p13.nativeWheelWellTrim = { sides = {
    { side = 1, inner = .1, segments = { { -1, 1, -.1, -.05, .24 } } },
    { side = -1, inner = .2, segments = { { -1, 1, -.1, -.05, .35 } } },
} }
fixture.tick()
check(stockCalls == 1 and stockArgs[1] == "-10,10,3,2.5,2.4" and stockArgs[2] == "-10,10,3,2.5,3.5"
    and stockArgs[3] == 1 and stockArgs[4] == 2,"native stock slabs lost source axes/clearances")
local beforeMissingStock = curvedCalls
bridge.setNativeWheelWellTrim = nil
event("OnMainMenuEnter")
fixture.tick()
check(stockCalls == 1 and curvedCalls == beforeMissingStock,"older bridge armed flat mode without native stock removal")
event("OnMainMenuEnter")

-- Stock colour is optional: arming keeps the measured material on older bridges.
local metalCalls, materialCalls, materialReady = 0, 0, false
bridge.setNativeWheelWellTrim = function() return true end
bridge.setBodyLining = function() materialReady = false end
bridge.setBodyLiningPlain = noop
bridge.setBodyLiningMaterial = function() materialCalls = materialCalls + 1; materialReady = true end
bridge.setBodyLiningBoundaryFinish = noop
bridge.setBodyLiningStockMetal = function()
    check(materialReady, "stock colour armed before measured material classification")
    metalCalls = metalCalls + 1
end
p13.nativeBodyLining, p13.nativePlainFinish = { .64, .66, .67 }, true
p13.nativeWallMaterial = { texture = "MELensShell_f700box_walls", height = 1.2, perimeter = 7 }
p13.nativeStockMetal = { texture = "vehicle_vanseatsshell", paintUV = { .56640625, .35546875 },
    panelUV = { .3427734375, .2861328125, .4970703125, .3896484375 }, panelWidth = 1.1, panelHeight = .7425 }
event("OnMainMenuEnter")
fixture.tick()
check(metalCalls == 1 and materialCalls == 1, "stock colour not armed through production profile tick")
bridge.setBodyLiningStockMetal = nil
event("OnMainMenuEnter")
check(pcall(fixture.tick) and materialCalls == 2 and materialReady,
    "older bridge lost its existing measured finish when stock colour API is absent")
bridge.setBodyLiningStockMetal = function() metalCalls = metalCalls + 1 end
p13.nativeStockMetal = nil
event("OnMainMenuEnter")
fixture.tick()
check(metalCalls == 1 and materialCalls == 3,
    "stock colour escaped its explicit profile opt-in")
event("OnMainMenuEnter")

MELensRV, M.Profiles, getScriptManager, getSpecificPlayer = old.rv, old.profiles, old.manager, old.player
M.Interact, M.Parts.extendScript, M.Parts.syncShellDoors = old.interact, old.extend, old.doors
Events.OnTick.Add = fixture.tickAdd
for name in pairs(fixture.events) do Events[name] = fixture.oldEvents[name] end
ProfileKeepPlaneRegression = nil

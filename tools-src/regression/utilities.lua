-- Production utility functions and timed-action completion with explicit engine doubles.
-- These checks do not simulate native input, real fluid components, rendering or multiplayer.
local M, U, P, H = MELens, MELens.Utilities, MELens.Parts, MELens.Home
local names = { "isClient", "isServer", "SandboxVars", "Fluid", "FluidContainer", "VehicleUtils", "addSound",
    "getCell", "getClimateManager", "instanceof", "instanceItem", "Perks", "addXp", "sendRemoveItemFromContainer",
    "sendAddItemToContainer", "sendItemStats", "syncItemFields", "syncVisuals", "sendHumanVisual", "CharacterStat",
    "ISWashClothing", "BloodBodyPartType", "BloodClothingType", "ComponentType", "getGameTime" }
local saved = {}
for _, name in ipairs(names) do saved[name] = _G[name] end
local client, server = false, true
local worldHour = 100
getGameTime = function() return { getWorldAgeHours = function() return worldHour end } end
isClient, isServer = function() return client end, function() return server end
SandboxVars = { MELens = { GeneratorFuelUse = 1, GeneratorWear = 1, PropaneAppliances = true,
    ShorePower = true, RainFillsTank = true } }
Fluid = { Petrol = "petrol", Water = "water", TaintedWater = "tainted" }
Perks, CharacterStat = { Electricity = "electricity" }, { THIRST = "thirst" }
local packets, sounds, xp, disposed = 0, 0, 0, 0
sendRemoveItemFromContainer = function() packets = packets + 1 end
sendAddItemToContainer = function() packets = packets + 1 end
sendItemStats, syncItemFields, syncVisuals, sendHumanVisual = function() end, function() end, function() end, function() end
addSound = function() sounds = sounds + 1 end
addXp = function(_, _, amount) xp = xp + amount end
instanceof = function(item, kind) return item and item.class == kind end
local function near(actual, expected, label)
    check(math.abs(actual - expected) < 0.000001, label .. ": " .. tostring(actual) .. " != " .. tostring(expected))
end
local function list(values)
    local l = values or {}
    function l:size() return #self end
    function l:get(i) return self[i + 1] end
    return l
end
local function fluid(kind, amount, capacity)
    local f = { kind = kind, amount = amount or 0, capacity = capacity or 10 }
    function f:isEmpty() return self.amount <= 0 end
    function f:isFull() return self.amount >= self.capacity end
    function f:isPureFluid(k) return self.kind == k end
    function f:getAmount() return self.amount end
    function f:getFreeCapacity() return self.capacity - self.amount end
    function f:setCapacity(c) self.capacity = c end
    function f:canAddFluid(k) return k == Fluid.Water or k == Fluid.TaintedWater end
    function f:addFluid(k, a) self.kind = k; self.amount = math.min(self.capacity, self.amount + a) end
    function f:removeFluid(a) self.amount = math.max(0, self.amount - a) end
    return f
end
FluidContainer = { CreateContainer = function() return fluid(nil, 0, 1) end,
    DisposeContainer = function() disposed = disposed + 1 end }
local function item(full, contents)
    local i = { full = full or "Base.Bottle", fluid = contents, uses = 1, blood = 1, favorite = true }
    function i:getFullType() return self.full end
    function i:getType() return string.match(self.full, "%.(.+)$") end
    function i:getFluidContainer() return self.fluid end
    function i:getCurrentUsesFloat() return self.uses end
    function i:setUsedDelta(n) self.uses = n end
    function i:syncItemFields() self.synced = (self.synced or 0) + 1 end
    function i:getContainer() return self.container end
    function i:getBloodLevel() return self.blood end
    function i:setBloodLevel(n) self.blood = n end
    function i:getItemAfterCleaning() return self.afterCleaning end
    function i:isFavorite() return self.favorite end
    function i:setFavorite(f) self.favorite = f end
    return i
end
instanceItem = function(full) return item(full) end
ISWashClothing = { GetRequiredWater = function() return 2 end,
    GetRequiredSoap = function(i) return i.soapRequired or 0 end }
local serial = 9000
local function fixture()
    serial = serial + 1
    local v = { id = serial, parts = {}, data = {}, charge = 0, transmits = 0 }
    function v:getId() return self.id end
    function v:getX() return 100 end
    function v:getY() return 100 end
    function v:getZ() return 0 end
    function v:getScript() return { getFullName = function() return "Base.Trailer54FlyingCloud22" end } end
    function v:getModData() return self.data end
    function v:getPartById(id) return self.parts[id] end
    function v:getSquare() return { getX = function() return 100 end, getY = function() return 100 end,
        getZ = function() return 0 end, isOutside = function() return not self.indoors end } end
    function v:setNeedPartsUpdate(value) self.awake = value end
    function v:transmitPartModData() self.transmits = self.transmits + 1 end
    function v:transmitPartCondition() self.transmits = self.transmits + 1 end
    function v:transmitModData() self.transmits = self.transmits + 1 end
    local function part(id, piece)
        local p = { id = id, data = {}, condition = 100, container = { temperature = 0 }, lastUpdated = worldHour }
        function p:getLastUpdated() return self.lastUpdated end
        function p:setLastUpdated(n) self.lastUpdated = n end
        function p:getModData() return self.data end
        function p:getCondition() return self.condition end
        function p:setCondition(n) self.condition = n end
        function p:getInventoryItem() return self.installed end
        function p:getItemContainer() return self.container end
        function p.container:setCustomTemperature(t) self.temperature = t end
        if piece then p.installed = item(P.itemType(piece)) end
        v.parts[id] = p
        return p
    end
    local f = { v = v, gen = part(P.GENERATOR), water = part(P.WATER), oven = part(P.OVEN),
        kitchen = part(P.SPOT .. 5, "kitchen"), fridge = part(P.SPOT .. 6, "fridge"),
        heater = part(P.SPOT .. 8, "heater"), compartment = part("PassengerCompartment") }
    f.gen.data, f.water.data = { fuel = 5, on = false }, { water = 10, tainted = false }
    local inventory = { items = {} }
    function inventory:AddItem(i) self.items[i] = true; i.container = self; return i end
    function inventory:Remove(i) self.items[i] = nil; i.container = nil end
    function inventory:contains(i) return self.items[i] == true end
    function inventory:containsRecursive(i) return self:contains(i) end
    function inventory:getSoapList() return list() end
    local p = { inventory = inventory, xx = 100, yy = 100, vehicle = v, thirst = 0.25 }
    function p:getInventory() return self.inventory end
    function p:getVehicle() return self.vehicle end
    function p:DistToSquared(x, y) return (self.xx - x)^2 + (self.yy - y)^2 end
    function p:isTimedActionInstant() return true end
    function p:getPerkLevel() return 4 end
    function p:removeFromHands() end
    function p:updateHandEquips() end
    function p:getStats() return { get = function() return self.thirst end } end
    function p:DrinkFluid(fc) self.drankKind = fc.kind; self.drank = fc.amount end
    p.visual = { blood = { [0] = 1, [1] = 0, [2] = 1 }, dirt = { [0] = 0, [1] = 1, [2] = 0 } }
    function p:getHumanVisual() return self.visual end
    function p.visual:getBlood(part) return self.blood[part] end
    function p.visual:getDirt(part) return self.dirt[part] end
    function p.visual:setBlood(part, n) self.blood[part] = n end
    function p.visual:setDirt(part, n) self.dirt[part] = n end
    f.p = p
    return f
end
-- Record the requested helper delta. Build42.21's real helper applies that delta
-- twice; this double does not claim to verify the resulting native battery field.
VehicleUtils = { chargeBattery = function(v, amount) v.charge = v.charge + amount end }
local active, shoreGenerator, rain = fixture(), nil, 0
getCell = function()
    return {
        getGridSquare = function(_, x, y, z)
            if x == 104 and y == 100 and z == 0 then return { getGenerator = function() return shoreGenerator end } end
        end,
        getVehicles = function() return { iterator = function()
            local used = false
            return { hasNext = function() return not used end, next = function() used = true; return active.v end }
        end } end,
    }
end
getClimateManager = function() return { getRainIntensity = function() return rain end } end

-- Water amount/taint conservation, including full and empty unchanged controls.
local f = fixture()
near(U.changeWater(f.v, 100, false), 50, "water refill clamps to tank capacity")
check(f.water.data.water == 60 and not f.water.data.tainted, "clean refill changes tank")
check(U.changeWater(f.v, 5, true) == 0 and not f.water.data.tainted, "rejected full refill taints clean water")
near(U.changeWater(f.v, -59), -59, "water withdrawal")
near(U.changeWater(f.v, 0.5, true), 0.5, "tainted partial refill")
check(f.water.data.tainted and f.water.data.water == 1.5, "mixed tank loses contamination")
U.changeWater(f.v, 1, false)
check(f.water.data.tainted, "clean top-up purifies dirty tank")
near(U.changeWater(f.v, -100), -2.5, "withdrawal clamps to available water")
check(f.water.data.water == 0 and not f.water.data.tainted, "empty tank retains old taint")
check(U.changeWater(f.v, -1) == 0, "empty tank produces water")
U.changeWater(f.v, 2, false)
check(not f.water.data.tainted, "clean refill into emptied tank remains tainted")

-- Refills use pure fluids, retain leftover liquid, and reject stale ownership/reach/full state.
f = fixture()
local can = item("Base.PetrolCan", fluid(Fluid.Petrol, 10, 10)); f.p.inventory:AddItem(can)
f.gen.data.fuel = 18
local refuel = MELensRefuelGenerator:new(f.p, f.v, can)
check(refuel:isValid() and refuel:complete(), "valid partial petrol refill refused")
near(f.gen.data.fuel, 20, "generator overfilled"); near(can.fluid.amount, 8, "petrol remainder not retained")
check(not refuel:complete() and can.fluid.amount == 8, "full generator consumes more petrol")
f.gen.data.fuel = 0; can.fluid.kind = "mixed"
check(not refuel:isValid() and not refuel:complete(), "mixed petrol accepted")
can.fluid.kind = Fluid.Petrol; f.p.inventory:Remove(can)
check(not refuel:complete() and f.gen.data.fuel == 0 and can.fluid.amount == 8, "stale petrol ownership mutates fuel")
f.p.inventory:AddItem(can); f.p.vehicle = nil; f.p.xx = 200
check(not refuel:complete() and f.gen.data.fuel == 0, "distant petrol action mutates fuel")
f.p.xx = 100; can.fluid.amount = 0
check(not refuel:complete(), "empty petrol can accepted")
can.fluid.amount = 1
check(refuel:complete() and can.fluid.amount == 0 and f.gen.data.fuel == 1, "small petrol supply not consumed exactly")

f = fixture()
local bottle = item("Base.Bottle", fluid(Fluid.TaintedWater, 5, 5)); f.p.inventory:AddItem(bottle)
f.water.data.water = 59
local pour = MELensFillWaterTank:new(f.p, f.v, bottle)
check(pour:isValid() and pour:complete(), "tainted partial tank refill refused")
near(bottle.fluid.amount, 4, "water bottle remainder"); check(f.water.data.water == 60 and f.water.data.tainted, "tainted refill tank state")
check(not pour:complete() and bottle.fluid.amount == 4, "full tank drains bottle")
f.water.data.water = 0; f.p.inventory:Remove(bottle)
check(not pour:complete() and bottle.fluid.amount == 4 and f.water.data.water == 0, "stale water ownership mutates state")
f.p.inventory:AddItem(bottle); bottle.fluid.kind = Fluid.Petrol
check(not pour:complete(), "petrol poured into water tank")

-- Tap refills and drinking retain taint, bound consumption and reject departure.
f = fixture(); f.water.data.water = 1; f.water.data.tainted = true
bottle = item("Base.Bottle", fluid(nil, 0, 2)); f.p.inventory:AddItem(bottle)
local fill = MELensFillFromTank:new(f.p, f.v, bottle)
check(fill:complete() and bottle.fluid.amount == 1 and bottle.fluid.kind == Fluid.TaintedWater, "tap loses quantity/taint")
check(f.water.data.water == 0 and not f.water.data.tainted, "tap withdrawal leaves tank tainted/negative")
check(not fill:complete() and bottle.fluid.amount == 1, "empty tank duplicates tap water")
f.water.data.water = 2; f.p.inventory:Remove(bottle)
check(not fill:complete() and f.water.data.water == 2, "tap fills item no longer carried")
f.p.inventory:AddItem(bottle); f.p.vehicle = nil
check(not fill:complete() and f.water.data.water == 2, "tap fills bottle after leaving")
f.p.vehicle = f.v; f.water.data.tainted = true
local drink = MELensDrinkFromTank:new(f.p, f.v)
check(drink:complete() and f.p.drankKind == Fluid.TaintedWater, "drink loses tank taint")
near(f.water.data.water, 1.5, "drinking consumes thirst-limited water"); near(f.p.drank, 0.5, "drink amount")
check(disposed == 1, "temporary drink fluid not disposed")
f.p.vehicle = nil
check(not drink:complete() and f.water.data.water == 1.5, "drink completes after leaving")
f.p.vehicle = f.v; f.p.inventory:AddItem(bottle); bottle.fluid.amount = bottle.fluid.capacity
check(not fill:complete() and f.water.data.water == 1.5, "full bottle consumes tap water")
bottle.fluid.amount = 0; bottle.fluid.canAddFluid = function() return false end
check(not fill:complete() and f.water.data.water == 1.5, "incompatible bottle consumes tap water")
BloodBodyPartType = { MAX = { index = function() return 3 end }, FromIndex = function(i) return i end }
f.water.data.water = 0.75
local wash = MELensWashFromTank:new(f.p, f.v)
check(wash:complete() and f.p.visual.blood[0] == 0 and f.p.visual.dirt[1] == 1, "partial body wash exceeds available water")
near(f.water.data.water, 0.25, "partial body wash water")
check(not wash:complete() and f.p.visual.dirt[1] == 1, "insufficient body-wash water cleans anyway")
f.water.data.water = 2; f.p.vehicle = nil
check(not wash:complete() and f.water.data.water == 2, "body wash completes after leaving")

-- Switch and repair completion revalidate requirements, not merely presentation state.
f = fixture(); f.gen.data.fuel = 0
local start = MELensSwitch:new(f.p, f.v, "generator", true)
check(not start:isValid() and not start:complete() and not f.gen.data.on, "empty generator starts")
f.gen.data.fuel = 2; f.gen.condition = 0
check(not start:complete() and not f.gen.data.on, "broken generator starts")
f.gen.condition = 100
check(start:complete() and f.gen.data.on and f.v.awake, "fueled generator does not start/wake")
f.p.vehicle = nil; f.p.xx = 200
check(not MELensSwitch:new(f.p, f.v, "lights", false):complete() and not f.v.data.MELensLightsOff, "distant lights switch completes")
f.p.vehicle = f.v; f.p.xx = 100; f.gen.data.on = false; f.gen.condition = 40
local scrap = item("Base.ElectronicsScrap"); f.p.inventory:AddItem(scrap)
local repair = MELensRepairGenerator:new(f.p, f.v, scrap)
check(repair:isValid() and repair:complete() and f.gen.condition == 46 and xp == 5, "generator repair not applied")
check(not repair:complete() and f.gen.condition == 46 and xp == 5, "repeated repair consumes absent scrap/gives XP")
local wrong = item("Base.Plank"); f.p.inventory:AddItem(wrong)
check(not MELensRepairGenerator:new(f.p, f.v, wrong):complete() and f.p.inventory:contains(wrong), "wrong repair material consumed")
scrap = item("Base.ElectronicsScrap"); f.p.inventory:AddItem(scrap); f.gen.data.on = true
check(not MELensRepairGenerator:new(f.p, f.v, scrap):complete() and f.p.inventory:contains(scrap), "running generator repaired")
f.gen.data.on = false; f.gen.condition = 100
check(not MELensRepairGenerator:new(f.p, f.v, scrap):complete() and f.p.inventory:contains(scrap), "already repaired generator consumes scrap")

-- Equal elapsed-time controls and finite fuel/wear bound actual generation time.
f = fixture(); f.gen.data.on = true; f.gen.data.fuel = 2
local fuelBefore, chargeBefore = f.gen.data.fuel, f.v.charge
U.runGenerator(f.v, f.gen, 0)
check(f.gen.data.fuel == fuelBefore and f.v.charge == chargeBefore, "zero-time generator changes state")
U.runGenerator(f.v, f.gen, 60)
near(f.gen.data.fuel, 1.8, "one-hour fridge-only fuel consumption"); near(f.v.charge, 0.06, "one-hour battery generation")
near(f.gen.data.wear, 0.25, "one-hour wear")
f = fixture(); f.gen.data.on = true; f.gen.data.fuel = 0.1; f.fridge.container.temperature = U.FRIDGE_COLD
U.runGenerator(f.v, f.gen, 60)
near(f.gen.data.fuel, 0, "fuel exhausted"); near(f.v.charge, 0.03, "exhausted generator charges full interval")
near(f.gen.data.wear, 0.125, "exhausted generator wears full interval")
check(not f.gen.data.on and f.fridge.container.temperature == 0, "fuel cutoff does not immediately stop fridge power")
near(f.gen.data.noise, 0, "generator noise interval was not emitted")
U.updateGenerator(f.v, f.gen, 1)
check(not f.v.awake, "fully stopped camper keeps unnecessary part updates awake")
f = fixture(); f.gen.data.on = true; f.gen.condition = 1; f.gen.data.wear = 0.9
U.runGenerator(f.v, f.gen, 60)
near(f.v.charge, 0.024, "broken generator charges beyond 24-minute lifetime")
near(f.gen.data.fuel, 4.92, "wear cutoff consumes full-interval petrol")
check(f.gen.condition == 0 and not f.gen.data.on, "wear cutoff does not stop generator")
SandboxVars.MELens.GeneratorFuelUse, SandboxVars.MELens.GeneratorWear = 0, 0
f = fixture(); f.gen.data.on = true; U.runGenerator(f.v, f.gen, 60)
near(f.gen.data.fuel, 5, "zero fuel-use option consumes petrol"); near(f.v.charge, 0.06, "zero-rate options stop generation")
SandboxVars.MELens.GeneratorFuelUse, SandboxVars.MELens.GeneratorWear = 1, 1

-- The same game hour at different appliance loads, with idle/off controls.
f = fixture(); near(U.generatorFuelRate(f.v), 0.2, "fridge load rate")
f.gen.data.on = true; f.v.awake = false
U.updateGenerator(f.v, f.gen, 1)
check(f.v.awake == true, "stock cold-engine update puts running generator back to sleep")
f.fridge.installed = nil; near(U.generatorFuelRate(f.v), 0.08, "idle generator rate")
f.fridge.installed = item(P.itemType("fridge"))
f.oven.data.on, f.heater.data.on = true, true
near(U.generatorFuelRate(f.v), 0.2, "propane appliances consume generator petrol")
SandboxVars.MELens.PropaneAppliances = false
near(U.generatorFuelRate(f.v), 0.8, "full electrical load rate")
SandboxVars.MELens.PropaneAppliances = true

-- Starting after days parked OFF must not bill those days as running time.
f = fixture(); f.gen.lastUpdated = worldHour - 72
local before = f.gen.data.fuel
U.setSwitch(f.v, "generator", true)
near(f.gen.lastUpdated, worldHour, "generator start retains parked clock")
near(f.gen.data.fuel, before, "starting charges for parked time")
worldHour = worldHour + 1 / 6
U.setSwitch(f.v, "generator", false)
near(f.gen.data.fuel, before - 0.2 / 6, "ten game-minute fuel use")
worldHour = worldHour + 48
U.setSwitch(f.v, "generator", true)
near(f.gen.data.fuel, before - 0.2 / 6, "restarting charges two days switched off")
worldHour = worldHour + 1 / 6
U.setSwitch(f.v, "generator", true)
U.setSwitch(f.v, "generator", false)
near(f.gen.data.fuel, before - 0.2 / 3, "repeated start resets away running time")

-- Shore power is actual production Home scanning/caching; battery charge alone is not appliance power.
active = fixture(); active.gen.data.on = false
shoreGenerator = nil; now = now + 3000
check(not U.hasPower(active.v), "nonrunning onboard generator powers fridge without shore")
shoreGenerator = { isActivated = function() return true end, getFuel = function() return 10 end }
now = now + 3000
check(U.hasPower(active.v), "running shore generator does not power camper")
U.updateFridge(active.v, active.fridge, 1)
check(active.fridge.container.temperature == U.FRIDGE_COLD, "shore-powered fridge does not cool")
H.shoreTick()
check(active.v.data.MELensShore and active.v.awake, "shore arrival does not wake appliances")
shoreGenerator = nil; now = now + 3000; H.shoreTick()
check(not U.hasPower(active.v) and active.fridge.container.temperature == 0, "shore departure leaves fridge cold")
shoreGenerator = { isActivated = function() return true end, getFuel = function() return 10 end }
active = fixture(); active.gen.data.on = true; now = now + 3000
U.setSwitch(active.v, "generator", false)
check(active.fridge.container.temperature == U.FRIDGE_COLD, "manual onboard stop cancels available shore refrigeration")
active.gen.data.on, active.gen.data.fuel = true, 0.1
U.runGenerator(active.v, active.gen, 60)
check(not active.gen.data.on and active.fridge.container.temperature == U.FRIDGE_COLD,
    "onboard fuel exhaustion cancels available shore refrigeration")
shoreGenerator = nil; now = now + 3000; U.powerLost(active.v)
check(active.fridge.container.temperature == 0, "loss of every power source leaves fridge cold")
SandboxVars.MELens.ShorePower = false
shoreGenerator = { isActivated = function() return true end, getFuel = function() return 10 end }
now = now + 3000
check(not H.shorePower(active.v), "shore power option ignored")
SandboxVars.MELens.ShorePower = true; shoreGenerator = nil; now = now + 3000

-- Propane bounds, refills and appliances; switching off is independent of fuel availability.
f = fixture(); U.setPropane(f.v, 1.9, true)
local tank = item("Base.PropaneTank"); f.p.inventory:AddItem(tank)
local insert = MELensInsertPropane:new(f.p, f.v, tank)
check(insert:complete(), "partial propane refill refused")
near(U.propaneLevel(f.v), 2, "propane capacity"); near(tank.uses, 0.9, "propane tank remainder")
local tankRemainder = tank.uses
check(not insert:complete() and tank.uses == tankRemainder, "full propane reservoir drains tank")
U.setPropane(f.v, 0, true); f.p.inventory:Remove(tank)
check(not insert:complete() and U.propaneLevel(f.v) == 0, "stale propane ownership mutates state")
check(not MELensSwitch:new(f.p, f.v, "stove", true):complete(), "stove starts without propane")
U.setPropane(f.v, 1, true)
check(MELensSwitch:new(f.p, f.v, "stove", true):complete(), "propane stove cannot start")
U.updateOven(f.v, f.oven, 10)
near(f.oven.data.heat, U.OVEN_HOT, "stove heat cap"); near(U.propaneLevel(f.v), 1 - 0.025 / 6, "stove propane consumption")
check(f.oven.container.temperature == U.OVEN_HOT, "stove does not set food container heat")
check(MELensSwitch:new(f.p, f.v, "heater", true):complete(), "propane heater cannot start")
U.updateHeater(f.v, f.heater, 10)
near(f.compartment.data.temperature, 5, "heater warms passenger compartment")
near(U.propaneLevel(f.v), 1 - 0.025 / 6 - 0.05 / 6, "heater propane consumption")
U.setPropane(f.v, 0.001, true); U.updateHeater(f.v, f.heater, 10)
check(U.propaneLevel(f.v) == 0 and not f.heater.data.on and not f.oven.data.on, "exhaustion does not stop both propane appliances")
U.addPropane(f.v, 1)
check(not f.heater.data.on and not f.oven.data.on, "refill restarts previously stopped appliances")
f.oven.data.heat = 2; f.compartment.data.temperature = 5
U.updateOven(f.v, f.oven, 10); U.updateHeater(f.v, f.heater, 10)
near(f.oven.data.heat, 1.5, "stopped oven cooling"); near(f.compartment.data.temperature, 4, "stopped heater cooling")
near(U.propaneLevel(f.v), 1, "stopped appliances consume propane")
SandboxVars.MELens.PropaneAppliances = false; f.gen.data.on = true
U.updateOven(f.v, f.oven, 1); U.setSwitch(f.v, "stove", true); U.updateOven(f.v, f.oven, 1)
check(U.canBurn(f.v) and U.propaneLevel(f.v) == 1, "electric appliance mode burns propane")
SandboxVars.MELens.PropaneAppliances = true

-- Rain is authoritative and taints collected water; unchanged weather/indoors controls.
active = fixture(); active.water.data.water = 0; rain = 0
emit("EveryTenMinutes"); check(active.water.data.water == 0, "dry weather adds water")
rain = 1; active.v.indoors = true; H.rainTick()
check(active.water.data.water == 0, "indoor camper collects rain")
active.v.indoors = false; H.rainTick()
near(active.water.data.water, 2.5, "camper roof rain amount"); check(active.water.data.tainted, "rain water not tainted")
client = true; H.rainTick()
check(active.water.data.water == 2.5, "client independently fills tank")
client = false

-- Dirty bandages use the game's clean-item replacement contract, preserving favorite and packet identity.
f = fixture(); local dirty = item("Base.BandageDirty"); dirty.afterCleaning = "Base.Bandage"
dirty.blood = 0 -- native InventoryItem getter is zero for replacement-based bandages/rags
check(MELensWashClothing.canWash(dirty), "native zero-blood dirty bandage missing from tap wash menu")
local cleanEligibility = item("Base.Bandage"); cleanEligibility.blood = 0
check(not MELensWashClothing.canWash(cleanEligibility), "clean bandage offered for washing")
cleanEligibility.afterCleaning = ""
check(not MELensWashClothing.canWash(cleanEligibility), "empty cleaning replacement offered for washing")
local ragEligibility = item("Base.RippedSheetsDirty"); ragEligibility.blood = 0; ragEligibility.afterCleaning = "Base.RippedSheets"
check(MELensWashClothing.canWash(ragEligibility), "native zero-blood dirty rag missing from wash menu")
local staleWash = item("Base.Cloth"); f.p.inventory:AddItem(staleWash)
local staleWashing = MELensWashClothing:new(f.p, f.v, staleWash, 1, 0, true)
staleWash.blood = 0
check(not staleWashing:complete() and f.p.inventory:contains(staleWash) and f.water.data.water == 10,
    "item cleaned while wash queued still consumes water")
f.p.inventory:AddItem(dirty); local washing = MELensWashClothing:new(f.p, f.v, dirty, 1, 0, true)
local beforePackets = packets
check(washing:complete(), "dirty bandage wash refused")
local clean
for candidate in pairs(f.p.inventory.items) do if candidate:getFullType() == "Base.Bandage" then clean = candidate end end
check(clean and clean.favorite == dirty.favorite and not f.p.inventory:contains(dirty), "dirty bandage not replaced by favorite clean bandage")
near(f.water.data.water, 8, "bandage washing water consumption")
check(packets == beforePackets + 2, "cleaning replacement packet count")
check(not washing:complete() and f.water.data.water == 8, "repeated cleaning duplicates bandage/consumes water")
dirty = item("Base.BandageDirty"); dirty.afterCleaning = "Base.Bandage"; f.p.inventory:AddItem(dirty)
f.water.data.water = 1
check(not MELensWashClothing:new(f.p, f.v, dirty, 1, 0, true):complete() and f.p.inventory:contains(dirty), "insufficient-water wash removes item")
f.water.data.water = 10; instanceItem = function() return nil end
check(not MELensWashClothing:new(f.p, f.v, dirty, 1, 0, true):complete()
    and f.p.inventory:contains(dirty) and f.water.data.water == 10, "failed replacement creation loses source/water")
instanceItem = function(full) return item(full) end
dirty.container = {} -- stale/non-root ownership, even if another inventory lookup still lists it
check(not MELensWashClothing:new(f.p, f.v, dirty, 1, 0, true):complete() and f.water.data.water == 10,
    "cleaning replacement removes an item from the wrong source inventory")

-- Ordinary clothing stays the same item; soap use, visible fields and water follow the vanilla contracts.
f = fixture(); local shirt = item("Base.Shirt"); shirt.class = "Clothing"
shirt.dirtiness = 50
function shirt:getDirtiness() return self.dirtiness end
shirt.bloodParts, shirt.dirtParts = { [0] = 1, [1] = 0 }, { [0] = 0, [1] = 1 }
function shirt:getBloodClothingType() return "shirt" end
function shirt:getBlood(part) return self.bloodParts[part] end
function shirt:setBlood(part, n) self.bloodParts[part] = n end
function shirt:setDirt(part, n) self.dirtParts[part] = n end
function shirt:setWetness(n) self.wetness = n end
function shirt:setDirtiness(n) self.dirtiness = n end
local soap = { uses = 2 }
function soap:hasComponent() return false end
function soap:getCurrentUses() return self.uses end
function soap:UseAndSync() self.uses = self.uses - 1 end
function f.p.inventory:getSoapList() return list({ soap }) end
BloodClothingType, ComponentType = { getCoveredParts = function() return list({ 0, 1 }) end }, { FluidContainer = "fluid" }
f.p.inventory:AddItem(shirt); beforePackets = packets
check(MELensWashClothing:new(f.p, f.v, shirt, 1, 1, false):complete(), "ordinary clothing wash refused")
check(f.p.inventory:contains(shirt) and packets == beforePackets, "clothing wash replaces/clones original item")
check(shirt.bloodParts[0] == 0 and shirt.dirtParts[1] == 0 and shirt.blood == 0
    and shirt.wetness == 100 and shirt.dirtiness == 0, "clothing visual wash fields not cleaned")
near(f.water.data.water, 8, "clothing wash water consumption"); check(soap.uses == 1, "soap not consumed once for bloody area")

for _, name in ipairs(names) do _G[name] = saved[name] end

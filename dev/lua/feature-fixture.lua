-- Disposable native feature-test fixture. This file changes setup state only:
-- it never clicks a control, calls a UI handler, queues an action or saves.
-- Re-running returns a fresh read-only snapshot without replenishing consumed
-- supplies. Set MELensFeatureTestReset=true before loading to reset this fixture.
-- Actual input: MEMCNativeLab.clickAt(x,y), clickButtonAt(x,y,1), holdKey(code,ms).
require "TimedActions/MELens_Actions"

local p = getPlayer()
local v = MELensTest and MELensTest.vehicle
if not p or not v then return "feature fixture needs the loaded player and MELensTest.vehicle" end
local M, U = MELens, MELens.Utilities
local F = MELensFeatureTest
if not F or F.vehicle ~= v or F.player ~= p then F = { items = {} } end
MELensFeatureTest = F
F.player, F.vehicle = p, v

local function optional(fn)
    local ok, value = pcall(fn)
    if ok then return value end
    return nil
end

local function ownItem(key, fullType)
    local inv = p:getInventory()
    local item = inv:getFirstEvalRecurse(function(candidate)
        return candidate:getFullType() == fullType and candidate:getModData().MELensFeatureFixture == key
    end)
    if not item then item = inv:AddItem(fullType) end
    assert(item, "missing installed fixture item " .. fullType)
    item:getModData().MELensFeatureFixture = key
    if item:getContainer() ~= inv then
        local old = item:getContainer()
        if old then old:Remove(item) end
        inv:AddItem(item)
    end
    F.items[key] = item
    return item
end

local function fill(item, fluid, amount)
    local fc = item:getFluidContainer()
    assert(fc, "fixture item lacks a native fluid container: " .. item:getFullType())
    if fc:getAmount() > 0 then fc:removeFluid(fc:getAmount()) end
    fc:addFluid(fluid, math.min(amount, fc:getCapacity()))
    item:syncItemFields()
end

if not F.initialized or MELensFeatureTestReset == true then
    local queue = ISTimedActionQueue.getTimedActionQueue(p).queue
    assert(#queue == 0, "wait for the current action queue before resetting feature setup")
    local petrol = ownItem("petrol", "Base.PetrolCan")
    local water = ownItem("water", "Base.WaterBottle")
    local propane = ownItem("propane", "Base.PropaneTank")
    ownItem("scrap", "Base.ElectronicsScrap")
    fill(petrol, Fluid.Petrol, 0.5)
    fill(water, Fluid.Water, 0.5)
    propane:setUsedDelta(0.1)
    propane:syncItemFields()

    local generator, tank = U.generatorState(v), U.waterState(v)
    assert(generator and tank, "fixture camper needs generator and water parts")
    generator.part:getModData().on = false
    generator.part:getModData().fuel = 0
    generator.part:setCondition(80)
    tank.part:getModData().water = 0
    tank.part:getModData().tainted = false
    U.setPropane(v, 0, true)
    v:getModData().MELensLightsOff = true
    U.transmit(v, generator.part)
    U.transmit(v, tank.part)
    F.initialized = true
    F.setupCount = (F.setupCount or 0) + 1
    F.setupNote = "real native containers; 0.5 L petrol, 0.5 L pure water, 0.1 propane tank, one electronics scrap"
    MELensFeatureTestReset = nil
end

-- This function only reads state. Calling it does not refresh UI, modify items,
-- advance game time, queue actions or change any committed simulation state.
function F.snapshot()
    local generator, tank = U.generatorState(v), U.waterState(v)
    local r = {
        setupCount = F.setupCount,
        setupNote = F.setupNote,
        vehicle = v:getScript():getFullName(),
        player = { x = p:getX(), y = p:getY(), z = p:getZ(), inside = p:getVehicle() == v },
        utilities = {
            generatorOn = generator and generator.on,
            generatorRunning = generator and generator.running,
            generatorFuel = generator and generator.fuel or 0,
            generatorCapacity = generator and generator.capacity or 0,
            generatorCondition = generator and generator.condition or 0,
            water = tank and tank.water or 0,
            waterCapacity = tank and tank.capacity or 0,
            tainted = tank and tank.tainted,
            propane = U.propaneLevel(v),
            stoveOn = U.isOn(v, "stove"), heaterOn = U.isOn(v, "heater"),
            lightsOn = M.lightsSwitchedOn(v), hasPower = U.hasPower(v),
        },
        inventory = {}, sums = {}, queue = {}, controls = {},
    }
    local inv = p:getInventory()
    for key, item in pairs(F.items) do
        local fc = item:getFluidContainer()
        r.inventory[key] = {
            id = item:getID(), fullType = item:getFullType(),
            inMainInventory = inv:contains(item),
            amount = fc and fc:getAmount() or 0,
            capacity = fc and fc:getCapacity() or 0,
            purePetrol = fc and fc:isPureFluid(Fluid.Petrol) or false,
            pureWater = fc and fc:isPureFluid(Fluid.Water) or false,
            propane = M.Parts.propaneIn(item),
            weight = optional(function() return item:getWeight() end),
        }
    end
    local function amount(key, fluid)
        local item = F.items[key]
        local fc = item and item:getFluidContainer()
        return fc and fc:isPureFluid(fluid) and fc:getAmount() or 0
    end
    r.sums.petrol = r.utilities.generatorFuel + amount("petrol", Fluid.Petrol)
    r.sums.water = r.utilities.water + amount("water", Fluid.Water)
    r.sums.propane = r.utilities.propane + (F.items.propane and M.Parts.propaneIn(F.items.propane) or 0)
    r.inventoryWeight = optional(function() return inv:getCapacityWeight() end)
    r.player.capacity = optional(function() return p:getMaxWeight() end)
    r.player.aiming = optional(function() return p:isAiming() end)
    r.player.pathActive = optional(function() return p:getPath2() ~= nil end)
    r.player.thirst = p:getStats():get(CharacterStat.THIRST)
    r.player.timedActionInstant = p:isTimedActionInstant()
    r.player.electricity = p:getPerkLevel(Perks.Electricity)
    r.vehicleSpeed = v:getCurrentSpeedKmHour()
    if p:getVehicle() == v then
        local x, z = M.Parts.characterAt(v, p)
        r.player.passengerX, r.player.passengerZ = x, z
    end
    local queue = ISTimedActionQueue.getTimedActionQueue(p).queue
    r.queueCount = #queue
    for i, action in ipairs(queue) do
        r.queue[i] = { type = tostring(action.Type), which = action.which, on = action.on,
            maxTime = action.maxTime, jobDelta = optional(function() return action:getJobDelta() end) }
    end

    local w = M.Dashboard.instance
    if w and w:isVisible() then
        r.dashboard = { x = w:getX(), y = w:getY(), width = w:getWidth(), height = w:getHeight() }
        local actions = {
            [w.onGenerator] = "generator", [w.onAddFuel] = "addFuel", [w.onFix] = "fixGenerator",
            [w.onLights] = "lights", [w.onAddWater] = "addWater", [w.onAddPropane] = "addPropane",
            [w.onStove] = "stove", [w.onHeater] = "heater", [w.onRename] = "rename", [w.onPaint] = "paint",
        }
        for i, c in ipairs(w.controls) do
            r.controls[i] = {
                action = actions[c.fn] or "unknown", enabled = c.enabled == true,
                x = w:getX() + c.x, y = w:getY() + c.y, width = c.w, height = c.h,
                centerX = math.floor(w:getX() + c.x + c.w / 2),
                centerY = math.floor(w:getY() + c.y + c.h / 2),
                text = c.button and c.button.text, tip = c.tip,
            }
        end
    end
    return r
end

return F.snapshot()

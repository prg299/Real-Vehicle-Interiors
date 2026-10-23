--
-- ME: LENS camper utilities: the generator, the water tank, the oven, the fridge and
-- the heater. State lives in the parts' modData (MELens_Parts.lua), so it is saved and
-- synced with the vehicle; the part update functions run wherever the game runs
-- vehicle Lua (single player, or the server in multiplayer).
--
--   generator  { on, fuel (litres) }, condition = the part's condition
--   water tank { water (litres), tainted }
--   oven       { on, heat (container temperature) }
--   heater     { on } on its furniture spot
--   propane    vehicle modData MELensPropane (tanks of gas; the stove and the heater burn it)
--   lights     vehicle modData MELensLightsOff (MELens_Cabin.lua)
--
require "MELens_Parts"

MELens = MELens or {}
local M = MELens
M.Utilities = M.Utilities or {}
local U = M.Utilities
local P = M.Parts

U.IDLE_FUEL_PER_HOUR = 0.08  -- litres per game hour, including battery charging
U.FRIDGE_FUEL_PER_HOUR = 0.12
U.STOVE_FUEL_PER_HOUR = 0.4
U.HEATER_FUEL_PER_HOUR = 0.2
U.WEAR_PER_HOUR = 0.25       -- condition lost per running hour (a new generator: about 16 days)
U.CHARGE_PER_MINUTE = 0.001  -- battery charge while running (the same as a running engine)
U.NOISE_RADIUS = 20          -- tiles; like a generator on the ground, zombies hear it
U.OVEN_HOT = 2.0             -- container temperature of a hot oven (vanilla stoves reach about 2)
U.FRIDGE_COLD = 0.2          -- container temperature of a powered fridge (vanilla: 0.2)
U.HEATER_WARMTH = 15         -- degrees the heater adds inside, at most
U.PROPANE_CAPACITY = 2.0     -- tanks of propane a vehicle holds (the game's propane tank is 1.0)
U.PROPANE_START = 0.4        -- what a vehicle holds that never had a record (also one from an older save)
U.PROPANE_STOVE = 0.025      -- tanks an hour while the stove burns (one tank: 40 hours)
U.PROPANE_HEATER = 0.05      -- tanks an hour while the heater burns (one tank: 20 hours)

local function num(value, default)
    return tonumber(value) or default
end

function U.profile(vehicle)
    return M.profileFor(vehicle)
end

function U.part(vehicle, id)
    return vehicle and vehicle:getPartById(id) or nil
end

-- Server side (and single player): send a part's modData to everyone.
function U.transmit(vehicle, part)
    if isServer() then
        vehicle:transmitPartModData(part)
    end
end

-- The game only runs a parked vehicle's part update Lua while the vehicle "needs parts
-- update" (a running engine sets it). A camper's appliances need it while anything
-- runs, warms up or cools down.
function U.busy(vehicle)
    local gen = U.part(vehicle, P.GENERATOR)
    if gen and gen:getModData().on == true then return true end
    local oven = U.part(vehicle, P.OVEN)
    if oven then
        local d = oven:getModData()
        if d.on == true or num(d.heat, 1.0) > 1.001 then return true end
    end
    local heater = U.heaterPart(vehicle)
    if heater and heater:getModData().on == true then return true end
    if vehicle:getModData().MELensShore == true then return true end
    if U.lampsActive and U.lampsActive(vehicle) then return true end
    local pc = vehicle:getPartById("PassengerCompartment")
    return pc ~= nil and num(pc:getModData().temperature, 0) > 0.01
end

function U.wake(vehicle)
    vehicle:setNeedPartsUpdate(true)
end

-- On load: keep a running camper running.
function U.initGenerator(vehicle, part)
    if U.busy(vehicle) then
        U.wake(vehicle)
    end
end

------------------------------------------------------------------------------------
-- Propane: what the stove and the heater burn (sandbox option PropaneAppliances; off, they run on power as before)
------------------------------------------------------------------------------------

U.PROPANE_KEY = "MELensPropane"
local propaneSent = {}           -- vehicle id -> the level last sent out (a server)

function U.propaneOn()
    return M.sandbox("PropaneAppliances", true) == true
end

-- Tanks of propane in the vehicle (1.0 is one of the game's full tanks). A vehicle that never had a record holds
-- a starting amount, so one from an older save is not left without.
function U.propaneLevel(vehicle)
    local level = tonumber(vehicle:getModData()[U.PROPANE_KEY])
    if level == nil then return U.PROPANE_START end
    return math.max(0, math.min(U.PROPANE_CAPACITY, level))
end

-- Sets the level. A server sends it to everyone once it moved by a hundredth of a tank (or when forced).
function U.setPropane(vehicle, level, force)
    level = math.max(0, math.min(U.PROPANE_CAPACITY, level))
    vehicle:getModData()[U.PROPANE_KEY] = level
    if isServer() then
        local id = vehicle:getId()
        local sent = propaneSent[id]
        if force or sent == nil or math.abs(level - sent) >= 0.01 then
            propaneSent[id] = level
            vehicle:transmitModData()
        end
    end
end

-- Puts propane into the vehicle (tanks). Returns what went in.
function U.addPropane(vehicle, amount)
    local level = U.propaneLevel(vehicle)
    local put = math.max(0, math.min(amount, U.PROPANE_CAPACITY - level))
    if put > 0 then
        U.setPropane(vehicle, level + put, true)
    end
    return put
end

-- Whether the stove and the heater have what they burn: propane, or with the option off the power as before.
function U.canBurn(vehicle)
    if U.propaneOn() then
        return U.propaneLevel(vehicle) > 0
    end
    return U.hasPower(vehicle)
end

local function switchOff(vehicle, part)
    if part and part:getModData().on == true then
        part:getModData().on = false
        U.transmit(vehicle, part)
    end
end

-- Burns propane for an appliance (rate: tanks an hour). Out of propane the stove and the heater both go out, and
-- stay off when a tank is put in. Returns whether the appliance burned.
function U.burn(vehicle, rate, minutes)
    local level = U.propaneLevel(vehicle)
    if level <= 0 then return false end
    level = level - rate * minutes / 60
    if level <= 0 then
        U.setPropane(vehicle, 0, true)
        switchOff(vehicle, U.part(vehicle, P.OVEN))
        switchOff(vehicle, U.heaterPart(vehicle))
        return false
    end
    U.setPropane(vehicle, level)
    return true
end

------------------------------------------------------------------------------------
-- Generator
------------------------------------------------------------------------------------

function U.fuelCapacity(vehicle)
    local profile = U.profile(vehicle)
    return profile and profile.fuelTank or 20
end

function U.generatorState(vehicle)
    local part = U.part(vehicle, P.GENERATOR)
    if not part then return nil end
    local data = part:getModData()
    local fuel = num(data.fuel, 0)
    local condition = part:getCondition()
    return {
        part = part,
        on = data.on == true,
        fuel = fuel,
        capacity = U.fuelCapacity(vehicle),
        condition = condition,
        running = data.on == true and fuel > 0 and condition > 0,
    }
end

-- Power for the fridge, the stove and the heater: the camper's own generator running, or a generator
-- beside it (MELens_Home.lua, shore power).
function U.hasPower(vehicle)
    local state = U.generatorState(vehicle)
    if state ~= nil and state.running then return true end
    return M.Home ~= nil and M.Home.shorePower(vehicle)
end

function U.createGenerator(vehicle, part)
    if isClient() then return end
    local data = part:getModData()
    local fresh = data.fuel == nil and data.on == nil
    if data.fuel == nil then data.fuel = 0 end
    if data.on == nil then data.on = false end
    if fresh and part:getCondition() < 0 then part:setCondition(100) end
end

function U.updateGenerator(vehicle, part, elapsedMinutes)
    U.runGenerator(vehicle, part, elapsedMinutes)
    -- Nothing running, warming or cooling any more: let the camper rest.
    -- The stock Engine callback can clear this flag earlier in the same update.
    -- Re-arm it while appliances are active, even with the engine stopped and cold.
    vehicle:setNeedPartsUpdate(U.busy(vehicle))
end

-- Server: the players get the battery's charge again once it moved 0.001 since they last got it (or always with
-- force). The game's chargeBattery only sends it when the charge crosses a hundredth, so a running generator (0.001 a
-- minute) left the clients' battery up to a percent behind the server's.
local sentCharge = {}      -- battery item ID -> charge last sent
function U.syncBatteryCharge(vehicle, force)
    if not isServer() or not vehicle.getBattery or not vehicle.transmitPartUsedDelta then return end
    local battery = vehicle:getBattery()
    local item = battery and battery:getInventoryItem()
    if not item or not item.getCurrentUsesFloat then return end
    local charge = item:getCurrentUsesFloat()
    local id = item.getID and item:getID() or item
    local sent = sentCharge[id]
    if force or sent == nil or math.abs(charge - sent) >= 0.001 then
        sentCharge[id] = charge
        vehicle:transmitPartUsedDelta(battery)
    end
end

function U.generatorFuelRate(vehicle)
    local rate = U.IDLE_FUEL_PER_HOUR
    local profile = U.profile(vehicle)
    for index in ipairs(profile and profile.spots or {}) do
        if P.pieceAt(P.spotPart(vehicle, index)) == "fridge" then
            rate = rate + U.FRIDGE_FUEL_PER_HOUR
        end
    end
    if not U.propaneOn() then
        local oven, heater = U.part(vehicle, P.OVEN), U.heaterPart(vehicle)
        if oven and oven:getModData().on == true then rate = rate + U.STOVE_FUEL_PER_HOUR end
        if heater and heater:getModData().on == true then rate = rate + U.HEATER_FUEL_PER_HOUR end
    end
    return rate * math.max(0, M.sandbox("GeneratorFuelUse", 1.0))
end

function U.runGenerator(vehicle, part, elapsedMinutes)
    local data = part:getModData()
    if data.on ~= true or not elapsedMinutes or elapsedMinutes <= 0 then return end
    local fuel = num(data.fuel, 0)
    if fuel <= 0 or part:getCondition() <= 0 then
        -- Out of petrol or broken: it stops by itself.
        data.on = false
        data.fuel = math.max(0, fuel)
        U.transmit(vehicle, part)
        U.powerLost(vehicle)
        return
    end
    -- A parked vehicle can receive a long catch-up interval. It only generates power
    -- for the portion its remaining fuel and condition can actually sustain.
    local fuelRate = U.generatorFuelRate(vehicle)
    local wearRate = U.WEAR_PER_HOUR * math.max(0, M.sandbox("GeneratorWear", 1.0))
    local wear = num(data.wear, 0)
    local hours = elapsedMinutes / 60
    if fuelRate > 0 then hours = math.min(hours, fuel / fuelRate) end
    if wearRate > 0 then hours = math.min(hours, math.max(0, part:getCondition() - wear) / wearRate) end
    local runningMinutes = hours * 60
    data.fuel = math.max(0, fuel - fuelRate * hours)
    data.wear = wear + wearRate * hours
    local lostCondition = math.floor(data.wear + 0.000000001)
    if lostCondition >= 1 then
        part:setCondition(math.max(0, part:getCondition() - lostCondition))
        data.wear = math.max(0, data.wear - lostCondition)
        if isServer() then
            vehicle:transmitPartCondition(part)
        end
    end
    if runningMinutes > 0 then
        VehicleUtils.chargeBattery(vehicle, U.CHARGE_PER_MINUTE * runningMinutes)
        U.syncBatteryCharge(vehicle, false)
    end
    data.noise = num(data.noise, 0) + runningMinutes
    if data.noise >= 10 then
        data.noise = 0
        addSound(nil, math.floor(vehicle:getX()), math.floor(vehicle:getY()), math.floor(vehicle:getZ()), U.NOISE_RADIUS, U.NOISE_RADIUS)
    end
    local stopped = data.fuel <= 0.000000001 or part:getCondition() <= 0
    if stopped then
        if data.fuel <= 0.000000001 then data.fuel = 0 end
        data.on = false
        U.powerLost(vehicle)
        U.syncBatteryCharge(vehicle, true)
    end
    data.sync = num(data.sync, 0) + runningMinutes
    if data.sync >= 10 or stopped then
        data.sync = 0
        U.transmit(vehicle, part)
    end
end

------------------------------------------------------------------------------------
-- Water tank
------------------------------------------------------------------------------------

function U.waterCapacity(vehicle)
    local profile = U.profile(vehicle)
    return profile and profile.waterTank or 60
end

function U.waterState(vehicle)
    local part = U.part(vehicle, P.WATER)
    if not part then return nil end
    local data = part:getModData()
    return {
        part = part,
        water = num(data.water, 0),
        capacity = U.waterCapacity(vehicle),
        tainted = data.tainted == true,
    }
end

function U.createWaterTank(vehicle, part)
    if isClient() then return end
    local data = part:getModData()
    if data.water == nil then data.water = 0 end
    if data.tainted == nil then data.tainted = false end
end

-- Adds or takes water (litres; negative takes). Tainted water taints the tank until it
-- is empty. Returns the amount actually moved.
function U.changeWater(vehicle, amount, tainted)
    local part = U.part(vehicle, P.WATER)
    if not part then return 0 end
    local data = part:getModData()
    local water = num(data.water, 0)
    local new = math.max(0, math.min(U.waterCapacity(vehicle), water + amount))
    if new == water then return 0 end              -- a full tank takes nothing (nor is it tainted by what did not go in)
    data.water = new
    if amount > 0 and tainted then
        data.tainted = true
    elseif new <= 0 then
        data.tainted = false
    end
    U.transmit(vehicle, part)
    return new - water
end

------------------------------------------------------------------------------------
-- Kitchen: the oven (its own container) and the taps
------------------------------------------------------------------------------------

-- The kitchen spot part and its spot, if a kitchen is installed.
function U.kitchen(vehicle)
    local profile = U.profile(vehicle)
    for index = 1, profile and #profile.spots or 0 do
        local part = P.spotPart(vehicle, index)
        if P.pieceAt(part) == "kitchen" then
            return part, profile.spots[index]
        end
    end
    return nil
end

function U.ovenState(vehicle)
    local part = U.part(vehicle, P.OVEN)
    if not part then return nil end
    local data = part:getModData()
    return { part = part, on = data.on == true, heat = num(data.heat, 1.0), kitchen = U.kitchen(vehicle) ~= nil }
end

function U.initOven(vehicle, part)
    local container = part:getItemContainer()
    if container then
        container:setType("MELensOven")
    end
end

-- The oven is in reach at the kitchen.
function U.ovenTest(vehicle, part, chr)
    local kitchen = U.kitchen(vehicle)
    return kitchen ~= nil and P.canReach(vehicle, kitchen, chr)
end

function U.updateOven(vehicle, part, elapsedMinutes)
    local data = part:getModData()
    local container = part:getItemContainer()
    if not container or not elapsedMinutes or elapsedMinutes <= 0 then return end
    local heating = data.on == true and U.kitchen(vehicle) ~= nil and U.canBurn(vehicle)
    if heating and U.propaneOn() then
        heating = U.burn(vehicle, U.PROPANE_STOVE, elapsedMinutes)
    end
    local heat = num(data.heat, 1.0)
    if heating then
        heat = math.min(U.OVEN_HOT, heat + 0.1 * elapsedMinutes)
    else
        heat = math.max(1.0, heat - 0.05 * elapsedMinutes)
    end
    data.heat = heat
    container:setCustomTemperature(heat > 1.001 and heat or 0)
end

------------------------------------------------------------------------------------
-- Fridge and heater (furniture spots)
------------------------------------------------------------------------------------

-- The generator stopped: fridges stop cooling at once (part updates may pause now).
function U.powerLost(vehicle)
    local profile = U.profile(vehicle)
    for index = 1, profile and #profile.spots or 0 do
        local part = P.spotPart(vehicle, index)
        if P.pieceAt(part) == "fridge" then
            U.updateFridge(vehicle, part, 0)
        end
    end
end

function U.updateFridge(vehicle, part, elapsedMinutes)
    local container = part:getItemContainer()
    if container then
        container:setCustomTemperature(U.hasPower(vehicle) and U.FRIDGE_COLD or 0)
    end
end

function U.heaterPart(vehicle)
    local profile = U.profile(vehicle)
    for index = 1, profile and #profile.spots or 0 do
        local part = P.spotPart(vehicle, index)
        if P.pieceAt(part) == "heater" then
            return part
        end
    end
    return nil
end

-- Like a car's heater: warms the passenger compartment, which the game adds to the
-- air temperature of everyone inside.
function U.updateHeater(vehicle, part, elapsedMinutes)
    local pc = vehicle:getPartById("PassengerCompartment")
    if not pc or not elapsedMinutes or elapsedMinutes <= 0 then return end
    local pcData = pc:getModData()
    local temperature = num(pcData.temperature, 0)
    local before = temperature
    local burning = part:getModData().on == true and U.canBurn(vehicle)
    if burning and U.propaneOn() then
        burning = U.burn(vehicle, U.PROPANE_HEATER, elapsedMinutes)
    end
    if burning then
        temperature = math.min(U.HEATER_WARMTH, temperature + 0.5 * elapsedMinutes)
    elseif temperature > 0 then
        temperature = math.max(0, temperature - 0.1 * elapsedMinutes)
    end
    pcData.temperature = temperature
    if math.abs(temperature - before) > 0.01 then
        pcData.heaterSync = num(pcData.heaterSync, 0) + elapsedMinutes
        if pcData.heaterSync >= 5 then
            pcData.heaterSync = 0
            U.transmit(vehicle, pc)
        end
    end
end

------------------------------------------------------------------------------------
-- Switches (called by the timed actions, on the server in multiplayer)
------------------------------------------------------------------------------------

-- which: "generator", "stove" or "heater".
function U.setSwitch(vehicle, which, on)
    local part
    if which == "generator" then
        part = U.part(vehicle, P.GENERATOR)
    elseif which == "stove" then
        part = U.part(vehicle, P.OVEN)
    elseif which == "heater" then
        part = U.heaterPart(vehicle)
    end
    if not part then return false end
    local data = part:getModData()
    if which == "generator" and (data.on == true) ~= (on == true) then
        local hours = getGameTime():getWorldAgeHours()
        if data.on == true then
            U.runGenerator(vehicle, part, math.max(0, hours - part:getLastUpdated()) * 60)
        end
        -- Native part callbacks measure time since last update, including time spent parked OFF.
        -- Start the clock now so restarting cannot burn fuel for that idle interval.
        part:setLastUpdated(hours)
    end
    part:getModData().on = on == true
    U.transmit(vehicle, part)
    U.wake(vehicle)
    if which == "generator" and not on then
        U.powerLost(vehicle)
        U.syncBatteryCharge(vehicle, true)
    end
    return true
end

function U.isOn(vehicle, which)
    if which == "generator" then
        local state = U.generatorState(vehicle)
        return state ~= nil and state.on
    elseif which == "stove" then
        local state = U.ovenState(vehicle)
        return state ~= nil and state.on
    elseif which == "heater" then
        local part = U.heaterPart(vehicle)
        return part ~= nil and part:getModData().on == true
    end
    return false
end

------------------------------------------------------------------------------------
-- Occupied lamps: one ephemeral clock per vehicle, owned by single player/server.
-- Native vehicle entry events only cover local players; the existing sync tick
-- observes the server's actual passengers too, including a standing-seat repair.
------------------------------------------------------------------------------------

U.LAMP_DRAIN_PER_HOUR = 0.0018
local lampClocks, lampScan, lampSeen = {}, nil, {}
local lampIndex = 1
local lampCell, nextLampScan, lastLampTick = nil, 0, 0
local LAMP_SCAN_MS, LAMP_SCAN_BATCH = 500, 64

local function lampState(vehicle)
    local profile = M.profileFor(vehicle)
    if not profile or not profile.light or not vehicle.getBattery or not vehicle.getMaxPassengers then return nil end
    local battery = vehicle:getBattery()
    local item = battery and battery:getInventoryItem()
    local occupants = {}
    local occupied = false
    for seat = 0, vehicle:getMaxPassengers() - 1 do
        local player = vehicle:getCharacter(seat)
        if player and player:getVehicle() == vehicle and not player:isDead() then
            occupants[player], occupied = true, true
        end
    end
    local active = occupied and vehicle:getModData().MELensLightsOff ~= true
        and item ~= nil and item:getCurrentUsesFloat() > 0
    return active, occupants, battery, item
end

function U.lampsActive(vehicle)
    if isClient() then return false end
    return lampState(vehicle) == true
end

-- Returns without touching a client's battery or clocks. No saved last-hour value
-- is used, so loading a save or returning to an unloaded vehicle never catches up.
function U.observeLamps(vehicle, force)
    if isClient() or not vehicle then return end
    local id = vehicle:getId()
    if not vehicle.getSquare or not vehicle:getSquare() then lampClocks[id] = nil; return end
    local active, occupants, battery, item = lampState(vehicle)
    if active == nil then lampClocks[id] = nil; return end
    local gameTime = getGameTime and getGameTime()
    local hour = gameTime and gameTime:getWorldAgeHours()
    if type(hour) ~= "number" or hour ~= hour or math.abs(hour) == math.huge then return end
    local previous = lampClocks[id]
    if previous and previous.vehicle ~= vehicle then previous = nil end
    local continuous = false
    if previous and previous.active and active then
        for player in pairs(occupants) do
            if previous.occupants[player] then continuous = true; break end
        end
    end
    local sameBattery = previous and previous.item == item
    local clock = { vehicle = vehicle, hour = hour, active = active, occupants = occupants, item = item,
        unapplied = not force and continuous and sameBattery and hour >= previous.hour and (previous.unapplied or 0) or 0 }
    lampClocks[id] = clock
    if force or not previous or previous.active ~= active or (active and not continuous) then U.wake(vehicle) end
    if force or not continuous or not sameBattery or hour <= previous.hour then return end
    -- The game's chargeBattery helper applies its delta twice. Clamp the actual
    -- battery value once here, and let the native server replicate the part.
    local before = item:getCurrentUsesFloat()
    local debit = clock.unapplied + U.LAMP_DRAIN_PER_HOUR * (hour - previous.hour)
    local requested = math.max(0, before - debit)
    clock.unapplied = debit
    if debit > 0 and requested ~= before then
        item:setUsedDelta(requested)
        local after = item:getCurrentUsesFloat()
        -- Native batteries quantize uses. A half-second debit is smaller than
        -- one use, so retain the unapplied fraction until the battery can debit it.
        clock.unapplied = debit - math.max(0, before - after)
        if after ~= before and isServer() then vehicle:transmitPartUsedDelta(battery) end
        if after <= 0 then clock.active, clock.unapplied = false, 0; U.wake(vehicle) end
    end
end

-- Position keepalives prime a new occupied period but never reset an already
-- continuous one; otherwise frequent walking packets would postpone all drain.
function U.primeLamps(vehicle)
    if isClient() or not vehicle then return end
    local previous = lampClocks[vehicle:getId()]
    local active, occupants = lampState(vehicle)
    if previous and previous.vehicle == vehicle and previous.active == active and active then
        for player in pairs(occupants) do if previous.occupants[player] then return end end
    end
    U.observeLamps(vehicle, true)
end

-- At most 64 loaded vehicles per frame; after a complete pass, wait 500 real ms.
-- An interrupted/new-world pass discards its clocks. Removed vehicles lose their
-- baseline at the end of the pass and are primed anew if they load again.
function U.lampTick()
    if isClient() then return end
    local milliseconds = getTimestampMs()
    local cell = getCell and getCell()
    if cell ~= lampCell or milliseconds < lastLampTick then
        lampClocks, lampScan, lampSeen = {}, nil, {}
        lampCell, nextLampScan = cell, 0
    end
    lastLampTick = milliseconds
    if not cell then return end
    if lampScan == nil then
        if milliseconds < nextLampScan then return end
        -- IsoCell exposes a Java Set, not an indexed list. Snapshot its iterator
        -- on the game thread so a vehicle loading between frames cannot invalidate
        -- the next batch's iterator.
        lampScan, lampSeen, lampIndex = {}, {}, 1
        local it = cell:getVehicles():iterator()
        while it:hasNext() do lampScan[#lampScan + 1] = it:next() end
    end
    local count = #lampScan
    local stop = math.min(count, lampIndex + LAMP_SCAN_BATCH - 1)
    for index = lampIndex, stop do
        local vehicle = lampScan[index]
        local id = vehicle:getId()
        if lampSeen[id] ~= vehicle then
            lampSeen[id] = vehicle
            U.observeLamps(vehicle)
            -- A cold stock engine may sleep the parts before the generator's own
            -- minute is due. Reuse this bounded authority scan to keep appliances ticking.
            if M.profileFor(vehicle) and U.busy(vehicle) and not vehicle:needPartsUpdate() then
                U.wake(vehicle)
            end
        end
    end
    lampIndex = stop + 1
    if lampIndex > count then
        for id, clock in pairs(lampClocks) do
            if lampSeen[id] ~= clock.vehicle then lampClocks[id] = nil end
        end
        lampScan, nextLampScan = nil, milliseconds + LAMP_SCAN_MS
    end
end

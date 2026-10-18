--
-- ME: LENS timed actions. Shared, with the work in complete(), so they run on the
-- server in multiplayer (the game rebuilds them there from the fields named like the
-- arguments of new()) and in the normal way in single player.
--
require "TimedActions/ISBaseTimedAction"
require "TimedActions/ISWashYourself"
require "TimedActions/ISWashClothing"
require "MELens_Utilities"
require "MELens_Loose"
require "MELens_Home"

local function U() return MELens.Utilities end
local function P() return MELens.Parts end

local function inCamper(character, vehicle)
    return vehicle ~= nil and character:getVehicle() == vehicle
end

-- In the camper, or standing next to it: the dashboard works from outside too.
MELens.Parts.AT_RANGE = 5.5
function MELens.Parts.atCamper(character, vehicle)
    if not vehicle or not character then return false end
    local inside = character:getVehicle()
    if inside then return inside == vehicle end
    local r = MELens.Parts.AT_RANGE
    return character:DistToSquared(vehicle:getX(), vehicle:getY()) <= r * r
end
local atCamper = MELens.Parts.atCamper

-- A character's container item holding only petrol, or only (tainted) water.
function MELens.Parts.fluidIn(item, kind)
    local fc = item and item:getFluidContainer()
    if not fc or fc:isEmpty() then return nil end
    if kind == "petrol" then
        return fc:isPureFluid(Fluid.Petrol) and fc or nil
    end
    if fc:isPureFluid(Fluid.Water) or fc:isPureFluid(Fluid.TaintedWater) then
        return fc
    end
    return nil
end

-- Tanks of gas in a propane tank item (the game's: 1.0 is full), or 0 for anything else.
function MELens.Parts.propaneIn(item)
    if not item or item:getFullType() ~= "Base.PropaneTank" then return 0 end
    return item:getCurrentUsesFloat()
end

------------------------------------------------------------------------------------
-- Pour petrol into the generator
------------------------------------------------------------------------------------

MELensRefuelGenerator = ISBaseTimedAction:derive("MELensRefuelGenerator")

function MELensRefuelGenerator:isValid()
    local state = U().generatorState(self.vehicle)
    return atCamper(self.character, self.vehicle) and state ~= nil and state.fuel < state.capacity
        and self.character:getInventory():contains(self.item) and MELens.Parts.fluidIn(self.item, "petrol") ~= nil
end

function MELensRefuelGenerator:update()
    self.item:setJobDelta(self:getJobDelta())
end

function MELensRefuelGenerator:start()
    self.item:setJobType(getText("ContextMenu_GeneratorAddFuel"))
    self.item:setJobDelta(0.0)
    self:setActionAnim("refuelgascan")
    self:setOverrideHandModels(self.item, nil)
    self.sound = self.character:playSound("GeneratorAddFuel")
end

function MELensRefuelGenerator:stopSound()
    if self.sound and self.character:getEmitter():isPlaying(self.sound) then
        self.character:stopOrTriggerSound(self.sound)
    end
end

function MELensRefuelGenerator:stop()
    self:stopSound()
    self.item:setJobDelta(0.0)
    ISBaseTimedAction.stop(self)
end

function MELensRefuelGenerator:perform()
    self:stopSound()
    self.item:setJobDelta(0.0)
    ISBaseTimedAction.perform(self)
end

function MELensRefuelGenerator:complete()
    if not self:isValid() then return false end
    local state = U().generatorState(self.vehicle)
    local fc = MELens.Parts.fluidIn(self.item, "petrol")
    if not state or not fc then return false end
    local amount = math.min(fc:getAmount(), state.capacity - state.fuel)
    if amount <= 0 then return false end
    fc:removeFluid(amount)
    self.item:syncItemFields()
    local data = state.part:getModData()
    data.fuel = state.fuel + amount
    U().transmit(self.vehicle, state.part)
    return true
end

function MELensRefuelGenerator:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    local state = U().generatorState(self.vehicle)
    local fc = self.item and self.item:getFluidContainer()
    local amount = (state and fc) and math.min(fc:getAmount(), state.capacity - state.fuel) or 1
    return 70 + amount * 40
end

function MELensRefuelGenerator:new(character, vehicle, item)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.item = item
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

------------------------------------------------------------------------------------
-- Pour water into the tank
------------------------------------------------------------------------------------

MELensFillWaterTank = ISBaseTimedAction:derive("MELensFillWaterTank")

function MELensFillWaterTank:isValid()
    local state = U().waterState(self.vehicle)
    return atCamper(self.character, self.vehicle) and state ~= nil and state.water < state.capacity
        and self.character:getInventory():contains(self.item) and MELens.Parts.fluidIn(self.item, "water") ~= nil
end

function MELensFillWaterTank:update()
    self.item:setJobDelta(self:getJobDelta())
end

function MELensFillWaterTank:start()
    self.item:setJobType(getText("ContextMenu_MELens_FillWaterTank"))
    self.item:setJobDelta(0.0)
    self:setActionAnim("fill_container_tap")
    self:setOverrideHandModels(self.item, nil)
    self.sound = self.character:playSound("PourWaterIntoObject")
end

MELensFillWaterTank.stopSound = MELensRefuelGenerator.stopSound
MELensFillWaterTank.stop = MELensRefuelGenerator.stop
MELensFillWaterTank.perform = MELensRefuelGenerator.perform

function MELensFillWaterTank:complete()
    if not self:isValid() then return false end
    local state = U().waterState(self.vehicle)
    local fc = MELens.Parts.fluidIn(self.item, "water")
    if not state or not fc then return false end
    local amount = math.min(fc:getAmount(), state.capacity - state.water)
    if amount <= 0 then return false end
    local tainted = fc:isPureFluid(Fluid.TaintedWater)
    fc:removeFluid(amount)
    self.item:syncItemFields()
    U().changeWater(self.vehicle, amount, tainted)
    return true
end

function MELensFillWaterTank:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    local state = U().waterState(self.vehicle)
    local fc = self.item and self.item:getFluidContainer()
    local amount = (state and fc) and math.min(fc:getAmount(), state.capacity - state.water) or 1
    return math.max(6, amount) * 7
end

function MELensFillWaterTank:new(character, vehicle, item)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.item = item
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

------------------------------------------------------------------------------------
-- Repair the generator with electronics scrap (like fixing a generator)
------------------------------------------------------------------------------------

MELensRepairGenerator = ISBaseTimedAction:derive("MELensRepairGenerator")

function MELensRepairGenerator:isValid()
    local state = U().generatorState(self.vehicle)
    return atCamper(self.character, self.vehicle) and state ~= nil and not state.on and state.condition < 100
        and self.item ~= nil and self.item:getType() == "ElectronicsScrap"
        and self.character:getInventory():contains(self.item)
end

function MELensRepairGenerator:start()
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Mid")
    self.sound = self.character:playSound("GeneratorRepair")
end

MELensRepairGenerator.stopSound = MELensRefuelGenerator.stopSound

function MELensRepairGenerator:stop()
    self:stopSound()
    ISBaseTimedAction.stop(self)
end

function MELensRepairGenerator:perform()
    self:stopSound()
    ISBaseTimedAction.perform(self)
end

function MELensRepairGenerator:complete()
    if not self:isValid() then return false end
    local state = U().generatorState(self.vehicle)
    if not state then return false end
    local skill = self.character:getPerkLevel(Perks.Electricity)
    state.part:setCondition(math.min(100, state.condition + 4 + math.floor(skill / 2)))
    if isServer() then
        self.vehicle:transmitPartCondition(state.part)
    end
    self.character:removeFromHands(self.item)
    self.character:getInventory():Remove(self.item)
    sendRemoveItemFromContainer(self.character:getInventory(), self.item)
    addXp(self.character, Perks.Electricity, 5)
    return true
end

function MELensRepairGenerator:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return 150 - self.character:getPerkLevel(Perks.Electricity) * 3
end

function MELensRepairGenerator:new(character, vehicle, item)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.item = item
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

------------------------------------------------------------------------------------
-- Switches: generator, stove, heater, lights
------------------------------------------------------------------------------------

MELensSwitch = ISBaseTimedAction:derive("MELensSwitch")

function MELensSwitch:isValid()
    if not atCamper(self.character, self.vehicle) then return false end
    if self.which == "generator" and self.on then
        local state = U().generatorState(self.vehicle)
        return state ~= nil and state.fuel > 0 and state.condition > 0
    end
    if (self.which == "stove" or self.which == "heater") and self.on then
        return U().canBurn(self.vehicle) or not U().propaneOn()       -- (without propane there is nothing to burn)
    end
    return true
end

function MELensSwitch:start()
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Mid")
end

function MELensSwitch:perform()
    local sounds = {
        generator = self.on and "GeneratorStarting" or "GeneratorStopping",
        lights = "LightSwitch",
    }
    self.character:playSound(sounds[self.which] or "LightSwitch")
    ISBaseTimedAction.perform(self)
end

function MELensSwitch:complete()
    if not self:isValid() then return false end
    if self.which == "lights" then
        local data = self.vehicle:getModData()
        data.MELensLightsOff = (not self.on) or nil
        if U().observeLamps then U().observeLamps(self.vehicle, true) end
        if isServer() then
            self.vehicle:transmitModData()
        end
        return true
    end
    return U().setSwitch(self.vehicle, self.which, self.on)
end

function MELensSwitch:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return self.which == "generator" and 40 or 10
end

function MELensSwitch:new(character, vehicle, which, on)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.which = which
    o.on = on
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

------------------------------------------------------------------------------------
-- The taps: drink, fill a container, wash (water from the tank)
------------------------------------------------------------------------------------

local function tankFluid(vehicle, amount)
    local state = U().waterState(vehicle)
    local fc = FluidContainer.CreateContainer()
    fc:setCapacity(math.max(amount, 0.001))
    fc:addFluid(state and state.tainted and Fluid.TaintedWater or Fluid.Water, amount)
    return fc
end

MELensDrinkFromTank = ISBaseTimedAction:derive("MELensDrinkFromTank")

function MELensDrinkFromTank:isValid()
    local state = U().waterState(self.vehicle)
    return inCamper(self.character, self.vehicle) and state ~= nil and state.water > 0
end

function MELensDrinkFromTank:start()
    self:setActionAnim("drink_tap")
    self:setOverrideHandModels(nil, nil)
    self.sound = self.character:playSound("DrinkingFromTap")
end

MELensDrinkFromTank.stopSound = MELensRefuelGenerator.stopSound

function MELensDrinkFromTank:stop()
    self:stopSound()
    ISBaseTimedAction.stop(self)
end

function MELensDrinkFromTank:perform()
    self:stopSound()
    ISBaseTimedAction.perform(self)
end

function MELensDrinkFromTank:complete()
    if not self:isValid() then return false end
    local state = U().waterState(self.vehicle)
    if not state then return false end
    local amount = math.min(self.character:getStats():get(CharacterStat.THIRST) * 2, state.water)
    if amount <= 0 then return true end
    local fc = tankFluid(self.vehicle, amount)
    U().changeWater(self.vehicle, -amount)
    self.character:DrinkFluid(fc, 1)
    FluidContainer.DisposeContainer(fc)
    return true
end

function MELensDrinkFromTank:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    local state = U().waterState(self.vehicle)
    local amount = math.min(self.character:getStats():get(CharacterStat.THIRST) * 2, state and state.water or 0)
    return amount * 100 + 15
end

function MELensDrinkFromTank:new(character, vehicle)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

MELensFillFromTank = ISBaseTimedAction:derive("MELensFillFromTank")

function MELensFillFromTank:isValid()
    local state = U().waterState(self.vehicle)
    local fc = self.item and self.item:getFluidContainer()
    return inCamper(self.character, self.vehicle) and state ~= nil and state.water > 0 and fc ~= nil and not fc:isFull()
        and self.character:getInventory():contains(self.item)
end

function MELensFillFromTank:update()
    self.item:setJobDelta(self:getJobDelta())
end

function MELensFillFromTank:start()
    self.item:setJobType(getText("ContextMenu_Fill") .. self.item:getName())
    self.item:setJobDelta(0.0)
    self:setAnimVariable("PourType", self.item:getPourType())
    self:setActionAnim("fill_container_tap")
    self:setOverrideHandModels(self.item:getStaticModel(), nil)
    self.sound = self.character:playSound(self.item:getFillFromTapSound() or "GetWaterFromTap")
end

MELensFillFromTank.stopSound = MELensRefuelGenerator.stopSound
MELensFillFromTank.stop = MELensRefuelGenerator.stop
MELensFillFromTank.perform = MELensRefuelGenerator.perform

function MELensFillFromTank:complete()
    if not self:isValid() then return false end
    local state = U().waterState(self.vehicle)
    local fc = self.item:getFluidContainer()
    if not state or not fc then return false end
    local fluid = state.tainted and Fluid.TaintedWater or Fluid.Water
    if not fc:canAddFluid(fluid) then return false end
    local amount = math.min(fc:getFreeCapacity(), state.water)
    if amount <= 0 then return false end
    fc:addFluid(fluid, amount)
    U().changeWater(self.vehicle, -amount)
    self.item:syncItemFields()
    sendItemStats(self.item)
    return true
end

function MELensFillFromTank:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    local state = U().waterState(self.vehicle)
    local fc = self.item and self.item:getFluidContainer()
    local amount = (state and fc) and math.min(fc:getFreeCapacity(), state.water) or 1
    return amount * 100 + 30
end

function MELensFillFromTank:new(character, vehicle, item)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.item = item
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

MELensWashFromTank = ISBaseTimedAction:derive("MELensWashFromTank")
MELensWashFromTank.WATER_PER_PART = 0.5   -- litres for each dirty or bloody body part

function MELensWashFromTank:isValid()
    local state = U().waterState(self.vehicle)
    return inCamper(self.character, self.vehicle) and state ~= nil and state.water >= MELensWashFromTank.WATER_PER_PART
end

function MELensWashFromTank:start()
    self:setActionAnim("WashFace")
    self:setOverrideHandModels(nil, nil)
    self.character:reportEvent("EventWashClothing")
end

MELensWashFromTank.stopSound = MELensRefuelGenerator.stopSound

function MELensWashFromTank:stop()
    self:stopSound()
    ISBaseTimedAction.stop(self)
end

function MELensWashFromTank:perform()
    self:stopSound()
    self.character:resetModelNextFrame()
    ISBaseTimedAction.perform(self)
end

function MELensWashFromTank:animEvent(event, parameter)
    if event == "PlayWashSound" then
        self:stopSound()
        self.sound = self.character:playSound("WashYourself")
    end
end

function MELensWashFromTank:complete()
    if not self:isValid() then return false end
    local state = U().waterState(self.vehicle)
    if not state then return false end
    local visual = self.character:getHumanVisual()
    local used = 0
    for i = 1, BloodBodyPartType.MAX:index() do
        if used + MELensWashFromTank.WATER_PER_PART > state.water then break end
        local part = BloodBodyPartType.FromIndex(i - 1)
        if visual:getBlood(part) + visual:getDirt(part) > 0 then
            visual:setBlood(part, 0)
            visual:setDirt(part, 0)
            used = used + MELensWashFromTank.WATER_PER_PART
        end
    end
    sendHumanVisual(self.character)
    U().changeWater(self.vehicle, -used)
    return true
end

function MELensWashFromTank:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return math.max(1, ISWashYourself.GetRequiredWater(self.character)) * 126
end

function MELensWashFromTank:new(character, vehicle)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.stopOnWalk = false
    o.forceProgressBar = true
    o.maxTime = o:getDuration()
    return o
end

------------------------------------------------------------------------------------
-- Furniture: place an item at a spot, pick a piece up
------------------------------------------------------------------------------------

MELensPlaceFurniture = ISBaseTimedAction:derive("MELensPlaceFurniture")

function MELensPlaceFurniture:isValid()
    local spot, profile = P().spotOf(self.vehicle, self.part)
    local piece = P().pieceOfItem(self.item)
    return inCamper(self.character, self.vehicle) and self.part:getInventoryItem() == nil
        and self.character:getInventory():contains(self.item) and P().fits(spot, piece)
        and P().placeTest(self.vehicle, self.part, self.character)    -- a stacked box needs the one below
        and P().roomFor(profile, P().standing(self.vehicle, profile), P().spotIndex(self.part), piece)
end

function MELensPlaceFurniture:update()
    self.item:setJobDelta(self:getJobDelta())
    self.character:setMetabolicTarget(Metabolics.MediumWork)
end

function MELensPlaceFurniture:start()
    self.item:setJobType(getText("ContextMenu_MELens_Place", self.item:getDisplayName()))
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Low")
end

MELensPlaceFurniture.stopSound = MELensRefuelGenerator.stopSound
MELensPlaceFurniture.stop = MELensRefuelGenerator.stop

function MELensPlaceFurniture:perform()
    self:stopSound()
    self.item:setJobDelta(0.0)
    local pdata = getPlayerData(self.character:getPlayerNum())
    if pdata then
        pdata.playerInventory:refreshBackpacks()
        pdata.lootInventory:refreshBackpacks()
    end
    ISBaseTimedAction.perform(self)
end

function MELensPlaceFurniture:complete()
    if not self:isValid() then return false end
    if self.part:getInventoryItem() then return false end
    if not P().placeTest(self.vehicle, self.part, self.character) then return false end
    self.character:removeFromHands(self.item)
    self.character:getInventory():Remove(self.item)
    sendRemoveItemFromContainer(self.character:getInventory(), self.item)
    self.part:setInventoryItem(self.item)
    P().applyPiece(self.vehicle, self.part)
    self.vehicle:transmitPartItem(self.part)
    -- nothing is left buried under it (what lay on the floor there, what lay on a box that has another on it now)
    local moved = MELens.Loose.displace(self.vehicle, P().spotIndex(self.part))
    if moved then
        U().transmit(self.vehicle, moved)
    end
    return true
end

function MELensPlaceFurniture:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return 150
end

function MELensPlaceFurniture:new(character, vehicle, part, item)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.part = part
    o.item = item
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

MELensPickUpFurniture = ISBaseTimedAction:derive("MELensPickUpFurniture")

function MELensPickUpFurniture:isValid()
    return inCamper(self.character, self.vehicle) and P().pickUpTest(self.vehicle, self.part, self.character)
end

function MELensPickUpFurniture:update()
    self.character:setMetabolicTarget(Metabolics.MediumWork)
end

function MELensPickUpFurniture:start()
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Low")
end

function MELensPickUpFurniture:perform()
    local pdata = getPlayerData(self.character:getPlayerNum())
    if pdata then
        pdata.playerInventory:refreshBackpacks()
        pdata.lootInventory:refreshBackpacks()
    end
    ISBaseTimedAction.perform(self)
end

function MELensPickUpFurniture:complete()
    -- Another player may fill the box, stack on it or take it during this action.
    -- Revalidate on the authority before changing either the part or the inventory.
    if not self:isValid() then return false end
    local item = self.part:getInventoryItem()
    if not item then return false end
    local container = self.part:getItemContainer()
    if container and not container:isEmpty() then return false end
    self.part:setInventoryItem(nil)
    P().applyPiece(self.vehicle, self.part)
    self.vehicle:transmitPartItem(self.part)
    self.character:getInventory():AddItem(item)
    sendAddItemToContainer(self.character:getInventory(), item)
    return true
end

function MELensPickUpFurniture:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return 120
end

function MELensPickUpFurniture:new(character, vehicle, part)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.part = part
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

------------------------------------------------------------------------------------
-- Loose items (MELens_Loose.lua): place and drop (one action), grab, turn
------------------------------------------------------------------------------------

local function Lo() return MELens.Loose end

MELens.Parts.LOOSE_REACH = 1.6      -- tiles between you and a loose item for the actions below

-- Whether the character is near enough to a point of the vehicle's inside to reach it.
function MELens.Parts.reachesLoose(character, vehicle, x, z)
    local cx, cz = MELens.Parts.characterAt(vehicle, character)
    if not cx then return false end
    local r = MELens.Parts.LOOSE_REACH
    return (cx - x) ^ 2 + (cz - z) ^ 2 <= r * r
end
local reaches = MELens.Parts.reachesLoose

-- The item is carried (the character's inventory; on a client the object may be another copy, so by number).
local function carried(character, item)
    if isClient() and item then
        return character:getInventory():containsID(item:getID())
    end
    return character:getInventory():contains(item)
end

local function refreshWindows(character)
    local pdata = getPlayerData(character:getPlayerNum())
    if pdata then
        pdata.playerInventory:refreshBackpacks()
        pdata.lootInventory:refreshBackpacks()
    end
end

MELensPlaceLoose = ISBaseTimedAction:derive("MELensPlaceLoose")

function MELensPlaceLoose:isValid()
    local floor = Lo().floorContainer(self.vehicle)
    if not inCamper(self.character, self.vehicle) or not floor or not self.item then return false end
    local x, _, z = Lo().checked(self.vehicle, self.x, self.y, self.z, self.r, self.s)
    if not x then return false end                 -- not a place a vehicle has (or has any more)
    if not reaches(self.character, self.vehicle, x, z) then return false end
    if self.item:getContainer() == floor then
        return true        -- moving what lies there
    end
    return carried(self.character, self.item) and floor:hasRoomFor(self.character, self.item)
end

function MELensPlaceLoose:update()
    self.item:setJobDelta(self:getJobDelta())
end

function MELensPlaceLoose:start()
    self.item:setJobType(getText("IGUI_JobType_Dropping"))
    self.item:setJobDelta(0.0)
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Low")
    local sound = self.item:getPlaceOneSound() or "PutItemInBag"
    if not self.character:getEmitter():isPlaying(sound) then
        self.sound = self.character:playSound(sound)
    end
end

MELensPlaceLoose.stopSound = MELensRefuelGenerator.stopSound

function MELensPlaceLoose:stop()
    self:stopSound()
    self.item:setJobDelta(0.0)
    ISBaseTimedAction.stop(self)
end

function MELensPlaceLoose:perform()
    self.item:setJobDelta(0.0)
    refreshWindows(self.character)
    ISBaseTimedAction.perform(self)
end

-- A lit candle or lantern goes out when it is put down, as the game does on the ground.
local function snuff(character, item)
    local unlit
    if item:getType() == "CandleLit" then
        unlit = "Base.Candle"
    elseif item:getType() == "Lantern_HurricaneLit" then
        unlit = "Base.Lantern_Hurricane"
    end
    if not unlit then return item end
    local other = instanceItem(unlit)
    if not other then return item end
    local inventory = item:getContainer() or character:getInventory()
    inventory:AddItem(other)
    other:setUsedDelta(item:getCurrentUsesFloat())
    other:setCondition(item:getCondition())
    other:setFavorite(item:isFavorite())
    sendAddItemToContainer(inventory, other)
    inventory:Remove(item)
    sendRemoveItemFromContainer(inventory, item)
    return other
end

function MELensPlaceLoose:complete()
    if not self:isValid() then return false end
    local floor = Lo().floorContainer(self.vehicle)
    if not floor then return false end
    local x, y, z, r, s = Lo().checked(self.vehicle, self.x, self.y, self.z, self.r, self.s)
    if not x then return false end
    local item = self.item
    if item:getContainer() ~= floor then
        if not floor:hasRoomFor(self.character, item) then return false end
        item = snuff(self.character, item)
        local source = item:getContainer()
        self.character:removeFromHands(item)
        if source then
            source:Remove(item)
            sendRemoveItemFromContainer(source, item)
        end
        floor:AddItem(item)
        sendAddItemToContainer(floor, item)
    end
    local part = Lo().set(self.vehicle, item, x, y, z, r, s)
    if part then
        U().transmit(self.vehicle, part)
    end
    return true
end

function MELensPlaceLoose:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    local time = 50
    local weight = self.item:getActualWeight()
    if weight > 3 then weight = 3 end
    time = math.max(8, time * weight * 0.1)
    if self.character:hasTrait(CharacterTrait.DEXTROUS) then
        time = time * 0.5
    end
    if self.character:hasTrait(CharacterTrait.ALL_THUMBS) or self.character:isWearingAwkwardGloves() then
        time = time * 2.0
    end
    return time
end

-- (x, y, z) the place in passenger space, r the turn in degrees, s what it stands on (MELens_Loose.lua).
function MELensPlaceLoose:new(character, vehicle, item, x, y, z, r, s)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.item = item
    o.x, o.y, o.z, o.r, o.s = x, y, z, r, s
    o.stopOnWalk = false
    o.stopOnRun = false
    o.maxTime = o:getDuration()
    return o
end

MELensGrabLoose = ISBaseTimedAction:derive("MELensGrabLoose")

function MELensGrabLoose:isValid()
    if not inCamper(self.character, self.vehicle) then return false end
    local floor = Lo().floorContainer(self.vehicle)
    if not floor then return false end
    local entry = Lo().entry(self.vehicle, self.itemId)
    if entry and not reaches(self.character, self.vehicle, entry.x, entry.z) then return false end
    local item = floor:getItemById(self.itemId)
    if item then
        return self.character:getInventory():hasRoomFor(self.character, item)
    end
    -- a client may not hold the Floor's items yet: the position says it is there
    return isClient() and Lo().entry(self.vehicle, self.itemId) ~= nil
end

function MELensGrabLoose:start()
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Low")
    self.character:reportEvent("EventLootItem")
end

function MELensGrabLoose:perform()
    refreshWindows(self.character)
    ISBaseTimedAction.perform(self)
end

function MELensGrabLoose:complete()
    if not self:isValid() then return false end
    local floor = Lo().floorContainer(self.vehicle)
    local item = floor and floor:getItemById(self.itemId)
    if not item then
        -- gone already: forget where it lay
        local part = Lo().remove(self.vehicle, self.itemId)
        if part then U().transmit(self.vehicle, part) end
        return false
    end
    local inventory = self.character:getInventory()
    if not inventory:hasRoomFor(self.character, item) then return false end
    floor:Remove(item)
    sendRemoveItemFromContainer(floor, item)
    inventory:AddItem(item)
    sendAddItemToContainer(inventory, item)
    local part = Lo().remove(self.vehicle, self.itemId)
    if part then
        U().transmit(self.vehicle, part)
    end
    return true
end

function MELensGrabLoose:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    local time = 20 + 8 * math.min(self.weight or 1, 3)
    if self.character:hasTrait(CharacterTrait.DEXTROUS) then
        time = time * 0.5
    end
    return time
end

function MELensGrabLoose:new(character, vehicle, itemId, weight)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.itemId = itemId
    o.weight = weight
    o.stopOnWalk = false
    o.stopOnRun = false
    o.maxTime = o:getDuration()
    return o
end

MELensTurnLoose = ISBaseTimedAction:derive("MELensTurnLoose")

function MELensTurnLoose:isValid()
    if not inCamper(self.character, self.vehicle) then return false end
    if Lo().entry(self.vehicle, self.itemId) ~= nil then return true end
    -- an item with no record of its place (put in the Floor through the loot window): turning it records one
    local floor = Lo().floorContainer(self.vehicle)
    return floor ~= nil and floor:getItemById(self.itemId) ~= nil
end

function MELensTurnLoose:start()
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Low")
end

function MELensTurnLoose:complete()
    if not self:isValid() then return false end
    local entry = Lo().adopt(self.vehicle, self.itemId)
    if not entry then return false end
    entry.r = ((entry.r or 0) + self.degrees) % 360
    local part = Lo().floorPart(self.vehicle)
    if part then
        U().transmit(self.vehicle, part)
    end
    return true
end

function MELensTurnLoose:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return 12
end

function MELensTurnLoose:new(character, vehicle, itemId, degrees)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.itemId = itemId
    o.degrees = degrees
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

------------------------------------------------------------------------------------
-- Home (MELens_Home.lua): a name, paint on the walls, washing clothes at the tap
------------------------------------------------------------------------------------

local function Ho() return MELens.Home end

MELensRename = ISBaseTimedAction:derive("MELensRename")

function MELensRename:isValid()
    return atCamper(self.character, self.vehicle)
end

function MELensRename:start()
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Mid")
end

function MELensRename:complete()
    if not self:isValid() then return false end
    Ho().setName(self.vehicle, self.name)
    return true
end

function MELensRename:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return 30
end

function MELensRename:new(character, vehicle, name)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.name = name
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

MELensPaintWalls = ISBaseTimedAction:derive("MELensPaintWalls")

function MELensPaintWalls:isValid()
    if not self.character then return false end
    if not inCamper(self.character, self.vehicle) then return false end
    if self.r == nil then return self.g == nil and self.b == nil end -- stripping needs nothing
    if not carried(self.character, self.can) or not carried(self.character, self.brush)
            or not Ho().isBrush(self.brush) or self.can:getCurrentUses() < Ho().PAINT_USES then return false end
    -- The shared vanilla palette is also available on the server. A carried
    -- drainable item and arbitrary client RGB values are not a can of paint.
    for _, value in ipairs({ self.r, self.g, self.b }) do
        if type(value) ~= "number" or value ~= value or value < 0 or value > 1 then return false end
    end
    if self.g == nil or self.b == nil then return false end
    for _, entry in ipairs(Ho().paints()) do
        if self.can:getType() == entry.paint and entry.color
                and math.abs(self.r - entry.color[1]) < 0.00001
                and math.abs(self.g - entry.color[2]) < 0.00001
                and math.abs(self.b - entry.color[3]) < 0.00001 then return true end
    end
    return false
end

function MELensPaintWalls:start()
    self:setActionAnim("Painting")
    if self.can then
        self:setOverrideHandModels(self.brush, self.can)
    end
    self.sound = self.character:playSound("Painting")
end

MELensPaintWalls.stopSound = MELensRefuelGenerator.stopSound

function MELensPaintWalls:stop()
    self:stopSound()
    ISBaseTimedAction.stop(self)
end

function MELensPaintWalls:perform()
    self:stopSound()
    ISBaseTimedAction.perform(self)
end

function MELensPaintWalls:complete()
    if not self:isValid() then return false end
    if self.r ~= nil then
        for _ = 1, Ho().PAINT_USES do
            self.can:UseAndSync()
        end
    end
    Ho().setPaint(self.vehicle, self.r, self.g, self.b)
    return true
end

function MELensPaintWalls:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return self.r == nil and 120 or 400
end

-- r g b: the colour (0..1), or nothing to strip the paint. can and brush are the paint and the brush used.
function MELensPaintWalls:new(character, vehicle, can, brush, r, g, b)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.can = can
    o.brush = brush
    o.r, o.g, o.b = r, g, b
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

-- Washing clothes, bags and bandages at a tap, with the water of the tank and your soap (the work of the game's
-- ISWashClothing, whose sink here is the tank).
MELensWashClothing = ISBaseTimedAction:derive("MELensWashClothing")

function MELensWashClothing.canWash(item)
    if not item then return false end
    if instanceof(item, "Clothing") then
        return item:getDirtiness() > 0 or ISWashClothing.GetRequiredSoap(item) > 0
    elseif instanceof(item, "InventoryContainer") then
        return ISWashClothing.GetRequiredSoap(item) > 0
    end
    -- Generic dirty bandages/rags have no blood field; the native cleaning recipe replaces them.
    local cleanType = item:getItemAfterCleaning()
    return (cleanType ~= nil and cleanType ~= "") or item:getBloodLevel() > 0
end

function MELensWashClothing:isValid()
    local state = U().waterState(self.vehicle)
    return atCamper(self.character, self.vehicle) and state ~= nil
        and MELensWashClothing.canWash(self.item)
        and state.water >= ISWashClothing.GetRequiredWater(self.item) and carried(self.character, self.item)
end

function MELensWashClothing:update()
    self.item:setJobDelta(self:getJobDelta())
    self.character:setMetabolicTarget(Metabolics.HeavyDomestic)
end

function MELensWashClothing:start()
    self:setActionAnim("ScrubClothWithSoap")
    local soap = getScriptManager():FindItem("Soap2")
    local cloth = getScriptManager():FindItem("DishCloth")
    if soap and cloth then
        self:setOverrideHandModels(soap:getStaticModel(), cloth:getStaticModel())
    end
    self.character:reportEvent("EventWashClothing")
    self.sound = self.character:playSound("WashClothing")
end

MELensWashClothing.stopSound = MELensRefuelGenerator.stopSound

function MELensWashClothing:stop()
    self:stopSound()
    self.item:setJobDelta(0.0)
    ISBaseTimedAction.stop(self)
end

function MELensWashClothing:perform()
    self:stopSound()
    self.item:setJobDelta(0.0)
    self.character:resetModel()
    triggerEvent("OnClothingUpdated", self.character)
    ISBaseTimedAction.perform(self)
end

function MELensWashClothing:complete()
    if not self:isValid() then return false end
    local item = self.item
    local water = ISWashClothing.GetRequiredWater(item)
    local replacement
    if not instanceof(item, "Clothing") and not instanceof(item, "InventoryContainer")
            and item:getItemAfterCleaning() then
        -- As with vanilla cleaning, a replaced item must still be in the main
        -- inventory that receives its clean replacement, not another container.
        if item:getContainer() ~= self.character:getInventory() then return false end
        replacement = instanceItem(item:getItemAfterCleaning())
        if not replacement then return false end
        replacement:setFavorite(item:isFavorite())
    end
    local soaps = self.character:getInventory():getSoapList(nil, true)
    local function useSoap(part)
        local blood = part and item:getBlood(part) or item:getBloodLevel()
        if blood <= 0 then return end
        for i = 0, soaps:size() - 1 do
            local soap = soaps:get(i)
            if soap:hasComponent(ComponentType.FluidContainer) and soap:getFluidContainer():getAmount() > 0 then
                local left = soap:getFluidContainer():getAmount() - ZomboidGlobals.CleanStainCleaningFluidAmount
                if left <= 0.001 then soap:getFluidContainer():Empty() else soap:getFluidContainer():adjustAmount(left) end
                sendItemStats(soap)
                return
            elseif not soap:hasComponent(ComponentType.FluidContainer) and soap:getCurrentUses() > 0 then
                soap:UseAndSync()
                return
            end
        end
    end
    if instanceof(item, "Clothing") or instanceof(item, "InventoryContainer") then
        local parts = BloodClothingType.getCoveredParts(item:getBloodClothingType())
        if parts then
            for i = 0, parts:size() - 1 do
                if not self.noSoap then useSoap(parts:get(i)) end
                item:setBlood(parts:get(i), 0)
                item:setDirt(parts:get(i), 0)
            end
        end
        if instanceof(item, "Clothing") then
            item:setWetness(100)
            item:setDirtiness(0)
        end
    elseif replacement then
        local inventory = self.character:getInventory()
        self.character:removeFromHands(item)
        inventory:Remove(item)
        sendRemoveItemFromContainer(inventory, item)
        inventory:AddItem(replacement)
        sendAddItemToContainer(inventory, replacement)
    else
        if not self.noSoap then useSoap(nil) end
    end
    item:setBloodLevel(0)
    if not replacement then syncItemFields(self.character, item) end
    syncVisuals(self.character)
    self.character:updateHandEquips()
    U().changeWater(self.vehicle, -water)
    return true
end

function MELensWashClothing:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return math.min(500, math.max(80, ((self.blood or 0) + (self.dirt or 0)) * 15))
end

------------------------------------------------------------------------------------
-- Put the gas of a propane tank into the vehicle: the stove and the heater burn it
------------------------------------------------------------------------------------

MELensInsertPropane = ISBaseTimedAction:derive("MELensInsertPropane")

function MELensInsertPropane:isValid()
    return atCamper(self.character, self.vehicle) and U().propaneOn()
        and U().propaneLevel(self.vehicle) < U().PROPANE_CAPACITY - 0.001
        and self.character:getInventory():contains(self.item) and MELens.Parts.propaneIn(self.item) > 0
end

function MELensInsertPropane:update()
    self.item:setJobDelta(self:getJobDelta())
end

function MELensInsertPropane:start()
    self.item:setJobType(getText("ContextMenu_Insert_Propane_Tank"))
    self.item:setJobDelta(0.0)
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Low")
    self:setOverrideHandModels(nil, nil)
    self.sound = self.character:playSound("BBQPropaneTankInsert")
end

MELensInsertPropane.stopSound = MELensRefuelGenerator.stopSound

function MELensInsertPropane:stop()
    self:stopSound()
    self.item:setJobDelta(0.0)
    ISBaseTimedAction.stop(self)
end

function MELensInsertPropane:perform()
    self:stopSound()
    self.item:setJobDelta(0.0)
    ISBaseTimedAction.perform(self)
end

function MELensInsertPropane:complete()
    if not self:isValid() then return false end
    local u = U()
    if not u.propaneOn() then return false end
    local have = MELens.Parts.propaneIn(self.item)
    local take = math.min(have, u.PROPANE_CAPACITY - u.propaneLevel(self.vehicle))
    if take <= 0 then return false end
    u.addPropane(self.vehicle, take)
    self.item:setUsedDelta(math.max(0, have - take))
    self.item:syncItemFields()
    return true
end

function MELensInsertPropane:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return 100
end

function MELensInsertPropane:new(character, vehicle, item)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.item = item
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

-- blood and dirt: how much of each the item has (the time it takes); noSoap: wash without soap.
function MELensWashClothing:new(character, vehicle, item, blood, dirt, noSoap)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.item = item
    o.blood = blood
    o.dirt = dirt
    o.noSoap = noSoap
    o.stopOnWalk = false
    o.forceProgressBar = true
    o.maxTime = o:getDuration()
    return o
end

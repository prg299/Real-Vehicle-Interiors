--
-- ME: LENS: timed actions for animals inside (MELens_Animals.lua): putting a carried animal down inside and picking
-- one up. Shared, with the work in complete(), so the server does it in multiplayer (the game rebuilds an action
-- there from the fields named like the arguments of new()). The animal goes into and out of the vehicle's own
-- animal list with the game's own trailer calls and messages, as the game's trailer actions do.
--
require "TimedActions/ISBaseTimedAction"
require "MELens_Animals"
require "MELens_Loose"

local function A() return MELens.Animals end

local function refreshWindows(character)
    local pdata = getPlayerData(character:getPlayerNum())
    if pdata then
        pdata.playerInventory:refreshBackpacks()
        pdata.lootInventory:refreshBackpacks()
    end
end

-- The carried animal of an item, when it is alive.
local function liveAnimal(item)
    local animal = item and instanceof(item, "AnimalInventoryItem") and item:getAnimal() or nil
    return animal and A().alive(animal) and animal or nil
end

------------------------------------------------------------------------------------
-- Putting an animal down inside
------------------------------------------------------------------------------------

MELensDropAnimal = ISBaseTimedAction:derive("MELensDropAnimal")

function MELensDropAnimal:isValid()
    local animal = liveAnimal(self.item)
    return animal ~= nil and A().inside(self.character) == self.vehicle
        and self.character:getInventory():containsID(self.item:getID())
        and A().fits(self.vehicle, animal)
end

function MELensDropAnimal:start()
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Low")
    local animal = liveAnimal(self.item)
    if animal then
        self.sound = animal:playBreedSound("put_down")
    end
end

function MELensDropAnimal:stop()
    if self.sound then self.character:stopOrTriggerSound(self.sound) end
    ISBaseTimedAction.stop(self)
end

function MELensDropAnimal:perform()
    if self.sound then self.character:stopOrTriggerSound(self.sound) end
    refreshWindows(self.character)
    ISBaseTimedAction.perform(self)
end

function MELensDropAnimal:complete()
    local inventory = self.character:getInventory()
    -- Re-resolve committed inventory at completion; a queued/stale item object
    -- is not authority to add another animal after the item was transferred.
    local item = self.item and inventory:getItemWithID(self.item:getID())
    local animal = liveAnimal(item)
    local vehicle = self.vehicle
    local _, profile = A().inside(self.character)
    if not animal or not profile or A().inside(self.character) ~= vehicle or not A().fits(vehicle, animal) then
        return false
    end
    local px, pz = MELens.Parts.characterAt(vehicle, self.character)
    if not px then return false end
    local x, z = tonumber(self.x), tonumber(self.z)
    if not x or not z or x ~= x or z ~= z or (x-px)^2+(z-pz)^2 > 1.5^2 then x, z = px, pz end
    -- Floor/furniture/occupancy may have changed since the client chose a point.
    -- Reject a full interior without consuming its carried animal.
    x, z = A().freePoint(vehicle, profile, x, z, tostring(animal:getAnimalID()), {{x=px,z=pz}}, true)
    if not x then return false end
    vehicle:updateParts()
    vehicle:addAnimalFromHandsInTrailer(animal, self.character)
    if isServer() then sendAddAnimalFromHandsInTrailer(animal, self.character, vehicle) end
    local facing = tonumber(self.f) or 0
    if facing ~= facing or math.abs(facing) == math.huge then facing = 0 end
    A().place(vehicle, animal, x, z, facing, "idle")
    vehicle:transmitModData()
    return true
end

function MELensDropAnimal:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return 30
end

function MELensDropAnimal:new(character, vehicle, item, x, z, f)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.item = item
    o.x = x
    o.z = z
    o.f = f
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

------------------------------------------------------------------------------------
-- Picking an animal up inside
------------------------------------------------------------------------------------

MELensPickUpAnimal = ISBaseTimedAction:derive("MELensPickUpAnimal")

function MELensPickUpAnimal:animal()
    local animal = self.vehicle and self.vehicle:getAnimalById(tonumber(self.animalId) or -1)
    return animal and A().alive(animal) and animal or nil
end

function MELensPickUpAnimal:isValid()
    local animal = self:animal()
    return A().inside(self.character) == self.vehicle and animal ~= nil and A().canPickUp(animal)
end

function MELensPickUpAnimal:start()
    self:setActionAnim("Loot")
    self:setAnimVariable("LootPosition", "Low")
    local animal = self:animal()
    if animal then
        self.sound = animal:playBreedSound("pick_up")
    end
end

function MELensPickUpAnimal:stop()
    if self.sound then self.character:stopOrTriggerSound(self.sound) end
    ISBaseTimedAction.stop(self)
end

function MELensPickUpAnimal:perform()
    if self.sound then self.character:stopOrTriggerSound(self.sound) end
    refreshWindows(self.character)
    ISBaseTimedAction.perform(self)
end

-- The game's trailer Grab (ISRemoveAnimalFromTrailer): out of the list as a new animal at the way out, into an
-- item, out of the world again; the modData goes along (Companion Dogs keeps its dog's record there).
function MELensPickUpAnimal:complete()
    local vehicle = self.vehicle
    local animal = self:animal()
    if not self:isValid() then return false end
    local record = A().record(vehicle, animal)
    local x, z = MELens.Parts.characterAt(vehicle, self.character)
    if not record or not x or (record.x-x)^2+(record.z-z)^2 > 1.5^2 then return false end
    local data = {}
    for k, v in pairs(animal:getModData()) do data[k] = v end
    local fresh = vehicle:removeAnimalFromTrailer(animal)
    if not fresh or not instanceof(fresh, "IsoAnimal") then return false end
    local md = fresh:getModData()
    for k, v in pairs(data) do md[k] = v end
    local item = instanceItem("Base.Animal")
    item:setAnimal(fresh)
    self.character:getInventory():AddItem(item)
    fresh:removeFromWorld()
    fresh:removeFromSquare()
    fresh:setSquare(nil)
    forceDropHeavyItems(self.character)
    self.character:setPrimaryHandItem(nil)
    self.character:setSecondaryHandItem(nil)
    self.character:setPrimaryHandItem(item)
    self.character:setSecondaryHandItem(item)
    if isServer() then
        sendRemoveAndGrabAnimalFromTrailer(fresh, self.character, vehicle, item)
    end
    local records = A().records(vehicle, false)
    if records then
        records[tostring(self.animalId)] = nil
        vehicle:transmitModData()
    end
    return true
end

function MELensPickUpAnimal:getDuration()
    if self.character:isTimedActionInstant() then return 1 end
    return 40
end

function MELensPickUpAnimal:new(character, vehicle, animalId)
    local o = ISBaseTimedAction.new(self, character)
    o.vehicle = vehicle
    o.animalId = animalId
    o.stopOnWalk = false
    o.maxTime = o:getDuration()
    return o
end

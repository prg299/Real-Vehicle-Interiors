-- Developer test driver for animals inside (MELens_Animals.lua). MODE is replaced by the caller (dev\animals_test.ps1):
--   give:<type>       an animal of that type (first breed of its definition) in the player's arms
--   drop              the menu's Drop for the animal carried (the player must be inside)
--   state             "<animals inside> carried=<n> | id x z pose hunger thirst ..."
--   hungry / thirsty  the first animal inside at 0.6 hunger / thirst
--   food:<itemType>   that item on the floor 0.6 tiles from the first animal (a recorded place, as a dropped item)
--   water             a pet water dish with a quarter litre of water on the floor 0.6 tiles from the first animal
--   bowl:<food|water> a Companion Dogs bowl with 50 points of food or water there
--   minute            the server's look at the animals once (MELens.Animals.onMinute)
--   pickup            Pick up for the first animal inside (walks there, the action)
--   floor             what lies on the floor: "<type> <amount>" each
local MODE = "MODE"
local player = getPlayer()
local vehicle = player:getVehicle()
local A, L = MELens.Animals, MELens.Loose
local profile = vehicle and MELens.profileFor(vehicle)

local function first()
    return A.list(vehicle)[1]
end

local function nearFirst()
    local animal = first()
    local r = animal and A.record(vehicle, animal)
    if not r then return nil end
    return A.freePoint(vehicle, profile, r.x + 0.6, r.z, "none")
end

local function onFloor(item)
    local x, z = nearFirst()
    if not x then return "no animal inside" end
    local floor = L.floorContainer(vehicle)
    floor:AddItem(item)
    L.set(vehicle, item, x, profile.floorY, z, 0, 0)
    return string.format("%s at %.2f,%.2f", item:getFullType(), x, z)
end

local kind, arg = string.match(MODE, "^(%a+):?(.*)$")

if kind == "give" then
    local defs = AnimalDefinitions.animals[arg]
    if not defs then return "no definition " .. arg end
    local breed
    for name in pairs(defs.breeds or {}) do breed = breed or name end
    local animal = IsoAnimal.new(getCell(), math.floor(player:getX()), math.floor(player:getY()), 0, arg, breed)
    animal:setWild(false)
    local item = instanceItem("Base.Animal")
    item:setAnimal(animal)
    animal:removeFromWorld()
    animal:removeFromSquare()
    animal:setSquare(nil)
    player:getInventory():AddItem(item)
    player:setPrimaryHandItem(item)
    player:setSecondaryHandItem(item)
    return "carrying " .. arg .. " (" .. tostring(breed) .. ") id " .. animal:getAnimalID()
end

if not profile then return "not inside a vehicle ME: LENS knows" end

if kind == "drop" then
    local item = player:getInventory():getFirstTypeRecurse("Animal")
    if not item then return "nothing carried" end
    ISInventoryPaneContextMenu.dropItem(item, player:getPlayerNum())
    return "dropping " .. item:getDisplayName()
elseif kind == "state" then
    local out = { tostring(#A.list(vehicle)) .. " carried=" .. player:getInventory():getCountTypeRecurse("Animal") }
    for _, animal in ipairs(A.list(vehicle)) do
        local r = A.record(vehicle, animal)
        out[#out + 1] = string.format("%s %s x=%s z=%s %s hunger=%.2f thirst=%.2f", animal:getAnimalType(), animal:getAnimalID(),
            r and string.format("%.2f", r.x) or "?", r and string.format("%.2f", r.z) or "?", r and tostring(r.p) or "?",
            animal:getStats():get(CharacterStat.HUNGER), animal:getStats():get(CharacterStat.THIRST))
    end
    return table.concat(out, " | ")
elseif kind == "hungry" or kind == "thirsty" then
    local animal = first()
    if not animal then return "no animal inside" end
    animal:getStats():set(kind == "hungry" and CharacterStat.HUNGER or CharacterStat.THIRST, 0.6)
    return kind
elseif kind == "food" then
    return onFloor(instanceItem(arg))
elseif kind == "water" then
    local dish = instanceItem("Base.WaterDish")
    dish:getFluidContainer():addFluid(Fluid.Water, 0.25)
    return onFloor(dish)
elseif kind == "bowl" then
    local bowl = instanceItem("Base.CompanionDogsBowl")
    if not bowl then return "no Companion Dogs bowl" end
    if arg == "water" then bowl:getModData().cdWater = 50 else bowl:getModData().cdFoodMeals = 50 end
    if CompanionDogs and CompanionDogs.refreshDishModel then CompanionDogs.refreshDishModel(bowl, true) end
    return onFloor(bowl)
elseif kind == "minute" then
    A.onMinute()
    return "looked"
elseif kind == "pickup" then
    local animal = first()
    if not animal then return "no animal inside" end
    local r = A.record(vehicle, animal)
    local hit = { animal = animal, entry = { x = r.x, z = r.z } }
    local context = ISContextMenu.get(0, 100, 100)
    MELens.AnimalsUI.menu(player, vehicle, profile, hit, context)
    local chosen
    for _, option in ipairs(context.options or {}) do
        local sub = option.subOption and context:getSubMenu(option.subOption)
        for _, o in ipairs(sub and sub.options or {}) do
            if o.name == getText("ContextMenu_PickUpAnimalBody") then chosen = o end
        end
    end
    context:setVisible(false)
    if not chosen then return "no Pick up option" end
    if chosen.notAvailable then return "Pick up is off" end
    chosen.onSelect(chosen.target, chosen.param1, chosen.param2)
    return "picking up " .. animal:getAnimalType()
elseif kind == "floor" then
    local floor = L.floorContainer(vehicle)
    local out = {}
    for i = 0, floor:getItems():size() - 1 do
        local item = floor:getItems():get(i)
        local fc = item:getFluidContainer()
        local md = item:getModData()
        out[#out + 1] = item:getFullType() .. (fc and string.format(" %.3fL", fc:getAmount()) or "")
            .. (md.cdFoodMeals and (" meals=" .. tostring(md.cdFoodMeals)) or "") .. (md.cdWater and (" water=" .. tostring(md.cdWater)) or "")
            .. (instanceof(item, "DrainableComboItem") and string.format(" uses=%.2f", item:getCurrentUsesFloat()) or "")
    end
    return #out .. ": " .. table.concat(out, ", ")
end
return "unknown mode " .. MODE

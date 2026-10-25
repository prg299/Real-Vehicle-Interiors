--
-- ME: LENS: animals inside. An animal put down inside lives in the vehicle's own animal list, as
-- in a livestock trailer: the game saves it with the vehicle, sends it to the players and updates it every tick at
-- the vehicle's position (it ages, gets hungry and thirsty and rides along). Where it stands inside and what it is
-- doing is ME: LENS' part: the vehicle's modData MELensAnimals (one record per animal, by its animal id), written here
-- on the server (or in single player) and drawn by the Java part in the vehicle you are in
-- (client/MELens_AnimalsUI.lua). Hungry or thirsty, an animal walks to what stands on the floor and eats or drinks:
-- food its diet takes, a Companion Dogs bowl's stock, water in any container. Companion Dogs' dogs follow their
-- owner in and out.
--
require "MELens_Profiles"
require "MELens_Parts"
require "MELens_Loose"

MELens = MELens or {}
local M = MELens
M.Animals = M.Animals or {}
local A = M.Animals
local P = M.Parts
local L = M.Loose

A.KEY = "MELensAnimals"
A.ROOM = 300             -- trailer size of the animals one vehicle takes (a hen 30, a dog 50, a rabbit 90, a calf 120)
A.SPACING = 0.4          -- tiles between two animals' middles when one is put down or walks somewhere
A.BOWL_GAP = 0.3         -- tiles between an animal's middle and the thing it eats or drinks from
A.WANDER = 0.6           -- short occasional movement in a confined interior
A.REST_MINUTES = 20      -- minimum quiet time between voluntary movements
A.REST_JITTER = 20       -- extra game minutes, per animal, to avoid a shared pacing rhythm
A.DOOR_REACH = 3.5       -- tiles between a Companion Dogs dog and the way in for it to follow its owner in
A.FEED_MINUTES = 3       -- game minutes an animal spends at a bowl
A.RESTORE = 0.5          -- the most hunger or thirst one meal or drink takes away (a dog's bowl: Companion Dogs' sandbox)
A.WATER_PER_THIRST = 0.5 -- litres drunk per 1.0 of thirst (a quarter litre per drink, as Companion Dogs' dogs drink)

------------------------------------------------------------------------------------
-- Which vehicles, which animals
------------------------------------------------------------------------------------

local function reconcileCarried(vehicle, animals)
    if not isClient() or not animals or animals:size() == 0 then return end
    local records = vehicle:getModData()[A.KEY]
    if type(records) ~= "table" then return end -- no authoritative interior snapshot yet
    local players = getOnlinePlayers()
    local held = {}
    for i = 0, players:size() - 1 do
        local player = players:get(i)
        for _, item in pairs({ player:getPrimaryHandItem(), player:getSecondaryHandItem() }) do
            if item and instanceof(item, "AnimalInventoryItem") then
                local animal = item:getAnimal()
                if animal then held[tostring(animal:getAnimalID())] = animal end
            end
        end
    end
    local changed = false
    for i = animals:size() - 1, 0, -1 do
        local animal = animals:get(i)
        local id = tostring(animal:getAnimalID())
        local carried = held[id]
        -- A restored trailer can retain the carried instance after the native
        -- pickup packet. Require both authoritative removal and a replicated
        -- held animal; never infer removal from a missing record alone.
        if carried and not records[id] then
            animals:remove(animal)
            if animal:getVehicle() == vehicle then animal:setVehicle(nil) end
            if carried:getVehicle() == vehicle then carried:setVehicle(nil) end
            changed = true
        end
    end
    if changed then
        local size = 0
        for i = 0, animals:size() - 1 do size = size + animals:get(i):getAnimalTrailerSize() end
        vehicle:setCurrentTotalAnimalSize(size)
    end
end

-- The animals inside a vehicle ME: LENS knows (a Lua list), or {}.
function A.list(vehicle)
    local out = {}
    if not vehicle or not M.profileFor(vehicle) then return out end
    local animals = vehicle:getAnimals()
    reconcileCarried(vehicle, animals)
    for i = 0, (animals and animals:size() or 0) - 1 do
        local animal = animals:get(i)
        if animal then out[#out + 1] = animal end
    end
    return out
end

function A.alive(animal)
    return animal ~= nil and not animal:isDead() and animal:getHealth() > 0
end

function A.canPickUp(animal, player)
    local defs = AnimalDefinitions and AnimalDefinitions.animals
    local def = animal and defs and defs[animal:getAnimalType()]
    local CD = CompanionDogs
    if CD and CD.isDog and CD.isDog(animal) and CD.isCompanion and CD.isCompanion(animal)
            and CD.isOwnedBy and (not player or not CD.isOwnedBy(animal, player)) then return false end
    if not A.alive(animal) then return false end
    if player and type(animal.canBePicked) == "function" then return animal:canBePicked(player) end
    return not def or def.canBePicked ~= false
end

-- The vehicle and profile a player is inside (standing, or on a bed or seat inside), not in its cab or at its wheel.
function A.inside(player)
    local vehicle = player and player:getVehicle()
    local profile = vehicle and M.profileFor(vehicle)
    if not profile then return nil end
    local seat = vehicle:getSeat(player)
    if seat < 0 then return nil end
    local passenger = vehicle:getScript():getPassenger(seat)
    local id = passenger and passenger:getId()
    for _, vid in ipairs(profile.vanillaSeats or {}) do
        if vid == id then return nil end
    end
    return vehicle, profile
end

-- The trailer size the animals inside take, and whether one more fits.
function A.roomUsed(vehicle)
    local used = 0
    for _, animal in ipairs(A.list(vehicle)) do
        used = used + animal:getAnimalTrailerSize()
    end
    return used
end

function A.fits(vehicle, animal)
    return A.roomUsed(vehicle) + animal:getAnimalTrailerSize() <= A.ROOM
end

-- What the animal's definition says (AnimalDefinitions, the game's Lua tables).
local function definition(animal)
    local defs = AnimalDefinitions and AnimalDefinitions.animals
    return defs and defs[animal:getAnimalType()] or nil
end

function A.trigger(animal)
    local CD = CompanionDogs
    if CD and CD.isDog and CD.isDog(animal) and CD.troughFeedTrigger then
        return CD.troughFeedTrigger(CD.getOwnerPlayer and CD.getOwnerPlayer(animal) or nil)
    end
    local def = definition(animal)
    return def and tonumber(def.thirstHungerTrigger) or 0.1
end

------------------------------------------------------------------------------------
-- Records: where each animal stands inside and what it does
--   { x, z = where it stands (passenger space), f = facing (radians, as the standing player's),
--     p = "idle" | "lie" | "eat" | "drink", u = until when (world hours) it keeps eating or drinking }
------------------------------------------------------------------------------------

local function key(animal)
    return tostring(animal:getAnimalID())
end

function A.records(vehicle, create)
    local data = vehicle:getModData()
    local records = data[A.KEY]
    if records == nil and create then
        records = {}
        data[A.KEY] = records
    end
    return records
end

function A.record(vehicle, animal)
    local records = A.records(vehicle, false)
    return records and records[key(animal)] or nil
end

function A.nearAnimal(vehicle, animal, player, reach)
    if A.inside(player) ~= vehicle or not A.alive(animal) then return false end
    local record = A.record(vehicle, animal)
    local x, z = P.characterAt(vehicle, player)
    return record ~= nil and x ~= nil and (record.x-x)^2+(record.z-z)^2 <= (reach or 1.5)^2
end

local function now()
    return getGameTime():getWorldAgeHours()
end

local function facingTo(dx, dz)
    return math.atan2(-dx, dz)
end

-- A free place on the floor nearest to (x, z): where nothing stands and no other animal is (nor any of the
-- points in avoid: { { x, z }, ... }, e.g. where a player stands).
function A.freePoint(vehicle, profile, x, z, except, avoid, strict)
    local taken = {}
    local records = A.records(vehicle, false) or {}
    for k, r in pairs(records) do
        if k ~= except and type(r) == "table" and r.x and r.z then taken[#taken + 1] = r end
    end
    for _, r in ipairs(avoid or {}) do taken[#taken + 1] = r end
    local best, bestD
    for _, p in ipairs(L.floorPoints(vehicle, profile)) do
        local ok = true
        for _, r in ipairs(taken) do
            if (r.x - p[1]) ^ 2 + (r.z - p[2]) ^ 2 < A.SPACING * A.SPACING then ok = false break end
        end
        if ok then
            local d = (p[1] - x) ^ 2 + (p[2] - z) ^ 2
            if not bestD or d < bestD then best, bestD = p, d end
        end
    end
    if best then return best[1], best[2] end
    if strict then return nil end
    return x, z
end

-- A short interior step must be clear for its whole length, not just at its
-- destination. Reuse the same room/furniture geometry as placed floor items.
-- This is deliberately bounded local movement, rather than outside-world AI.
function A.clearStep(vehicle, profile, x0, z0, x1, z1)
    local dx, dz = x1 - x0, z1 - z0
    local count = math.max(1, math.ceil(math.sqrt(dx * dx + dz * dz) / 0.08))
    local floor = { kind = "floor", s = 0, y = profile.floorY }
    for i = 0, count do
        local t = i / count
        if not L.fitsSurface(vehicle, profile, floor, x0 + dx * t, z0 + dz * t, 0.1, 0.1) then return false end
    end
    return true
end

-- Puts an animal at a place inside (server or single player); the caller transmits the vehicle's modData.
function A.place(vehicle, animal, x, z, f, pose)
    local records = A.records(vehicle, true)
    local r = records[key(animal)] or {}
    r.x, r.z = x, z
    r.f = f or r.f or 0
    r.p = pose or "idle"
    r.u = nil
    r.nextMove = now() + (A.REST_MINUTES + ZombRand(A.REST_JITTER + 1)) / 60
    records[key(animal)] = r
    return r
end

------------------------------------------------------------------------------------
-- Food and water on the floor
------------------------------------------------------------------------------------

local function companionDogs()
    local CD = CompanionDogs
    return CD and CD.isDog and CD or nil
end

-- Trailer passengers are absent from Companion Dogs' world registry, including
-- its ordinary upkeep/in-play sweep. Keep continuity only for loaded interiors;
-- use its own care rules rather than a second hunger/health implementation.
local dogCare = setmetatable({}, { __mode = "k" })

local function wrapDogCare(CD)
    if not CD or type(CD.wasInPlay) ~= "function" or CD.meLensCareWrapped then return end
    local previous = CD.wasInPlay
    CD.wasInPlay = function(animal)
        local vehicle = animal and animal:getVehicle()
        if vehicle and M.profileFor(vehicle) then
            local cell = getCell()
            local vehicles = cell and cell:getVehicles()
            local state = dogCare[animal]
            return vehicles ~= nil and vehicles:contains(vehicle) and state ~= nil
                and state.vehicle == vehicle and state.continuing == true
        end
        return previous(animal)
    end
    CD.meLensCareWrapped = true
end

local function careDog(vehicle, animal)
    local CD = companionDogs()
    if not CD or not CD.isCompanion or not CD.isDog(animal) or not CD.isCompanion(animal)
            or type(CD.updateUpkeep) ~= "function" or type(CD.data) ~= "function" then return end
    if CD.upkeepEnabled and not CD.upkeepEnabled() then return end
    wrapDogCare(CD)
    local state = dogCare[animal]
    if not state or state.vehicle ~= vehicle then
        state = { vehicle = vehicle, continuing = false }
        dogCare[animal] = state
    end
    local owner = CD.getOwnerPlayer and CD.getOwnerPlayer(animal) or nil
    local data = CD.data(animal)
    -- The first loaded pass refreshes CD's clock without charging unloaded time.
    if not state.continuing then data.lastUpkeepMin = CD.worldMinutes() end
    CD.updateUpkeep(animal, owner, data)
    state.continuing = true
end

function A.isDogsBowl(item)
    local CD = companionDogs()
    if not item then return false end
    if CD and CD.isDishType then
        local ok, yes = pcall(CD.isDishType, item:getFullType())
        if ok then return yes == true end
    end
    return item:getFullType() == "Base.CompanionDogsBowl"
end

-- Whether an animal eats this item (its diet: AnimalDefinitions' eatTypeTrough; a Companion dog: the dog mod's own
-- rule for food in a trough).
function A.eats(animal, item)
    if not instanceof(item, "Food") and not instanceof(item, "DrainableComboItem") then return false end
    if instanceof(item, "Food") and (item:isRotten() or item:isBurnt()) then return false end
    local CD = companionDogs()
    if CD and CD.isDog(animal) and CD.isTroughFood then
        local ok, yes = pcall(CD.isTroughFood, item, CD.getBreed and CD.getBreed(animal) or nil)
        if ok then return yes == true end
    end
    local def = definition(animal)
    local list = def and def.eatTypeTrough
    if type(list) ~= "string" then return false end
    local foodType = instanceof(item, "Food") and item:getFoodType() or nil
    local feedType = item:getAnimalFeedType()
    for word in string.gmatch(list, "[^,%s]+") do
        if word == "All" and instanceof(item, "Food") then return true end
        if word == foodType or word == feedType then return true end
    end
    return false
end

-- Litres of water in an item's fluid container (water or tainted water: animals drink from puddles too).
function A.waterIn(item)
    local fc = item and item:getFluidContainer()
    if not fc or fc:isEmpty() or item:isSealed() then return 0 end
    -- water, tainted water or a mix of the two (a dish found in the world often holds both), nothing else in it
    if fc:getRatioForFluid(Fluid.Water) + fc:getRatioForFluid(Fluid.TaintedWater) < 0.999 then return 0 end
    return fc:getAmount()
end

local function stock(item, kind)
    local md = item:getModData()
    if kind == "water" then return tonumber(md.cdWater) or 0 end
    return tonumber(md.cdFoodMeals) or 0
end

-- What lies on the floor that the animal could eat or drink from ("food" or "water"), nearest first:
-- { item, entry, kind = "food" | "water", bowl = true for a Companion Dogs bowl }.
function A.sources(vehicle, profile, animal, want, fromX, fromZ)
    local floor = L.floorContainer(vehicle)
    if not floor then return {} end
    local CD = companionDogs()
    local dog = CD and CD.isDog(animal) == true
    local out = {}
    for _, e in ipairs(L.list(vehicle, profile)) do
        if (e.s or 0) == 0 then
            local item = floor:getItemById(e.id)
            if item then
                local found = false
                if A.isDogsBowl(item) then
                    -- Companion Dogs' bowls feed its dogs, as outside
                    -- The player's normal sink/bottle filling stores real
                    -- fluid. CD normally credits that during world placement;
                    -- our floor placement needs the same conversion here.
                    if dog and not isClient() and CD.absorbRealWater and CD.absorbRealWater(item) then
                        if CD.refreshDishModel then CD.refreshDishModel(item) end
                    end
                    found = dog and stock(item, want) > 0
                    if found then out[#out + 1] = { item = item, entry = e, kind = want, bowl = true } end
                elseif want == "water" then
                    found = A.waterIn(item) > 0.01
                    if found then out[#out + 1] = { item = item, entry = e, kind = want } end
                elseif A.eats(animal, item) then
                    out[#out + 1] = { item = item, entry = e, kind = want }
                end
            end
        end
    end
    table.sort(out, function(a, b)
        return (a.entry.x - fromX) ^ 2 + (a.entry.z - fromZ) ^ 2 < (b.entry.x - fromX) ^ 2 + (b.entry.z - fromZ) ^ 2
    end)
    return out
end

local function stat(animal, which)
    local CD = companionDogs()
    -- CD keeps hunger separately while its armed-dog protection clears the
    -- native stat. Use the same accessor as its normal feeding/upkeep code.
    if which == CharacterStat.HUNGER and CD and CD.isDog(animal) and type(CD.getHunger) == "function" then
        return CD.getHunger(animal)
    end
    return animal:getStats():get(which)
end

local function setStat(animal, which, value)
    animal:getStats():set(which, math.max(0, value))
end

-- Server: the clients get an item on the floor again as it is now (its water, a bowl's stock, what is left of food).
-- The game sends an item's changed fields only for a player's inventory or the ground (syncItemFields,
-- sendItemStats), and a client ignores an item sent to a container that already has its id: so it goes out and back
-- in, with the same id (the floor's recorded places are by id). Nothing when it was eaten up and is gone.
local function resend(item)
    local container = item:getContainer()
    if not container or not container:containsID(item:getID()) then return end
    sendRemoveItemFromContainer(container, item)
    sendAddItemToContainer(container, item)
end

-- Calls a Companion Dogs function when it has it (another version may not); nil when it has not or it failed.
local function cd(name, ...)
    local CD = companionDogs()
    local fn = CD and CD[name]
    if type(fn) ~= "function" then return nil end
    local ok, a, b = pcall(fn, ...)
    if ok then return a, b end
    return nil
end

-- A need of a Companion Dogs dog: through its own CD.setNeed (it keeps a copy while the dog holds a gun), or the stat.
local function setNeed(animal, kind, value)
    local CD = companionDogs()
    value = math.max(0, value)
    if CD and type(CD.setNeed) == "function" and pcall(CD.setNeed, animal, kind, value) then return end
    setStat(animal, kind == "thirst" and CharacterStat.THIRST or CharacterStat.HUNGER, value)
end

-- A Companion Dogs dog at one of its bowls, as Companion Dogs' own feeding does it outside (CompanionDogs_Feed.lua):
-- its portion (the sandbox's trough restore), the bowl's points (1.0 thirst = DISH_POINTS_PER_THIRST, 1.0 hunger =
-- 100), its need through CD.setNeed, the vet's roll for tainted water and for a food allergy, a protein meal noted,
-- a little calmer. True when something was taken.
local function atBowl(animal, item, kind)
    local CD = companionDogs()
    local md = item:getModData()
    local d = cd("data", animal)
    local perThirst = CD and tonumber(CD.DISH_POINTS_PER_THIRST) or 50
    if kind == "water" then
        local thirst = stat(animal, CharacterStat.THIRST)
        local take = math.min(cd("troughThirstRestore") or A.RESTORE, thirst, stock(item, "water") / perThirst)
        if take <= 0 then return false end
        setNeed(animal, "thirst", thirst - take)
        md.cdWater = math.max(0, (tonumber(md.cdWater) or 0) - take * perThirst)
        if d then cd("vetRollDishWater", animal, d, md) end
    else
        local hunger = stat(animal, CharacterStat.HUNGER)
        local take = math.min(cd("troughHungerRestore") or A.RESTORE, hunger, stock(item, "food") / 100)
        if take <= 0 then return false end
        setNeed(animal, "hunger", hunger - take)
        local points = take * 100
        md.cdFoodMeals = math.max(0, (tonumber(md.cdFoodMeals) or 0) - points)
        local meat = tonumber(md.cdFoodMeat) or 0
        local fromMeat, group = 0, nil
        if meat > 0 then
            fromMeat = math.min(meat, points)
            group = md.cdFoodProtein
            md.cdFoodMeat = meat - fromMeat
            if md.cdFoodMeat <= 0 then md.cdFoodProtein = nil end
        end
        if d and fromMeat > 0 then cd("markProteinMeal", d, fromMeat) end
        cd("vetRollFoodAllergy", animal, group)
    end
    cd("refreshDishModel", item)
    cd("addCombatStress", animal, -0.2)
    if d then d.lastTroughEatMin = cd("worldMinutes") or d.lastTroughEatMin end
    cd("transmit", animal)
    return true
end

-- Drinking or eating one portion from a source; true when something was taken.
local function consume(animal, source)
    local item = source.item
    if source.bowl then
        if not atBowl(animal, item, source.kind) then return false end
    elseif source.kind == "water" then
        local thirst = stat(animal, CharacterStat.THIRST)
        local take = math.min(A.RESTORE, thirst, A.waterIn(item) / A.WATER_PER_THIRST)
        if take <= 0 then return false end
        item:getFluidContainer():removeFluid(take * A.WATER_PER_THIRST)
        setStat(animal, CharacterStat.THIRST, thirst - take)
    else
        -- the game's own eating: what is left of the item, what it turns into, the players told
        animal:getData():eatItem(item, false)
    end
    if isServer() then
        resend(item)
    end
    return true
end

------------------------------------------------------------------------------------
-- The server's look at the animals inside (single player too), every game minute
------------------------------------------------------------------------------------

-- Where the animal stands to eat or drink from something at (x, z): beside it, on the side it comes from.
local function besidePoint(vehicle, profile, animal, r, x, z)
    local dx, dz = r.x - x, r.z - z
    local len = math.sqrt(dx * dx + dz * dz)
    -- Already beside this bowl: do not shuffle to another sampled floor point
    -- for every small remaining drink or portion of food.
    if len <= A.BOWL_GAP + 0.15 then return r.x, r.z, facingTo(-dx, -dz) end
    if len < 0.01 then dx, dz, len = 0, -1, 1 end
    local bx, bz = x + dx / len * A.BOWL_GAP, z + dz / len * A.BOWL_GAP
    if not L.fitsSurface(vehicle, profile, { kind = "floor", s = 0, y = profile.floorY }, bx, bz, 0.08, 0.08) then
        bx, bz = A.freePoint(vehicle, profile, bx, bz, key(animal))
    end
    if not A.clearStep(vehicle, profile, r.x, r.z, bx, bz) then return nil end
    return bx, bz, facingTo(x - bx, z - bz)
end

-- One animal: back from a meal, then thirst first, then hunger, else now and then a few steps or a rest.
-- True when its record changed.
local function look(vehicle, profile, animal, r, hours)
    if r.u and hours < r.u then return false end
    local changed = false
    if r.p == "eat" or r.p == "drink" then
        r.p, r.u = "idle", nil
        changed = true
    end
    -- thirst first; a thirsty animal with nothing to drink still eats
    local trigger = A.trigger(animal)
    local needs = {}
    if stat(animal, CharacterStat.THIRST) >= trigger then needs[#needs + 1] = "water" end
    if stat(animal, CharacterStat.HUNGER) >= trigger then needs[#needs + 1] = "food" end
    for _, wants in ipairs(needs) do
        for _, source in ipairs(A.sources(vehicle, profile, animal, wants, r.x, r.z)) do
            local bx, bz, f = besidePoint(vehicle, profile, animal, r, source.entry.x, source.entry.z)
            if bx and consume(animal, source) then
                r.x, r.z, r.f = bx, bz, f
                r.p = wants == "water" and "drink" or "eat"
                r.u = hours + A.FEED_MINUTES / 60
                r.nextMove = r.u + (A.REST_MINUTES + ZombRand(A.REST_JITTER + 1)) / 60
                if not source.bowl and source.kind == "food" then
                    -- an item eaten up leaves the floor: so does its recorded place
                    local part = L.prune(vehicle)
                    if part then vehicle:transmitPartModData(part) end
                end
                return true
            end
        end
    end
    -- Stay still allows necessary feeding/drinking, like CD's outside care,
    -- but must not resume our unrelated voluntary wandering when a timer expires.
    local CD = companionDogs()
    if CD and CD.isDog(animal) and CD.isCompanion and CD.isCompanion(animal)
            and CD.getState and CD.getState(animal) == (CD.STATE_STAY or "stay") then return changed end
    -- Needs can interrupt a rest, but a satisfied animal mostly stays settled.
    -- A missing timer on an old record starts a quiet interval on first load.
    if not r.nextMove then
        r.nextMove = hours + (A.REST_MINUTES + ZombRand(A.REST_JITTER + 1)) / 60
        return true
    end
    if hours < r.nextMove then return changed end
    r.nextMove = hours + (A.REST_MINUTES + ZombRand(A.REST_JITTER + 1)) / 60
    local roll = ZombRand(4)
    if roll == 0 then
        local tx, tz = r.x + ZombRandFloat(-A.WANDER, A.WANDER), r.z + ZombRandFloat(-A.WANDER, A.WANDER)
        local nx, nz = A.freePoint(vehicle, profile, tx, tz, key(animal))
        if (nx - r.x) ^ 2 + (nz - r.z) ^ 2 > 0.04 and A.clearStep(vehicle, profile, r.x, r.z, nx, nz) then
            r.f = facingTo(nx - r.x, nz - r.z)
            r.x, r.z, r.p = nx, nz, "idle"
            return true
        end
    elseif roll == 1 then
        r.p = r.p == "lie" and "idle" or "lie"
        return true
    end
    return true -- persist the new quiet interval even when it chose to stay still
end

-- Records for animals that have none (put in some other way: the game's trailer menu, Companion Dogs), none for
-- animals that left; then each one's look. True when the records changed.
function A.updateVehicle(vehicle, profile)
    local animals = A.list(vehicle)
    local records = A.records(vehicle, #animals > 0)
    if not records then return false end
    local changed = false
    local present = {}
    local hours = now()
    for _, animal in ipairs(animals) do
        local k = key(animal)
        present[k] = true
        local r = records[k]
        if type(r) ~= "table" or not r.x or not r.z then
            local door = profile.door or { x = 0, z = 0 }
            local x, z = A.freePoint(vehicle, profile, door.x, door.z, k)
            r = A.place(vehicle, animal, x, z, 0, "idle")
            changed = true
        end
        if A.alive(animal) then
            careDog(vehicle, animal)
            if A.alive(animal) and look(vehicle, profile, animal, r, hours) then changed = true end
            local CD = companionDogs()
            if CD and CD.isDog(animal) and CD.isCompanion and CD.isCompanion(animal) and CD.kennelSnapshot then
                local owner = CD.getOwnerPlayer and CD.getOwnerPlayer(animal)
                local data = CD.data(animal)
                local minutes = CD.worldMinutes()
                if owner and (not data.lastKennelMin or minutes-data.lastKennelMin >= (CD.KENNEL_MIRROR_MIN or 30)) then
                    data.lastKennelMin = minutes
                    CD.kennelSnapshot(owner, animal)
                end
            end
        end
    end
    local gone = {}
    for k in pairs(records) do
        if not present[k] then gone[#gone + 1] = k end
    end
    for _, k in ipairs(gone) do
        records[k] = nil
        changed = true
    end
    return changed
end

------------------------------------------------------------------------------------
-- Companion Dogs: the owner's following dogs come in and go out with them
------------------------------------------------------------------------------------

local function following(CD, dog)
    local ok, state = pcall(CD.getState, dog)
    return ok and state == CD.STATE_FOLLOW
end

-- Where the way in is, in the world (the standing place's outside position).
local function wayIn(vehicle, profile)
    local s = profile.standing
    if not s or not s.outside then return vehicle:getX(), vehicle:getY() end
    local o = vehicle:getScript():getModel():getOffset()
    local w = vehicle:getWorldPos(o:x() + s.outside[1], 0, o:z() + s.outside[3], Vector3f.new())
    return w:x(), w:y()
end

-- An owner standing inside: their following dogs that reached the way in walk in.
local function dogsIn(CD, player, vehicle, profile)
    if not CD.regCompanionsOf or not vehicle:isStopped() then return false end
    local ok, keyed, named = pcall(CD.regCompanionsOf, player)
    if not ok then return false end
    -- CD retains a username registry for companions from older saves. The same
    -- dog can occur in both registries; never board it twice.
    local dogs, seen = {}, {}
    for _, list in ipairs({ keyed or {}, named or {} }) do
        for _, dog in pairs(list) do
            if not seen[dog] then dogs[#dogs + 1], seen[dog] = dog, true end
        end
    end
    local wx, wy = wayIn(vehicle, profile)
    local changed = false
    for _, dog in pairs(dogs) do
        if type(dog) == "userdata" and instanceof(dog, "IsoAnimal") and dog:getSquare() ~= nil and dog:getVehicle() == nil
                and A.alive(dog) and following(CD, dog) and A.fits(vehicle, dog)
                and (dog:getX() - wx) ^ 2 + (dog:getY() - wy) ^ 2 <= A.DOOR_REACH * A.DOOR_REACH then
            local door = profile.door or { x = 0, z = 0 }
            local x, z = A.freePoint(vehicle, profile, door.x, door.z, key(dog), nil, true)
            if x then
                vehicle:addAnimalInTrailer(dog)
                A.place(vehicle, dog, x, z, facingTo(-door.x, -door.z), "idle")
                changed = true
            end
        end
    end
    return changed
end

-- Following dogs inside a vehicle their owner is not in: out at the way in (the game's trailer way out, which the
-- dog mod watches: it takes its dog back from there).
local function dogsOut(CD, vehicle)
    local changed = false
    for _, dog in ipairs(A.list(vehicle)) do
        if A.alive(dog) and CD.isDog(dog) and CD.isCompanion(dog) and following(CD, dog) then
            local okOwner, owner = pcall(CD.getOwnerPlayer, dog)
            if okOwner and owner and owner:getVehicle() ~= vehicle then
                local data = {}
                for k, v in pairs(dog:getModData()) do data[k] = v end
                local fresh = vehicle:removeAnimalFromTrailer(dog)
                if fresh and instanceof(fresh, "IsoAnimal") then
                    local md = fresh:getModData()
                    for k, v in pairs(data) do md[k] = v end
                    fresh:addToWorld()
                    if isServer() then sendRemoveAnimalFromTrailer(dog, owner, vehicle) end
                    local records = A.records(vehicle, false)
                    if records then records[key(dog)] = nil end
                    changed = true
                end
            end
        end
    end
    return changed
end

local function companionDogsPass(vehicles)
    local CD = companionDogs()
    if not CD or not CD.isCompanion or not CD.getState then return end
    local players = isServer() and getOnlinePlayers() or nil
    local list = {}
    if players then
        for i = 0, players:size() - 1 do list[#list + 1] = players:get(i) end
    else
        for i = 0, getNumActivePlayers() - 1 do
            local p = getSpecificPlayer(i)
            if p then list[#list + 1] = p end
        end
    end
    for _, player in ipairs(list) do
        local vehicle, profile = A.inside(player)
        if vehicle and dogsIn(CD, player, vehicle, profile) then
            vehicle:transmitModData()
        end
    end
    for _, vehicle in ipairs(vehicles) do
        local ok, changed = pcall(dogsOut, CD, vehicle)
        if not ok then
            print("[ME_LENS] animals: taking a dog out failed: " .. tostring(changed))
        elseif changed then
            -- Publish immediately when the last following dog leaves, too.
            vehicle:transmitModData()
        end
    end
end

-- Include stale records as well: another mod's Bring/extract command can remove
-- the last animal without going through our pickup or following-dog exit action.
local function withAnimalState()
    local out = {}
    local cell = getCell()
    local set = cell and cell:getVehicles()
    if not set then return out end
    local it = set:iterator()
    while it:hasNext() do
        local vehicle = it:next()
        if vehicle and M.profileFor(vehicle) then
            local records = A.records(vehicle, false)
            local saved = false
            for _ in pairs(records or {}) do saved = true; break end
            if (vehicle:getAnimals() and vehicle:getAnimals():size() > 0) or saved then
                out[#out + 1] = vehicle
            end
        end
    end
    return out
end

function A.onMinute()
    if isClient() then return end
    local vehicles = withAnimalState()
    local loaded = {}
    for _, vehicle in ipairs(vehicles) do loaded[vehicle] = true end
    for animal, state in pairs(dogCare) do
        if not loaded[state.vehicle] or animal:getVehicle() ~= state.vehicle then dogCare[animal] = nil end
    end
    local ok, err = pcall(companionDogsPass, vehicles)
    if not ok then print("[ME_LENS] animals: Companion Dogs pass failed: " .. tostring(err)) end
    for _, vehicle in ipairs(withAnimalState()) do
        local okV, changed = pcall(A.updateVehicle, vehicle, M.profileFor(vehicle))
        if not okV then
            print("[ME_LENS] animals: " .. tostring(changed))
        elseif changed then
            vehicle:transmitModData()
        end
    end
end

Events.EveryOneMinute.Add(A.onMinute)

------------------------------------------------------------------------------------
-- Companion Dogs counts anyone in a vehicle seat as "mounted": it puts the following dog away while the owner drives
-- and takes a carried dog out of the owner's arms. Standing or sitting inside is not driving: the dog stays.
------------------------------------------------------------------------------------

local function wrapCompanionDogs()
    local CD = companionDogs()
    if not CD or not CD.isMounted or CD.meLensMountedWrapped then return end
    local mounted = CD.isMounted
    CD.isMounted = function(player)
        if player and A.inside(player) then return false end
        return mounted(player)
    end
    CD.meLensMountedWrapped = true
end

------------------------------------------------------------------------------------
-- The way out for animals: the script area AnimalEntry at the standing place's way in (the game's trailer way out,
-- also what Companion Dogs uses to take its dog out of a vehicle)
------------------------------------------------------------------------------------

function A.addEntryAreas()
    local manager = getScriptManager()
    if not manager then return end
    for fullName, profile in pairs(M.Profiles or {}) do
        local script = manager:getVehicle(fullName)
        local s = profile.standing
        if script and s and s.outside then
            local area = script:getAreaById("AnimalEntry")
            if not area then
                local o = script:getModel():getOffset()
                script:Load(script:getName(), string.format("{ area AnimalEntry { xywh = %.4f %.4f 1.0 1.0, } }",
                    o:x() + s.outside[1], o:z() + s.outside[3]))
            end
        end
    end
end

local function boot()
    A.addEntryAreas()
    wrapCompanionDogs()
end

Events.OnGameBoot.Add(boot)
Events.OnInitWorld.Add(boot)
if Events.OnServerStarted then Events.OnServerStarted.Add(boot) end

--
-- ME: LENS: animals inside, the player's side (MELens_Animals.lua). A carried animal dropped while
-- you are inside (the menu's Drop, dragging it out of the inventory) is put down in front of you; right-clicking an
-- animal inside gives its name, Pick up and Info. Every tick the animals of the vehicle you are in go to the Java part
-- to be drawn: each walks from where it was shown to where the server says it stands, then idles, lies, eats or
-- drinks there.
--
require "MELens_Animals"
require "MELens_Inside"
require "MELens_LooseUI"
require "MELens_LooseView"
require "TimedActions/MELens_AnimalActions"
require "MELens_AnimalContext"

MELens = MELens or {}
local M = MELens
local A = M.Animals
local P = M.Parts
M.AnimalsUI = M.AnimalsUI or {}
local UI = M.AnimalsUI

-- Companion Dogs normally closes its status window for a trailer animal because
-- it is absent from the world. An animal sharing this player's RVI interior is
-- still present and inspectable; retain every other native close condition.
function UI.wrapDogWindow()
    local window = ISCDStatusWindow
    if not window or UI.dogWindowWrapped then return end
    local previous = window.checkShouldClose
    if type(previous) ~= "function" then return end
    window.checkShouldClose = function(self)
        local player = self.owner or getSpecificPlayer(self.playerNum or 0)
        local vehicle = A.inside(player)
        if vehicle and self.animal and not self.stashed and self.animal:getVehicle() == vehicle
                and A.alive(self.animal) and A.record(vehicle, self.animal) then return false end
        return previous(self)
    end
    UI.dogWindowWrapped = true
end
UI.wrapDogWindow()
Events.OnGameStart.Add(UI.wrapDogWindow)

-- Companion Dogs' inventory option normally uses a world-square placement
-- cursor. Inside, route that existing option to the vehicle's placement system.
function UI.bowlInventoryMenu(playerNum, context, items)
    local player = getSpecificPlayer(playerNum)
    if not player or not A.inside(player) then return end
    local actual = ISInventoryPane.getActualItems(items)
    local bowl
    for _, item in ipairs(actual or {}) do if A.isDogsBowl(item) then bowl = item;break end end
    if not bowl then return end
    for _, option in ipairs(context.options or {}) do
        if option.name == getText("IGUI_PD_PlaceDish") then
            option.target, option.param1 = player, bowl
            option.onSelect = function(actor, item) M.LooseUI.start(actor, { item }) end
            if #actual == 1 then context:removeOptionByName(getText("ContextMenu_MELens_PlaceItem")) end
            break
        end
    end
end
if not UI.bowlMenuHooked then
    UI.bowlMenuHooked = true
    -- All mods have registered their inventory entries by GameStart. Run after
    -- CD's entry builder regardless of the player's mod load order.
    Events.OnGameStart.Add(function()
        Events.OnFillInventoryObjectContextMenu.Remove(UI.bowlInventoryMenu)
        Events.OnFillInventoryObjectContextMenu.Add(UI.bowlInventoryMenu)
    end)
end

UI.SPEED = 0.7        -- tiles a second an animal walks inside
UI.TURN = 4.0         -- radians a second it turns
UI.PICK = 0.3         -- tiles round an animal's middle the mouse finds it
UI.HEIGHT = 0.55      -- how high (tiles) the mouse finds it
UI.AHEAD = 0.45       -- tiles in front of you a dropped animal is put down

local function java()
    local rv = M.java and M.java()
    if not rv then return nil end
    for _, name in ipairs({"beginAnimals", "addAnimal", "endAnimals", "clearAnimals"}) do
        if type(rv[name]) ~= "function" then return nil end
    end
    return rv
end

local function say(player, key, ...)
    HaloTextHelper.addBadText(player, getText(key, ...))
end

local function isDog(animal)
    local CD = CompanionDogs
    if not CD or not CD.isDog then return false end
    local ok, yes = pcall(CD.isDog, animal)
    return ok and yes == true
end

function UI.nameOf(animal)
    local custom = animal:getCustomName()
    if custom and custom ~= "" then return custom end
    local ok, full = pcall(function() return animal:getFullName() end)
    if ok and full and full ~= "" then return full end
    return getText("IGUI_AnimalType_" .. animal:getAnimalType())
end

------------------------------------------------------------------------------------
-- Dropping a carried animal inside
------------------------------------------------------------------------------------

-- Where you stand inside and which way you face (passenger space), standing or not.
local function standPoint(player, vehicle)
    local x, z = P.characterAt(vehicle, player)
    local f = M.facingOf and M.facingOf(player) or nil
    return x, z, f or 0
end

function UI.drop(player, vehicle, profile, item)
    if not java() then say(player, "IGUI_MELens_NoJava");return end
    local animal = item:getAnimal()
    if not animal or not A.alive(animal) then
        say(player, "IGUI_MELens_AnimalNotAlive")
        return
    end
    if not A.fits(vehicle, animal) then
        say(player, "IGUI_MELens_AnimalNoRoom")
        return
    end
    M.standingThen(player, function()
        local x, z, f = standPoint(player, vehicle)
        if not x then return end
        local ax, az = x - math.sin(f) * UI.AHEAD, z + math.cos(f) * UI.AHEAD
        -- not where you stand: the nearest free floor point ahead may be your own
        ax, az = A.freePoint(vehicle, profile, ax, az, tostring(animal:getAnimalID()), { { x = x, z = z } }, true)
        if not ax then say(player, "IGUI_MELens_AnimalNoRoom");return end
        -- it faces you
        ISTimedActionQueue.add(MELensDropAnimal:new(player, vehicle, item, ax, az, math.atan2(-(x - ax), z - az)))
    end)
end

local previousDrop = ISInventoryPaneContextMenu.dropItem

ISInventoryPaneContextMenu.dropItem = function(item, player)
    if item and instanceof(item, "AnimalInventoryItem") then
        local playerObj = getSpecificPlayer(player)
        local vehicle, profile = A.inside(playerObj)
        if vehicle and M.insideVehicle(playerObj) then
            UI.drop(playerObj, vehicle, profile, item)
            return
        end
    end
    return previousDrop(item, player)
end

------------------------------------------------------------------------------------
-- What is shown: each animal walks from where it was shown to where the server put it
------------------------------------------------------------------------------------

local shown = {}       -- animal id (string) -> { x, z, f, walking }
local shownVehicle = nil
local lastMs = nil

local function turnTowards(current, target, step)
    local d = target - current
    while d > math.pi do d = d - 2 * math.pi end
    while d < -math.pi do d = d + 2 * math.pi end
    if math.abs(d) <= step then return target end
    return current + (d > 0 and step or -step)
end

-- The animals of a vehicle as shown now: { animal, id, x, z, f, state, action }.
function UI.shown(vehicle)
    local out = {}
    if not vehicle then return out end
    local records = A.records(vehicle, false) or {}
    for _, animal in ipairs(A.list(vehicle)) do
        local id = tostring(animal:getAnimalID())
        local r = records[id]
        local s = shown[id]
        if r and r.x and r.z and s and shownVehicle == vehicle then
            out[#out + 1] = { animal = animal, id = id, x = s.x, z = s.z, f = s.f, record = r, walking = s.walking }
        elseif r and r.x and r.z then
            out[#out + 1] = { animal = animal, id = id, x = r.x, z = r.z, f = r.f or 0, record = r }
        end
    end
    return out
end

local function step(vehicle, profile, dt)
    local records = A.records(vehicle, false) or {}
    local seen = {}
    local rv = java()
    rv.beginAnimals(vehicle, profile.floorY)
    for _, animal in ipairs(A.list(vehicle)) do
        local id = tostring(animal:getAnimalID())
        local r = records[id]
        if r and r.x and r.z then
            seen[id] = true
            local s = shown[id]
            if not s then
                s = { x = r.x, z = r.z, f = r.f or 0 }
                shown[id] = s
            end
            local dx, dz = r.x - s.x, r.z - s.z
            local dist = math.sqrt(dx * dx + dz * dz)
            if dist > 3 then
                s.x, s.z, dist = r.x, r.z, 0      -- too far to walk (a reload, a long way): there at once
            end
            s.walking = dist > 0.02
            if s.walking then
                local move = math.min(dist, UI.SPEED * dt)
                s.x, s.z = s.x + dx / dist * move, s.z + dz / dist * move
                s.f = turnTowards(s.f, math.atan2(-dx, dz), UI.TURN * dt)
            else
                s.f = turnTowards(s.f, r.f or s.f, UI.TURN * dt)
            end
            local state, action = "idle", ""
            if not A.alive(animal) then
                state, action = "idle", "sit"
            elseif s.walking then
                state = "walk"
            elseif r.p == "lie" then
                action = "sit"
            elseif r.p == "eat" or r.p == "drink" then
                action = r.p
                -- the game's animals eat in the "eating" state; Companion Dogs' dogs in idle, with its own flags
                if not isDog(animal) then state = "eating" end
            end
            rv.addAnimal(animal, s.x, s.z, s.f, state, action)
        end
    end
    rv.endAnimals()
    for id in pairs(shown) do
        if not seen[id] then shown[id] = nil end
    end
end

local published = false

local function onTick()
    local rv = java()
    if not rv or not rv.beginAnimals then return end
    local now = getTimestampMs()
    local dt = lastMs and math.min(0.1, math.max(0, (now - lastMs) / 1000)) or 0
    lastMs = now
    local player = getSpecificPlayer(0)
    local vehicle, profile = nil, nil
    if player and MELensRV and M.insideVehicle then vehicle, profile = M.insideVehicle(player) end
    if not profile or vehicle:getAnimals():size() == 0 then
        if published then
            rv.clearAnimals()
            published = false
        end
        return
    end
    if shownVehicle ~= vehicle then
        shown = {}
        shownVehicle = vehicle
    end
    local ok, err = pcall(step, vehicle, profile, dt)
    if not ok then
        print("[ME_LENS] animals: showing them failed: " .. tostring(err))
    end
    published = true
end

Events.OnTick.Add(onTick)

------------------------------------------------------------------------------------
-- Pointing at an animal inside: the mouse pick (MELens_Interact.lua) and its menu
------------------------------------------------------------------------------------

local LOOK = "MELensAnimal:"      -- the stand-in type the item-name label looks up (see below)

local previousCandidates = M.LooseUI.pickCandidates

M.LooseUI.pickCandidates = function(vehicle, profile)
    local out = previousCandidates(vehicle, profile)
    for _, a in ipairs(UI.shown(vehicle)) do
        local cx, cz = a.x, a.z
        out[#out + 1] = {
            kind = "loose", animal = a.animal, animalId = a.animal:getAnimalID(),
            entry = { x = cx, z = cz, t = LOOK .. a.id, s = 0 },
            bottom = profile.floorY, top = profile.floorY + UI.HEIGHT,
            hits = function(x, z) return (x - cx) ^ 2 + (z - cz) ^ 2 <= UI.PICK * UI.PICK end,
        }
    end
    return out
end

-- The item-name label under the mouse asks for an item of the entry's type: for an animal, its name.
local previousProto = M.LooseView.proto

M.LooseView.proto = function(fullType)
    if type(fullType) == "string" and string.sub(fullType, 1, #LOOK) == LOOK then
        local id = string.sub(fullType, #LOOK + 1)
        local player = getSpecificPlayer(0)
        for _, animal in ipairs(A.list(player and player:getVehicle())) do
            if tostring(animal:getAnimalID()) == id then
                local name = UI.nameOf(animal)
                return { getDisplayName = function() return name end, getTex = function() return nil end }
            end
        end
        return nil
    end
    return previousProto(fullType)
end

function UI.menu(player, vehicle, profile, hit, context)
    local animal = hit.animal
    if not animal then return end
    return M.AnimalContext.menu(player, animal, context)
end

local previousMenu = M.LooseUI.menu

M.LooseUI.menu = function(player, vehicle, profile, hit, context)
    if hit and hit.animal then
        return UI.menu(player, vehicle, profile, hit, context)
    end
    return previousMenu(player, vehicle, profile, hit, context)
end

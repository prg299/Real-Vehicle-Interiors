-- Use the same animal-menu event as the world. Only travel and pickup differ
-- inside a moving vehicle; labels, ordering, icons and commands stay upstream.
require "MELens_Animals"
require "MELens_LooseUI"
require "TimedActions/MELens_AnimalActions"
require "ISUI/Animal/ISAnimalContextMenu"

local M, A = MELens, MELens.Animals
M.AnimalContext = M.AnimalContext or {}
local C = M.AnimalContext

function C.inside(player, animal)
    local vehicle, profile = A.inside(player)
    if vehicle and animal and animal:getVehicle() == vehicle then
        local record = A.record(vehicle, animal)
        if record then return vehicle, profile, record end
    end
end

function C.pickup(animal, player)
    local vehicle, profile = C.inside(player, animal)
    if not vehicle or not A.canPickUp(animal, player) then return end
    local id = animal:getAnimalID()
    M.standingThen(player, function()
        local _, _, record = C.inside(player, animal)
        if not record then return end
        local x, z = M.LooseUI.standFor(vehicle, profile, record.x, record.z, 0, player)
        M.walkTo(player, x, z, function()
            ISTimedActionQueue.add(MELensPickUpAnimal:new(player, vehicle, id))
        end)
    end)
end

function C.wrapPickup()
    if not AnimalContextMenu or C.pickupWrapped then return end
    local previous = AnimalContextMenu.onPickupAnimal
    AnimalContextMenu.onPickupAnimal = function(animal, player)
        if C.inside(player, animal) then return C.pickup(animal, player) end
        return previous(animal, player)
    end
    C.pickupWrapped = true
end
-- Run after Companion Dogs' ownership wrapper has been installed.
Events.OnGameStart.Add(C.wrapPickup)

local function decorate(action, player, animal)
    if action.animal ~= animal then return action end
    local valid, start, update, wait = action.isValid, action.start, action.update, action.waitToStart
    local function face()
        local _, _, record = C.inside(player, animal)
        return record and M.facePoint(player, record.x, record.z)
    end
    action.waitToStart = function(self)
        if C.inside(player, animal) then return not face() end
        return wait and wait(self) or false
    end
    action.update = function(self)
        if update then update(self) end
        face()
    end
    action.isValid = function(self)
        local vehicle = C.inside(player, animal)
        if not vehicle or not A.nearAnimal(vehicle, animal, player) then return false end
        if self.Type == "ISCDPetDog" then
            local CD = CompanionDogs
            return CD and CD.isOwnedBy(animal, player) == true
        end
        return valid(self)
    end
    action.start = function(self)
        start(self)
        face()
        if self.Type == "ISCDPetDog" then
            -- The native pet setup works for passengers too. CD's usual start
            -- skips it solely because a trailer passenger is outside the world.
            ISPetAnimal.start(self)
            local data = animal:getData()
            if data:getMaxSize() <= data:getMinSize() then player:setVariable("AnimalSizeY", 1) end
            player:setVariable("animal", animal:isBaby() and "raccoonkit"
                or animal:isFemale() and "raccoonsow" or "raccoonboar")
        elseif not animal:isExistInTheWorld() and self.handModelItem then
            self:setActionAnim(animal:getFeedByHandAnim())
            self:setOverrideHandModels(self.handModelItem, nil)
        end
    end
    if action.Type == "ISCDPetDog" then
        for _, name in ipairs({ "stop", "forceStop", "perform" }) do
            local previous = action[name]
            action[name] = function(self, ...)
                animal:clearVariable("idleAction")
                return previous(self, ...)
            end
        end
    end
    return action
end

-- Collect only the selected callback's synchronous travel/actions. Restore the
-- shared APIs before any asynchronous walking; all unrelated callbacks retain
-- their original behavior. Native actions keep their inventory/authority checks.
function C.invoke(player, animal, callback, ...)
    local vehicle, profile = C.inside(player, animal)
    if not vehicle then return callback(...) end
    local queued = {}
    local add, getUp, walk = ISTimedActionQueue.add, ISTimedActionQueue.addGetUpAndThen, luautils.walkAdj
    local function collect(action)
        if action.Type ~= "ISWalkToTimedActionF" and action.Type ~= "ISWalkToTimedAction"
                and action.Type ~= "ISPathFindAction" then queued[#queued + 1] = action end
    end
    ISTimedActionQueue.add = function(action)
        if action.character == player then collect(action) else return add(action) end
    end
    ISTimedActionQueue.addGetUpAndThen = function(actor, action)
        if actor == player then collect(action) else return getUp(actor, action) end
    end
    luautils.walkAdj = function(actor, square, ...)
        if actor == player then return true end
        return walk(actor, square, ...)
    end
    local ok, result = pcall(callback, ...)
    ISTimedActionQueue.add, ISTimedActionQueue.addGetUpAndThen, luautils.walkAdj = add, getUp, walk
    if not ok then error(result) end
    if #queued == 0 then return result end
    M.standingThen(player, function()
        local _, _, record = C.inside(player, animal)
        if not record then return end
        local x, z = M.LooseUI.standFor(vehicle, profile, record.x, record.z, 0, player, 0.65)
        M.walkTo(player, x, z, function()
            if not C.inside(player, animal) then return end
            for _, action in ipairs(queued) do add(decorate(action, player, animal)) end
        end)
    end)
    return result
end

local function adapt(menu, player, animal, first, seen)
    if seen[menu] then return end
    seen[menu] = true
    for index = first or 1, #(menu.options or {}) do
        local option = menu.options[index]
        if option.subOption then
            local sub = menu:getSubMenu(option.subOption)
            if sub then adapt(sub, player, animal, 1, seen) end
        end
        if option.onSelect then
            local callback = option.onSelect
            option.onSelect = function(...)
                if C.inside(player, animal) then return C.invoke(player, animal, callback, ...) end
            end
        end
    end
end

function C.menu(player, animal, context)
    local first = #(context.options or {}) + 1
    triggerEvent("OnClickedAnimalForContext", player:getPlayerNum(), context, { animal }, false)
    adapt(context, player, animal, first, {})
end

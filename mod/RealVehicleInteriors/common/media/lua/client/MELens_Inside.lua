--
-- ME: LENS: inside a walk-in vehicle the game should work as it does outside. The game
-- treats you as a passenger there, and a passenger cannot do a few things; this file lifts
-- those for the vehicles' insides (not for their own driver's and cab seats):
--
--   * dropping an item (the menu's Drop, or dragging it out of the inventory onto the world)
--     puts it on the vehicle's floor (the "Floor" in the loot window), where the game would
--     drop it on the ground beside the door, outside, and only with a door or window open;
--   * exercising (push-ups, sit-ups...), which the game refuses in any vehicle.
--
require "MELens_Cabin"
require "MELens_LooseUI"
require "ISUI/ISInventoryPane"
require "ISUI/ISInventoryPaneContextMenu"
require "TimedActions/ISFitnessAction"
require "ISUI/ISFitnessUI"

MELens = MELens or {}
local M = MELens

-- The vehicle and profile you are inside (walking, sitting or lying), or nil: not in a
-- vehicle, in one ME: LENS knows nothing of, or in its own driver's or cab seat.
function M.insideVehicle(player)
    local vehicle = player and player:getVehicle()
    local profile = vehicle and M.profileFor(vehicle)
    if not profile or not MELensRV then return nil end
    if M.cabinSeat(vehicle, profile) < 0 or M.inVanillaSeat(player, vehicle, profile) then return nil end
    return vehicle, profile
end

-- The vehicle's floor: a container that stays with the vehicle.
function M.floorContainer(vehicle)
    local part = vehicle and vehicle:getPartById(M.Parts.FLOOR)
    return part and part:getItemContainer() or nil
end

------------------------------------------------------------------------------------
-- Dropping
------------------------------------------------------------------------------------

local vanillaDropItem = ISInventoryPaneContextMenu.dropItem

-- The game's own steps for dropping an item (a lit candle or lantern is put out, worn and
-- held items come off), then onto the vehicle's floor instead of the world.
ISInventoryPaneContextMenu.dropItem = function(item, player)
    local playerObj = getSpecificPlayer(player)
    local vehicle = M.insideVehicle(playerObj)
    local floor = vehicle and M.floorContainer(vehicle)
    if not floor then
        return vanillaDropItem(item, player)
    end
    if "Tutorial" == getCore():getGameMode() then
        return
    end
    if item:getType() == "CandleLit" and item:isEquipped() then
        ISInventoryPaneContextMenu.litCandleExtinguish(item, player)
    end
    if (item:getType() == "Lantern_HurricaneLit" or item:hasTag(ItemTag.LIT_LANTERN)) and item:isEquipped() then
        ISInventoryPaneContextMenu.hurricaneLanternExtinguish(item, player)
    end
    playerObj:removeAttachedItem(item)
    if playerObj:isHandItem(item) then
        ISTimedActionQueue.add(ISUnequipAction:new(playerObj, item, 1, "drop"))
    else
        ISInventoryPaneContextMenu.unequipItem(item, player)
    end
    -- onto the floor where you stand, and it lies there (MELens_LooseUI.lua)
    if M.LooseUI and MELensRV then
        M.LooseUI.drop(playerObj, vehicle, M.profileFor(vehicle), item)
    else
        ISTimedActionQueue.add(ISInventoryTransferUtil.newInventoryTransferAction(playerObj, item, item:getContainer(), floor))
    end
end

-- The game greys "Drop" out in a vehicle whose door and window are shut (nothing could go
-- out of it); the floor inside takes the item, so it is always available there.
local function enableDrop(playerNum, context, items)
    if not M.insideVehicle(getSpecificPlayer(playerNum)) then return end
    local drop = getText("ContextMenu_Drop")
    for _, option in ipairs(context.options or {}) do
        if option.name == drop then
            option.notAvailable = false
            option.toolTip = nil
        end
    end
end

Events.OnFillInventoryObjectContextMenu.Add(enableDrop)

-- Dragging an item out of the inventory onto the world drops it, but in a vehicle only with
-- the passenger window open (nothing could go out of a closed one). The floor inside takes
-- it, so while the pane looks at where the drag ends, the vehicle has no window.
local vanillaPaneUpdate = ISInventoryPane.update

function ISInventoryPane:update()
    if not M.insideVehicle(getSpecificPlayer(self.player)) then
        return vanillaPaneUpdate(self)
    end
    local lookup = VehicleUtils.getChildWindow
    VehicleUtils.getChildWindow = function() return nil end
    -- an item let go over the world is dropped where the mouse is (MELens_LooseUI.lua), not at your feet
    local releasing = ISMouseDrag.dragging ~= nil and ISMouseDrag.draggingFocus == self and not isMouseButtonDown(0)
    if M.LooseUI then
        M.LooseUI.dragPoint = releasing and { x = getMouseXScaled(), y = getMouseYScaled(), n = 0 } or nil
    end
    local ok, err = pcall(vanillaPaneUpdate, self)
    if M.LooseUI then
        M.LooseUI.dragPoint = nil
    end
    VehicleUtils.getChildWindow = lookup
    if not ok then
        error(err, 0)
    end
end

------------------------------------------------------------------------------------
-- Exercise
------------------------------------------------------------------------------------

local vanillaFitnessValid = ISFitnessAction.isValid

function ISFitnessAction:isValid()
    if M.insideVehicle(self.character) then
        return true
    end
    return vanillaFitnessValid(self)
end

-- The game's rules for the exercise window's buttons, minus "you are in a vehicle".
local vanillaUpdateButtons = ISFitnessUI.updateButtons

function ISFitnessUI:updateButtons(currentAction)
    if not M.insideVehicle(self.player) then
        return vanillaUpdateButtons(self, currentAction)
    end
    self.cancel.enable = false
    self.ok.enable = true
    if currentAction and (currentAction.Type == "ISFitnessAction") and currentAction.action then
        self.cancel.enable = true
    end
    if self.player:getMoodles():getMoodleLevel(MoodleType.ENDURANCE) > ISFitnessUI.enduranceLevelThreshold then
        self.ok.enable = false
        self.ok.tooltip = getText("Tooltip_TooExhaustedFitness")
    end
    if self.player:getMoodles():getMoodleLevel(MoodleType.HEAVY_LOAD) > 2 then
        self.ok.enable = false
        self.ok.tooltip = getText("Tooltip_TooHeavyFitness")
    end
    if self.player:getVariableBoolean("sitonground") or self.player:isSittingOnFurniture() then
        self.ok.enable = false
        self.ok.tooltip = getText("Tooltip_StandStillFitness")
    end
    if self.player:getMoodles():getMoodleLevel(MoodleType.PAIN) > 3 then
        self.ok.enable = false
        self.ok.tooltip = getText("Tooltip_TooMuchPainFitness")
    end
    if self.player:isClimbing() then
        self.ok.enable = false
    end
end

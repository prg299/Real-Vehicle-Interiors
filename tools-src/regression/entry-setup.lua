-- Load the production entry actions after the other suites. World/UI/queue are
-- explicit doubles; this proves action contracts, not native input or networking.
ISVehicleMenu, ISVehicleSeatUI, ISExitVehicle = {}, {}, {}
for _, name in ipairs({ "OnGameStart", "OnMainMenuEnter", "OnFillWorldObjectContextMenu" }) do
    Events[name] = { Add = function() end }
end
function ISBaseTimedAction:perform() self.performed = (self.performed or 0) + 1 end
function ISBaseTimedAction:stop() self.stopped = (self.stopped or 0) + 1 end
function ISBaseTimedAction:forceComplete()
    self.forced = (self.forced or 0) + 1
    self:perform()
end
function getCell() return { setDrag = function() end } end
function getPlayerContextMenu() return nil end
entryEvents = {}
function triggerEvent(name, chr) entryEvents[#entryEvents + 1] = { name = name, character = chr } end

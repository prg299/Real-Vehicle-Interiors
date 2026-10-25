-- Engine doubles for focused release regressions. No world, UI input or renderer is simulated.
assertions = 0
function check(ok, message)
    assertions = assertions + 1
    assert(ok, message)
end
function require(_) end
-- A usable client bridge, with optional methods supplied by each focused double.
function completeJava(methods)
    local rv = methods or {}
    for _, name in ipairs({"setKeepPlane","bindSeatContainer","setCutaway","clearCutaway"}) do
        rv[name] = rv[name] or function() end
    end
    rv.isPartModelVisible=rv.isPartModelVisible or function() return true end
    rv.clearStalePartModels=rv.clearStalePartModels or function() return false end
    return rv
end
function getScriptManager() return nil end
function isClient() return true end
function isServer() return true end
function getOnlinePlayers() return { size = function() return 0 end } end
CharacterStat = { PANIC = "Panic" }
CharacterTrait = { AGORAPHOBIC = "Agoraphobic", CLAUSTROPHOBIC = "Claustrophobic" }
now = 1000
function getTimestampMs() return now end
Events = {}
for _, name in ipairs({ "OnGameBoot", "OnInitWorld", "OnPostDistributionMerge", "OnClientCommand", "OnServerCommand", "OnTick", "OnPlayerUpdate" }) do
    local event = { callbacks = {} }
    event.Add = function(fn) table.insert(event.callbacks, fn) end
    Events[name] = event
end
function emit(name, ...)
    for _, fn in ipairs(Events[name].callbacks) do fn(...) end
end
ISBaseTimedAction = {}
function ISBaseTimedAction:derive(_) local child = {}; setmetatable(child, { __index = self }); return child end
function ISBaseTimedAction:new(chr) local child = { character = chr }; setmetatable(child, { __index = self }); return child end
ContainerButtonIcons = {}
MELens = { Utilities = {}, Loose = {}, Home = {} }
MELens.Loose.itemsOn = function() return false end
function getText(key) return key end
Vector3f = {}
function Vector3f.new()
    local v = {}
    function v:set(x, y, z) self.xx, self.yy, self.zz = x, y, z; return self end
    function v:x() return self.xx end
    function v:y() return self.yy end
    function v:z() return self.zz end
    return v:set(0, 0, 0)
end
vehicles, players, sent, broadcasts = {}, {}, {}, {}
function getVehicleById(id) return vehicles[id] end
function getPlayerByOnlineID(id) return players[id] end
function getSpecificPlayer(_) return localPlayer end
function sendClientCommand(player, module, command, args) table.insert(sent, { player = player, args = args }) end
function sendServerCommand(module, command, args) table.insert(broadcasts, args) end
function sendAddItemToContainer(_, _) end
function character(id)
    local p = { id = id, xx = 100, yy = 100, zz = 0, vars = {}, variableWrites = {}, inventory = {} }
    function p:getOnlineID() return self.id end
    function p:isLocalPlayer() return self == localPlayer end
    function p:getVehicle() return self.vehicle end
    function p:DistToSquared(x, y) return (self.xx - x)^2 + (self.yy - y)^2 end
    function p:setX(x) self.xx = x end
    function p:setY(y) self.yy = y end
    function p:setZ(z) self.zz = z end
    function p:setVariable(k, v) self.vars[k] = v; self.variableWrites[k] = (self.variableWrites[k] or 0) + 1 end
    function p:getVariableString(k) return self.vars[k] end
    function p:getVariableBoolean(k) return self.vars[k] == true or self.vars[k] == "true" end
    function p:clearVariable(k) self.vars[k] = nil end
    function p:getInventory() return self.inventory end
    function p.inventory:AddItem(item) table.insert(self, item) end
    function p:isTimedActionInstant() return true end
    players[id] = p
    return p
end
localPlayer = character(1)

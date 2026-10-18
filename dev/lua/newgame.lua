-- Developer test driver: start a fresh sandbox world from the main menu.
-- Sent to the isolated test game through ZombieBuddy's local Lua endpoint.
local x, y = 10835, 10144 -- middle of Muldraugh, on the street
local current = ActiveMods.getById("currentGame")
current:copyFrom(ActiveMods.getById("default"))
if ActiveMods.requiresResetLua(current) then
    return "needs Lua reset for mods: restart the test game"
end
MainScreen.instance:setDefaultSandboxVars()
SandboxVars.Zombies = 6            -- none
SandboxVars.VehicleEasyUse = true
getWorld():setGameMode("Sandbox")
getWorld():setMap("Muldraugh, KY")
local worldName = "melens-test-" .. getTimestamp()
getWorld():setWorld(worldName)
selectedDebugScenario = { name = "ME LENS test", startLoc = { x = x, y = y, z = 0 } }
createWorld(worldName)
GameWindow.doRenderEvent(false)
forceChangeState(LoadingQueueState.new())
return "starting " .. worldName

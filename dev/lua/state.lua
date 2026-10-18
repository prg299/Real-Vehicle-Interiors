-- Developer test driver: report ME: LENS state.
local player = getPlayer()
local state = MELens and MELens.debugState() or { error = "MELens missing" }
state.java = MELensRV and MELensRV.status() or "MELensRV missing"
state.gameState = tostring(getGameState and getGameState() or "?")
if player then
    state.px, state.py, state.pz = player:getX(), player:getY(), player:getZ()
    state.cabinVar = player:getVariableString("MELensCabin")
    state.seatVar = player:getVariableString("MELensCabinSeat")
    state.queue = #(ISTimedActionQueue.getTimedActionQueue(player).queue or {})
end
return state

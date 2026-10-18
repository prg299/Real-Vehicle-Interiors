-- Developer test driver: walk into the spawned test camper through the normal action queue.
local player = getPlayer()
local vehicle = MELensTest and MELensTest.vehicle
if not vehicle then return "spawn a camper first" end
local ok, reason = MELens.canWalkIn(player, vehicle)
if not ok then return "cannot walk in: " .. tostring(reason) end
MELens.walkIn(player, vehicle)
return "queued " .. #ISTimedActionQueue.getTimedActionQueue(player).queue .. " actions"

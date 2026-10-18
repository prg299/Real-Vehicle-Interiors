-- Developer test driver: spawn a Flying Cloud 22 next to the player, repaired,
-- unlocked and with its key, and remember it as MELensTest.vehicle.
MELensTest = MELensTest or {}
local player = getPlayer()
if not player then return "no player" end
local sq = getCell():getGridSquare(math.floor(player:getX()) + 4, math.floor(player:getY()), 0)
if not sq then return "no square" end
local vehicle = addVehicleDebug("Base.Trailer54FlyingCloud22", IsoDirections.E, 0, sq)
if not vehicle then return "spawn failed" end
vehicle:repair()
for i = 0, vehicle:getPartCount() - 1 do
    local door = vehicle:getPartByIndex(i):getDoor()
    if door then door:setLocked(false) end
end
player:getInventory():AddItem(vehicle:createVehicleKey())
MELensTest.vehicle = vehicle
return {
    id = vehicle:getId(),
    script = vehicle:getScript():getFullName(),
    x = vehicle:getX(), y = vehicle:getY(),
    passengers = vehicle:getMaxPassengers(),
    cabinSeat = MELens and MELens.cabinSeat(vehicle) or "MELens missing",
}

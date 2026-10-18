-- Test profile only. Prepare outside the doorway; entry itself must use input.
local p, v = getPlayer(), MELensTest.vehicle
assert(p and v and not p:getVehicle(), "fixture needs a player outside the test vehicle")
MELensEntryTest = MELensEntryTest or { entered = 0, exited = 0 }
local test = MELensEntryTest
if not test.watching then
    Events.OnEnterVehicle.Add(function(player)
        if player ~= getPlayer() then return end
        test.entered = test.entered + 1
        local vehicle = player:getVehicle()
        local part = vehicle:getAllSeatParts():get(vehicle:getSeat(player))
        test.lastPart = part and part:getId() or "MISSING"
        print("[ENTRY_CHECK] enter=" .. test.entered .. " part=" .. test.lastPart)
    end)
    Events.OnExitVehicle.Add(function(player)
        if player == getPlayer() then test.exited = test.exited + 1 end
    end)
    test.watching = true
end
local seat = MELens.cabinSeat(v)
local pos = Vector3f.new()
v:getWorldPos(v:getPassengerPosition(seat, "outside"):getOffset(), pos)
p:setX(pos:x()); p:setY(pos:y()); p:setLastX(pos:x()); p:setLastY(pos:y())
p:faceLocation(v:getX(), v:getY())
local lookup = v:getAllSeatParts()
local seats = {}
for i = 0, v:getMaxPassengers() - 1 do
    local part = lookup:get(i)
    seats[tostring(i)] = {passenger = v:getScript():getPassenger(i):getId(),
                         part = part and part:getId() or "MISSING"}
end
return {seats = seats, x = p:getX(), y = p:getY(), speed = v:getCurrentSpeedKmHour(),
        enterKey = getCore():getKey("Interact"), world = getWorld():getWorld()}

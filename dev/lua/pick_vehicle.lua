-- Developer test driver: remember one of the vehicles spawn_all.lua made as
-- MELensTest.vehicle (replace NAME with its script name, e.g. "Base.87fordB700school"),
-- for walkin.lua and the other drivers.
MELensTest = MELensTest or {}
local vehicle = MELensTest.all and MELensTest.all["NAME"]
if not vehicle then return "NAME not spawned (run spawn_all.lua)" end
MELensTest.vehicle = vehicle
local profile = MELens.profileFor(vehicle)
return { id = vehicle:getId(), x = vehicle:getX(), y = vehicle:getY(), profile = profile and profile.name or "-",
         seat = MELens.cabinSeat(vehicle) }

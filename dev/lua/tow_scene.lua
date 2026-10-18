-- Developer test driver (disposable test world only): a car on the road pulling the Flying Cloud 22 behind it
-- (heading S, the camper north of the car), for a screenshot. The camper becomes MELensTest.vehicle (walk in
-- with dev/lua/walkin.lua). Needs the road found by dev/lua/find_road.lua: x 10818..10827, long along y.
MELensTest = MELensTest or {}
MELensTest.all = MELensTest.all or {}
local CAR = "Base.PickUpTruck"
local CAMPER = "Base.Trailer54FlyingCloud22"
local X, Y = 10822, 10128                  -- the camper's square; the car starts 12 tiles south of it
local p = getPlayer()
local cell = getCell()
for _, name in ipairs({ "car", "camper" }) do
    local v = MELensTest[name]
    if v then pcall(function() v:permanentlyRemove() end); MELensTest[name] = nil end
end
if MELensTest.vehicle then pcall(function() MELensTest.vehicle:permanentlyRemove() end); MELensTest.vehicle = nil end
-- zombies of earlier runs are saved with the world (hundreds can be left standing about): they hit the test character
-- into a hit reaction that blocks the walk-in
local zl = cell:getZombieList()
for i = zl:size() - 1, 0, -1 do pcall(function() zl:get(i):removeFromWorld(); zl:get(i):removeFromSquare() end) end
MELensTest.zombies = {}
-- clear the road of everything else
local list = cell:getVehicles()
local it = list:iterator()
local others = {}
while it:hasNext() do others[#others + 1] = it:next() end
for _, v in ipairs(others) do pcall(function() v:permanentlyRemove() end) end
local function at(x, y) return cell:getGridSquare(x, y, 0) end
local camper = addVehicleDebug(CAMPER, IsoDirections.S, 0, at(X, Y))
local car = addVehicleDebug(CAR, IsoDirections.S, 0, at(X, Y + 12))
if not camper or not car then return "spawn failed" end
for _, v in ipairs({ camper, car }) do
    v:repair()
    for i = 0, v:getPartCount() - 1 do
        local door = v:getPartByIndex(i):getDoor()
        if door then door:setLocked(false) end
    end
end
local ok, err = pcall(function() car:addPointConstraint(p, camper, "trailer", "trailer") end)
MELensTest.car, MELensTest.camper, MELensTest.vehicle = car, camper, camper
MELensTest.all[CAMPER] = camper
p:getInventory():AddItem(camper:createVehicleKey())
return string.format("camper %.1f,%.1f car %.1f,%.1f constraint=%s %s", camper:getX(), camper:getY(), car:getX(), car:getY(), tostring(ok), tostring(err))

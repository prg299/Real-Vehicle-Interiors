-- Developer test driver (disposable test world only): a huge horde of zombies around the test vehicles
-- (MELensTest.camper / car, else MELensTest.vehicle): about COUNT zombies scattered over the ground within RADIUS
-- tiles, none within CLEAR tiles of a vehicle's edge (a zombie right against a cut-down wall shows its head and
-- arms over it, which reads as standing inside). FREEZE = 1: they stand where they are (setUseless); else they are
-- real zombies that walk to the player. Run it again to replace.
local COUNT, RADIUS = tonumber("COUNT") or 150, tonumber("RADIUS") or 14
local CLEAR, FREEZE = tonumber("CLEAR") or 2, tonumber("FREEZE") == 1
-- BOX "x0,y0,x1,y1": scatter over that rectangle of the map instead of a ring (the loaded map ends beside the road)
local BOX = {}
for n in string.gmatch("BOXSPEC", "[%d.]+") do BOX[#BOX + 1] = tonumber(n) end
MELensTest = MELensTest or {}
for _, z in ipairs(MELensTest.zombies or {}) do pcall(function() z:removeFromWorld(); z:removeFromSquare() end) end
MELensTest.zombies = {}
local centre = MELensTest.camper or MELensTest.vehicle
local cx, cy = centre:getX(), centre:getY()
local cars = {}
for _, v in ipairs({ MELensTest.camper, MELensTest.car, MELensTest.vehicle }) do if v then cars[#cars + 1] = v end end
local function nearCar(x, y)
    for _, v in ipairs(cars) do
        local dx, dy = x - v:getX(), y - v:getY()
        -- (vehicles here face N or S: 1.8 wide across x, 5.3 long along y)
        if math.abs(dx) < 0.9 + CLEAR and math.abs(dy) < 2.7 + CLEAR then return true end
    end
    return false
end
local made, tries = 0, 0
local rng = newrandom and newrandom() or nil
while made < COUNT and tries < COUNT * 20 do
    tries = tries + 1
    local a = ZombRandFloat(0, 2 * math.pi)
    local r = 2.5 + (RADIUS - 2.5) * math.sqrt(ZombRandFloat(0, 1))
    local x, y = cx + math.cos(a) * r * 1.0, cy + math.sin(a) * r * 1.0
    if #BOX == 4 then x, y = ZombRandFloat(BOX[1], BOX[3]), ZombRandFloat(BOX[2], BOX[4]) end
    local sq = getCell():getGridSquare(math.floor(x), math.floor(y), 0)
    if sq and sq:isFree(false) and not nearCar(x, y) then
        local list = addZombiesInOutfit(x, y, 0, 1, nil, 50)
        if list and list:size() > 0 then
            local z = list:get(0)
            if FREEZE then pcall(function() z:setUseless(true) end) end
            table.insert(MELensTest.zombies, z)
            made = made + 1
        end
    end
end
return string.format("horde %d zombies (tries %d) around %.1f,%.1f", made, tries, cx, cy)

-- Developer test driver (disposable test world only): remove loose items and corpses lying on the ground within
-- 40 tiles of the test spot (MELensTest.camper, else the player), and the blood.
local start = MELensTest and MELensTest.start
local c = MELensTest and MELensTest.camper or getPlayer()
local cx, cy = math.floor(start and start.x or c:getX()), math.floor(start and start.y or c:getY())
local cell = getCell()
local items, bodies = 0, 0
for x = cx - 40, cx + 40 do
    for y = cy - 40, cy + 40 do
        local sq = cell:getGridSquare(x, y, 0)
        if sq then
            local w = sq:getWorldObjects()
            for i = w:size() - 1, 0, -1 do
                local o = w:get(i)
                pcall(function() sq:transmitRemoveItemFromSquare(o); o:removeFromWorld(); o:removeFromSquare() end)
                items = items + 1
            end
            local b = sq:getDeadBodys()
            for i = b:size() - 1, 0, -1 do
                pcall(function() sq:removeCorpse(b:get(i), false) end)
                bodies = bodies + 1
            end
            pcall(function() sq:removeBlood(false, false) end)
        end
    end
end
return string.format("removed %d items, %d corpses", items, bodies)

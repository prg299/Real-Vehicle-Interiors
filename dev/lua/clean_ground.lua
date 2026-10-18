-- Developer test driver: clear the blood splatters (and dead bodies) of the test world's ground round the test
-- spot, so the captures show the vehicle and not stains of the map. The vehicles are spawned west of
-- MELensTest.start (dev/lua/spawn_one.lua) and the camera follows the character inside one.
local s = MELensTest and MELensTest.start or { x = getPlayer():getX(), y = getPlayer():getY() }
local cell = getCell()
local squares, bodies = 0, 0
for x = math.floor(s.x) - 34, math.floor(s.x) + 8 do
    for y = math.floor(s.y) - 18, math.floor(s.y) + 18 do
        local sq = cell:getGridSquare(x, y, 0)
        if sq then
            if pcall(function() sq:removeBlood(false, false) end) then squares = squares + 1 end
            local body = sq:getDeadBody()
            if body then
                pcall(function() sq:removeCorpse(body, false) end)
                bodies = bodies + 1
            end
        end
    end
end
return "cleaned " .. squares .. " squares, " .. bodies .. " bodies"

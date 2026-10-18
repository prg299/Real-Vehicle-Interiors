-- Developer test driver (disposable test world only): remove the game's furniture tiles (fixtures_, appliances_,
-- furniture_) standing on open ground round the test spot, left by dev/lua/vanilla_by_vehicle.lua or
-- vanilla_furniture.lua (they are saved with the world and stand in every later capture).
local s = MELensTest and MELensTest.start or { x = getPlayer():getX(), y = getPlayer():getY() }
local cell = getCell()
local removed = 0
for pass = 1, 2 do
    for x = math.floor(s.x) - 30, math.floor(s.x) + 30 do
        for y = math.floor(s.y) - 14, math.floor(s.y) + 25 do
            local sq = cell:getGridSquare(x, y, 0)
            if sq and not sq:getRoom() then
                local objs = sq:getObjects()
                for i = objs:size() - 1, 1, -1 do
                    local o = objs:get(i)
                    local sp = o:getSprite() and o:getSprite():getName() or ""
                    if sp:find("^fixtures_") or sp:find("^appliances_") or sp:find("^furniture_") then
                        sq:transmitRemoveItemFromSquare(o)
                        if objs:contains(o) then o:removeFromWorld(); o:removeFromSquare() end
                        removed = removed + 1
                    end
                end
            end
        end
    end
end
if MELensTest then MELensTest.vanilla = {} end
return "removed " .. removed

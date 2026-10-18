-- Developer test driver: remember the nearest walk-in camper as MELensTest.vehicle.
MELensTest = MELensTest or {}
local player = getPlayer()
local px, py = math.floor(player:getX()), math.floor(player:getY())
local best, bestDist = nil, nil
for dx = -8, 8 do
    for dy = -8, 8 do
        local sq = getCell():getGridSquare(px + dx, py + dy, 0)
        local v = sq and sq:getVehicleContainer()
        if v and MELens.profileFor(v) then
            local d = player:DistToSquared(v:getX(), v:getY())
            if not bestDist or d < bestDist then best, bestDist = v, d end
        end
    end
end
MELensTest.vehicle = best
return best and { id = best:getId(), x = best:getX(), y = best:getY(), dist = math.sqrt(bestDist) } or "no camper near"

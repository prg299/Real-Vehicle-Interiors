-- Developer test driver: find open ground near the player for spawn_all.lua (a row of
-- vehicles east of the player, 4 tiles apart): the nearest spot where a W x H block
-- (x: -2..W-3 from the player, y: -2..H-3) has no rooms, walls, trees, water or solid
-- objects, and move the player there. Replace W and H (defaults 18 x 50). With MEADOW = 1
-- only grass with nothing on it counts (no road, so no power lines). The spot is kept as
-- MELensTest.start for dev/enter_vehicle.ps1.
local W, H = tonumber("W") or 18, tonumber("H") or 50
local MEADOW = tonumber("MEADOW") == 1
local player = getPlayer()
local cell = getCell()
local px, py = math.floor(player:getX()), math.floor(player:getY())

local function blocked(x, y)
    local sq = cell:getGridSquare(x, y, 0)
    if not sq or not sq:getFloor() then return true end
    if sq:getRoom() or sq:getTree() then return true end
    if MEADOW then
        local floor = sq:getFloor():getSprite() and sq:getFloor():getSprite():getName() or ""
        if not floor:find("^blends_natural") then return true end
        -- short grass and ground scatter are fine; bushes, plants, fences and the like are not
        for i = 1, sq:getObjects():size() - 1 do
            local o = sq:getObjects():get(i)
            local name = o:getSprite() and o:getSprite():getName() or "?"
            if not (name:find("^e_newgrass") or name:find("^blends_grassoverlays") or name:find("^d_generic")) then
                return true
            end
        end
        if sq:getVehicleContainer() then return true end
    end
    local props = sq:getProperties()
    if props:has(IsoFlagType.water) or props:has(IsoFlagType.solid) or props:has(IsoFlagType.solidtrans)
        or props:has(IsoFlagType.collideN) or props:has(IsoFlagType.collideW)
        or props:has(IsoFlagType.WallN) or props:has(IsoFlagType.WallW) then
        return true
    end
    return false
end

-- open[x][y] once, then test blocks
local R = 70
local isBlocked = {}
for x = px - R - 2, px + R + W do
    local col = {}
    for y = py - R - 2, py + R + H do
        col[y] = blocked(x, y)
    end
    isBlocked[x] = col
end

local function blockOpen(ox, oy)
    for x = ox - 2, ox + W - 3 do
        local col = isBlocked[x]
        if not col then return false end
        for y = oy - 2, oy + H - 3 do
            if col[y] ~= false then return false end
        end
    end
    return true
end

local best, bestD = nil, nil
for ox = px - R, px + R, 2 do
    for oy = py - R, py + R, 2 do
        local d = (ox - px) ^ 2 + (oy - py) ^ 2
        if (not bestD or d < bestD) and blockOpen(ox, oy) then
            best, bestD = { ox, oy }, d
        end
    end
end
if not best then return "no open " .. W .. "x" .. H .. " block within " .. R .. " tiles" end
player:setX(best[1] + 0.5)
player:setY(best[2] + 0.5)
player:setLastX(best[1] + 0.5)
player:setLastY(best[2] + 0.5)
MELensTest = MELensTest or {}
MELensTest.start = { x = best[1] + 0.5, y = best[2] + 0.5 }
return string.format("moved to %d,%d (%.0f tiles away)", best[1], best[2], math.sqrt(bestD))

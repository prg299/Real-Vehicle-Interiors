-- Developer test driver: find a straight road near the player (asphalt floor squares), as runs along x
-- and along y. Returns the longest of each with the number of parallel rows that are road too.
local cell = getCell()
local p = getPlayer()
local px, py = math.floor(p:getX()), math.floor(p:getY())
local R = 60
local function road(x, y)
    local sq = cell:getGridSquare(x, y, 0)
    if not sq or sq:getRoom() or not sq:getFloor() then return false end
    local sp = sq:getFloor():getSprite()
    local n = sp and sp:getName() or ""
    return n:find("street") ~= nil and not n:find("sidewalk")
end
local bestX, bestY = { len = 0 }, { len = 0 }
for y = py - R, py + R do
    local run, start = 0, 0
    for x = px - R, px + R + 1 do
        if x <= px + R and road(x, y) then
            if run == 0 then start = x end
            run = run + 1
        else
            if run > bestX.len then
                local rows = 0
                for dy = -3, 3 do if road(start + math.floor(run / 2), y + dy) then rows = rows + 1 end end
                if rows >= 4 then bestX = { len = run, x0 = start, y = y, rows = rows } end
            end
            run = 0
        end
    end
end
for x = px - R, px + R do
    local run, start = 0, 0
    for y = py - R, py + R + 1 do
        if y <= py + R and road(x, y) then
            if run == 0 then start = y end
            run = run + 1
        else
            if run > bestY.len then
                local cols = 0
                for dx = -3, 3 do if road(x + dx, start + math.floor(run / 2)) then cols = cols + 1 end end
                if cols >= 4 then bestY = { len = run, y0 = start, x = x, cols = cols } end
            end
            run = 0
        end
    end
end
return string.format("player %d,%d | along x: len %d from x=%s y=%s rows=%s | along y: len %d from y=%s x=%s cols=%s",
    px, py, bestX.len, tostring(bestX.x0), tostring(bestX.y), tostring(bestX.rows),
    bestY.len, tostring(bestY.y0), tostring(bestY.x), tostring(bestY.cols))

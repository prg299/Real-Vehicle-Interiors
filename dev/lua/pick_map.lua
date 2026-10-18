-- Developer test driver: what a right-click at each screen point inside the vehicle you are in would pick
-- (MELens.Interact.pick), on a grid of screen points, for dev\pick_map.py to lay over a screenshot.
-- Returns "x0 y0 step cols rows|<cells>|<labels>": cells row by row, comma separated, each the spot index
-- picked there, "p" panel, "d" driver's seat, "l" a loose item, "-" nothing; labels "index:x:y;..." the screen
-- point of the middle of the top of every piece.
local STEP = 4
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a vehicle with a profile" end
local P, I = MELens.Parts, MELens.Interact
local offset = vehicle:getScript():getModel():getOffset()
local vec = Vector3f.new()
local base = vehicle:getWorldPos(0, 0, 0, Vector3f.new()):z()

local function screenOf(x, y, z)
    vehicle:getWorldPos(offset:x() + x, offset:y() + y, offset:z() + z, vec)
    return ISCoordConversion.ToScreen(vec:x(), vec:y(), base + (offset:y() + y) / 2.44949)
end

-- the screen box around the vehicle's inside (its spots, floor to the top of the highest stack)
local x0, y0, x1, y1 = math.huge, math.huge, -math.huge, -math.huge
local labels = {}
for index, spot in ipairs(profile.spots) do
    local piece = P.pieceAt(P.spotPart(vehicle, index))
    local length, depth, height = P.footprint(spot, piece)
    local bottom = profile.floorY + (spot.rise or 0)
    for _, a in ipairs({ -length / 2, length / 2 }) do
        for _, d in ipairs({ 0, depth }) do
            for _, h in ipairs({ bottom, bottom + height }) do
                local x, z = P.spotPoint(spot, a, d)
                local sx, sy = screenOf(x, h, z)
                x0, y0, x1, y1 = math.min(x0, sx), math.min(y0, sy), math.max(x1, sx), math.max(y1, sy)
            end
        end
    end
    if piece then
        local x, z = P.spotPoint(spot, 0, depth / 2)
        local sx, sy = screenOf(x, bottom + height, z)
        labels[#labels + 1] = string.format("%d:%d:%d", index, math.floor(sx + 0.5), math.floor(sy + 0.5))
    end
end
x0, y0 = math.floor(x0 - 20), math.floor(y0 - 20)
x1, y1 = math.ceil(x1 + 20), math.ceil(y1 + 20)
local cols, rows = math.floor((x1 - x0) / STEP) + 1, math.floor((y1 - y0) / STEP) + 1
local cells = {}
for r = 0, rows - 1 do
    for c = 0, cols - 1 do
        local hit = I.pick(vehicle, profile, x0 + c * STEP, y0 + r * STEP)
        local v = "-"
        if hit then
            if hit.index then v = tostring(hit.index)
            elseif hit.kind == "panel" then v = "p"
            elseif hit.kind == "driver" then v = "d"
            else v = "l" end
        end
        cells[#cells + 1] = v
    end
end
return string.format("%d %d %d %d %d|%s|%s", x0, y0, STEP, cols, rows, table.concat(cells, ","), table.concat(labels, ";"))

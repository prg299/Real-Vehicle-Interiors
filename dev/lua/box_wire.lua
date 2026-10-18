-- Developer test driver: the screen points of the eight corners of every piece in the vehicle you are in, as the
-- right-click pick projects them (dev\pick_map.py --wire draws them as boxes over a screenshot).
-- Returns "index:x,y x,y ... (8 corners: bottom 4 then top 4);..."
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a vehicle with a profile" end
local P = MELens.Parts
local offset = vehicle:getScript():getModel():getOffset()
local vec = Vector3f.new()
local base = vehicle:getWorldPos(0, 0, 0, Vector3f.new()):z()

local function screenOf(x, y, z)
    vehicle:getWorldPos(offset:x() + x, offset:y() + y, offset:z() + z, vec)
    return ISCoordConversion.ToScreen(vec:x(), vec:y(), base + (offset:y() + y) / 2.44949)
end

local out = {}
for index, spot in ipairs(profile.spots) do
    local piece = P.pieceAt(P.spotPart(vehicle, index))
    if piece then
        local length, depth, height = P.footprint(spot, piece)
        local bottom = profile.floorY + (spot.rise or 0)
        local pts = {}
        for _, h in ipairs({ bottom, bottom + height }) do
            for _, c in ipairs({ { -1, 0 }, { 1, 0 }, { 1, 1 }, { -1, 1 } }) do
                local x, z = P.spotPoint(spot, c[1] * length / 2, c[2] * depth)
                local sx, sy = screenOf(x, h, z)
                pts[#pts + 1] = string.format("%.1f,%.1f", sx, sy)
            end
        end
        out[#out + 1] = index .. ":" .. table.concat(pts, " ")
    end
end
return table.concat(out, ";")

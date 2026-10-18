-- Developer test driver: screen positions of points in the camper's passenger space
-- (x, y, z), for drawing furniture outlines and expected body points onto a capture.
-- Replace POINTS with a Lua list of { x, y, z } tables; returns "sx,sy;sx,sy;...".
local player = getPlayer()
local vehicle = player:getVehicle()
if not vehicle then return "not in a vehicle" end
local points = POINTS
local offset = vehicle:getScript():getModel():getOffset()
local vec = Vector3f.new()
local base = vehicle:getWorldPos(0, 0, 0, Vector3f.new()):z()
local zoom = getCore():getZoom(0)
local out = {}
for _, p in ipairs(points) do
    vehicle:getWorldPos(offset:x() + p[1], offset:y() + p[2], offset:z() + p[3], vec)
    local sx, sy = ISCoordConversion.ToScreen(vec:x(), vec:y(), base + (offset:y() + p[2]) / 2.44949)
    -- ToScreen gives the zoom-1 render position; window pixels are that / zoom
    out[#out + 1] = string.format("%.1f,%.1f", sx / zoom, sy / zoom)
end
return table.concat(out, ";")

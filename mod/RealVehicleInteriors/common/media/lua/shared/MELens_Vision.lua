-- Shared registration: clients owning zombies and Java-enabled servers use the
-- same hull/seat metadata. No player invisibility, target clearing or sound edits.
require "MELens_Phobia"
require "MELens_VisionGeometry"

MELens.Vision = MELens.Vision or {}
local V = MELens.Vision

function V.register()
    if not MELensRV or type(MELensRV.registerVisionHull) ~= "function" then return end
    for name, profile in pairs(MELens.Profiles or {}) do
        local ring = profile.shell and MELens.RoomRings and MELens.RoomRings[profile.walkGrid]
        local openings = MELens.VisionGeometry[name]
        if ring and #ring >= 3 and openings ~= nil then
            local points = {}
            for _, point in ipairs(ring) do points[#points + 1] = point[1] .. "," .. point[2] end
            MELensRV.registerVisionHull(name, table.concat(points, ";"), openings)
        end
    end
end

Events.OnGameBoot.Add(V.register)
Events.OnInitWorld.Add(V.register)

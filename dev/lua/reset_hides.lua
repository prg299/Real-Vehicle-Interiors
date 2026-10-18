-- Developer test driver: put back the keep planes the vehicles' profiles hide KI5 models with
-- (MELens.addStandingPositions does it at script load, but it also resets the passenger offsets, which moves
-- the character and so the camera in the middle of a test). The planes are one global map by model name, set
-- once for every profile when the scripts load: clearing them and putting back only the current vehicle's
-- (as this once did) leaves every other camper drawing KI5's own interior over ours until the game restarts.
MELensRV.clearKeepPlanes()
local count = 0
for _, profile in pairs(MELens.Profiles) do
    if profile.shell then
        local m = profile.mesh
        for model, keep in pairs(profile.hideKI5 or {}) do
            if keep == true then
                MELensRV.setKeepPlane(model, 0, 0, 0, 1)
            elseif type(keep) == "table" and keep.plane then
                local p = keep.plane
                MELensRV.setKeepPlane(model, p[1], p[2], p[3], p[4])
            else
                MELensRV.setKeepPlane(model, 0, 0, 1, keep / m.scale - m.lift)
            end
            count = count + 1
        end
    end
end
return count

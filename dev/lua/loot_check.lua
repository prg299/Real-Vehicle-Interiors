-- Developer test driver: the loot of every spawned cargo vehicle (MELensTest.all): each
-- box's container type and item count, and KI5's own cargo storage (expected empty on a
-- new vehicle, its loot being in the boxes).
local out = {}
for name, vehicle in pairs(MELensTest and MELensTest.all or {}) do
    local profile = MELens.profileFor(vehicle)
    if profile and profile.loot then
        local boxes = {}
        for index = 1, #(profile.spots or {}) do
            local part = MELens.Parts.spotPart(vehicle, index)
            local container = part and part:getItemContainer()
            table.insert(boxes, container and (container:getType() .. "=" .. container:getItems():size()) or "-")
        end
        local storage = vehicle:getPartById(profile.ki5Storage[1])
        local container = storage and storage:getItemContainer()
        table.insert(out, string.format("%s: %s | %s=%s", name, table.concat(boxes, " "), profile.ki5Storage[1],
            container and tostring(container:getItems():size()) or "missing"))
    end
end
return #out > 0 and table.concat(out, " || ") or "no cargo vehicles spawned (run spawn_all.lua)"

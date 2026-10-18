-- Developer test driver: remove every vehicle in the loaded world except the one the test character is in
-- (and MELensTest.vehicle): a restart loads the saved world with the vehicles earlier runs left standing
-- where new ones are spawned. Goes through the cell's own vehicle set (a vehicle that is not found on a grid
-- square, one resting on another, was left behind by the grid search this used to be).
local player = getPlayer()
local keep = { [player:getVehicle() or false] = true, [MELensTest and MELensTest.vehicle or false] = true }
local it = getCell():getVehicles():iterator()
local doomed, removed = {}, {}
while it:hasNext() do
    local v = it:next()
    if v and not keep[v] then
        doomed[#doomed + 1] = v
    end
end
for _, v in ipairs(doomed) do
    removed[#removed + 1] = tostring(v:getScriptName()) .. "#" .. v:getId()
    v:permanentlyRemove()
end
return "removed " .. #removed .. ": " .. table.concat(removed, ", ")

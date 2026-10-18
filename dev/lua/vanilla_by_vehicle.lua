-- Developer test driver (disposable test world only): the game's own furniture tiles on the ground on the
-- camera's side of the test vehicle (MELensTest.vehicle, heading E: the camera-facing flank is +y), in a row,
-- to compare ME: LENS' furniture with in the same shot, light and zoom. Run it again to replace what it placed.
local v = MELensTest and MELensTest.vehicle
if not v then return "spawn a vehicle first" end
local cell = getCell()
MELensTest.vanilla = MELensTest.vanilla or {}
for _, o in ipairs(MELensTest.vanilla) do
    local sq = o:getSquare()
    if sq then sq:transmitRemoveItemFromSquare(o) end
end
MELensTest.vanilla = {}
-- sprite, dx along the vehicle, dy away from it (tiles)
local ROW = {
    { "fixtures_counters_01_8", -2.0 }, { "fixtures_counters_01_40", -1.0 }, { "appliances_refrigeration_01_4", 0.0 },
    { "furniture_storage_01_4", 1.0 }, { "furniture_storage_02_4", 2.0 }, { "furniture_storage_01_0", 3.0 },
    { "furniture_bedding_01_8", 4.4 },
}
local vx, vy = math.floor(v:getX()), math.floor(v:getY())
local placed, missing = 0, {}
for _, e in ipairs(ROW) do
    local x, y = vx + math.floor(e[2]) + 1, vy + 4
    local sq = cell:getGridSquare(x, y, 0)
    if sq then
        for i = sq:getObjects():size() - 1, 1, -1 do
            local o = sq:getObjects():get(i)
            local sp = o:getSprite() and o:getSprite():getName() or ""
            if sp:find("^e_") or sp:find("^d_") or sp:find("^f_") or sp:find("^vegetation") or sp:find("^blends_grass") then sq:RemoveTileObject(o) end
        end
        local ok, obj = pcall(function() return IsoObject.new(cell, sq, e[1]) end)
        if ok and obj and obj:getSprite() then
            sq:AddTileObject(obj)
            table.insert(MELensTest.vanilla, obj)
            placed = placed + 1
        else
            missing[#missing + 1] = e[1]
        end
    end
end
return string.format("placed %d beside the vehicle at %d,%d; missing: %s", placed, vx, vy, table.concat(missing, ","))

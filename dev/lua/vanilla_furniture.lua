-- Developer test driver (disposable test world only): the game's own furniture tiles on the ground near the
-- test spot, to compare ME: LENS' furniture with in the same light and zoom. LAYOUT "row": three rows of 7
-- (OX, OY: the first tile's offset from MELensTest.start). LAYOUT "beside": a few pieces just south of where
-- dev/lua/spawn_one.lua puts a vehicle (9 tiles west of the start), so a capture from inside it shows both.
-- Run it again to replace what it placed.
local LAYOUT = "LAYOUTNAME"
local OX, OY = tonumber("OX") or 2, tonumber("OY") or 6
local ROWS = {
    { "fixtures_counters_01_0", "fixtures_counters_01_1", "appliances_cooking_01_4", "fixtures_sinks_01_0",
      "appliances_refrigeration_01_4", "furniture_storage_01_0", "furniture_storage_02_0" },
    { "furniture_bedding_01_0", "furniture_bedding_01_1", "furniture_seating_indoor_01_0", "furniture_tables_low_01_0",
      "furniture_seating_indoor_02_0", "furniture_seating_indoor_03_0", "fixtures_bathroom_01_0" },
    { "fixtures_counters_01_8", "fixtures_counters_01_40", "appliances_refrigeration_01_0", "furniture_storage_01_4",
      "furniture_storage_02_4", "furniture_bedding_01_8", "furniture_bedding_01_9" },
}
-- (dx, dy from MELensTest.start; the vehicle's middle is at -9, 0 and it is about 2.5 tiles wide)
local BESIDE = {
    { "fixtures_counters_01_0", -13, 3 }, { "fixtures_counters_01_1", -12, 3 }, { "appliances_cooking_01_4", -11, 3 },
    { "appliances_refrigeration_01_4", -9, 3 }, { "furniture_storage_01_0", -7, 3 }, { "furniture_storage_02_0", -5, 3 },
    { "furniture_bedding_01_0", -12, 5 }, { "furniture_bedding_01_1", -11, 5 }, { "furniture_seating_indoor_01_0", -9, 5 },
    { "furniture_tables_low_01_0", -8, 5 },
}
local s = MELensTest and MELensTest.start or { x = getPlayer():getX(), y = getPlayer():getY() }
local cell = getCell()
MELensTest = MELensTest or {}
-- (RemoveTileObject alone leaves these in place after the world was saved and loaded again)
for _, o in ipairs(MELensTest.vanilla or {}) do
    local sq = o:getSquare()
    if sq then sq:transmitRemoveItemFromSquare(o) end
end
MELensTest.vanilla = {}
local list = {}
if LAYOUT == "beside" then
    for _, e in ipairs(BESIDE) do list[#list + 1] = { e[1], math.floor(s.x) + e[2], math.floor(s.y) + e[3] } end
else
    for row, names in ipairs(ROWS) do
        for col, name in ipairs(names) do
            list[#list + 1] = { name, math.floor(s.x) + OX + (col - 1) * 2, math.floor(s.y) + OY + (row - 1) * 3 }
        end
    end
end
local placed, missing = 0, {}
for _, e in ipairs(list) do
    local name, x, y = e[1], e[2], e[3]
    local sq = cell:getGridSquare(x, y, 0)
    if sq then
        -- clear plants on the square first
        for i = sq:getObjects():size() - 1, 1, -1 do
            local o = sq:getObjects():get(i)
            local sp = o:getSprite() and o:getSprite():getName() or ""
            if sp:find("^e_") or sp:find("^d_") or sp:find("^f_") or sp:find("^vegetation") then sq:RemoveTileObject(o) end
        end
        local ok, obj = pcall(function() return IsoObject.new(cell, sq, name) end)
        if ok and obj and obj:getSprite() then
            sq:AddTileObject(obj)
            table.insert(MELensTest.vanilla, obj)
            placed = placed + 1
        else
            missing[#missing + 1] = name
        end
    end
end
return string.format("placed %d (%s); missing: %s", placed, LAYOUT, table.concat(missing, ","))

-- Developer test driver: the same items as dev/lua/loose_spike.lua lying on the ground beside the camper you
-- are in (the game's own world items), for comparing their size, orientation and height with the ones drawn
-- inside it. They stand in a row 3 tiles south of the camper's middle, one tile apart. LOOSE = 1 removes them again.
local player = getPlayer()
local vehicle = player:getVehicle()
if not vehicle then return "not in a vehicle" end
MELensTest = MELensTest or {}
for _, wi in ipairs(MELensTest.ground or {}) do
    pcall(function()
        wi:getSquare():transmitRemoveItemFromSquare(wi)
        wi:removeFromWorld()
        wi:removeFromSquare()
    end)
end
MELensTest.ground = {}
if tonumber("LOOSE") == 1 then return "removed" end
local types = { "Base.Hammer", "Base.Pot", "Base.Lantern_Hurricane", "Base.Spiffo", "Base.RadioBlack", "Base.Bag_Schoolbag" }
local cx, cy = math.floor(vehicle:getX()), math.floor(vehicle:getY()) + 3
for i, t in ipairs(types) do
    local sq = getCell():getGridSquare(cx + i - 3, cy, 0)
    local item = sq and instanceItem(t)
    if item then
        local wi = sq:AddWorldInventoryItem(item, 0.5, 0.5, 0.0)
        table.insert(MELensTest.ground, wi:getWorldItem())
    end
end
return #MELensTest.ground .. " items on the ground"

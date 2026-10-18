-- Developer test driver: the loose-item renderer (MELensRV.addLoose). Draws a few of the game's own
-- items inside the camper you are in, in a row along the aisle, and reports each one's model and size.
-- Run it twice: the first call starts loading the models, the second draws them.
-- TILE (default 1.5) is the factor the game's iso camera gives an item, set by MELensRV.setLooseTuning.
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a camper" end
local rv = MELensRV
rv.setLooseBasis(profile.mesh.scale, profile.mesh.lift)
local tile = tonumber("TILE") or 1.5
rv.setLooseTuning(tile, 64)
local YAW = tonumber("YAW") or 0
local types = { "Base.Hammer", "Base.Pot", "Base.Lantern_Hurricane", "Base.Spiffo", "Base.RadioBlack", "Base.Bag_Schoolbag" }
local zs = { -1.2, -0.7, -0.2, 0.3, 0.8, 1.3 }
MELensTest = MELensTest or {}
MELensTest.spike = MELensTest.spike or {}
local lines = {}
rv.beginLoose()
for i, t in ipairs(types) do
    local item = MELensTest.spike[t] or instanceItem(t)
    if item then
        MELensTest.spike[t] = item
        local ok = rv.addLoose(item, profile.aisleX or 0, profile.floorY, zs[i], YAW)
        lines[#lines + 1] = string.format("%s model=%s size=%s added=%s", t, tostring(rv.hasItemModel(item)), tostring(rv.itemSize(item)), tostring(ok))
    else
        lines[#lines + 1] = t .. " MISSING"
    end
end
rv.endLoose()
lines[#lines + 1] = rv.looseStatus()
return lines

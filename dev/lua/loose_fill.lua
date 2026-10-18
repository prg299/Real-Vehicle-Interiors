-- Developer test driver: puts an item on every surface of the vehicle you are in (the tops of the furniture, the
-- wheel wells) and a few on the floor, to check at a glance that they stand where they should. Run inside a vehicle
-- (dev/preview_interiors.ps1 -AfterEnter dev/lua/loose_fill.lua does it for each one).
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a camper" end
local L, P = MELens.Loose, MELens.Parts
local floor = L.floorContainer(vehicle)
if not floor then return "no floor" end
floor:clear()
local part = L.floorPart(vehicle)
part:getModData()[L.KEY] = nil
local types = { "Base.Hammer", "Base.Pot", "Base.Lantern_Hurricane", "Base.Spiffo", "Base.RadioBlack", "Base.Wrench", "Base.Screwdriver" }
local made, tried = 0, 0
local function put(surface, x, z, yaw)
    tried = tried + 1
    local t = types[tried % #types + 1]
    local ok, item = pcall(instanceItem, t)
    if not ok or not item then return end
    floor:AddItem(item)
    L.set(vehicle, item, x, surface.y, z, yaw or 0, surface.s)
    made = made + 1
end
local report = {}
for _, surface in ipairs(L.surfaces(vehicle, profile)) do
    if surface.kind ~= "floor" then
        put(surface, (surface.x0 + surface.x1) / 2, (surface.z0 + surface.z1) / 2, 0)
        report[#report + 1] = string.format("%s %s s=%d y=%.2f", surface.kind, surface.name or "", surface.s, surface.y)
    end
end
-- the floor: a few points of free floor
local points = L.floorPoints(vehicle, profile)
for i = 1, 4 do
    if #points > 0 then
        local p = points[(i * 7) % #points + 1]
        put({ y = profile.floorY, s = 0 }, p[1], p[2], i * 70)
    end
end
report[#report + 1] = made .. " items"
return report

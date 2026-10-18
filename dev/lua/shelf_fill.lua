-- Developer test driver: stands a shelf unit in the vehicle you are in (in a heater's place, else a cabinet's, a
-- fridge's or a wardrobe's) and puts a plush, a hammer and a pot on its boards. Run inside a vehicle
-- (dev/preview_interiors.ps1 -AfterEnter dev/lua/shelf_fill.lua does it for each one).
local player = getPlayer()
local vehicle = player:getVehicle()
local profile = vehicle and MELens.profileFor(vehicle)
if not profile then return "not in a camper" end
local L, P = MELens.Loose, MELens.Parts
local floor = L.floorContainer(vehicle)
floor:clear()
L.floorPart(vehicle):getModData()[L.KEY] = nil

local target
for pass = 1, 2 do
    for index = 1, #profile.spots do
        local part = P.spotPart(vehicle, index)
        local piece = P.pieceAt(part)
        local wanted = pass == 1 and piece == "heater"
            or pass == 2 and (piece == "cabinet" or piece == "fridge" or piece == "wardrobe")
        if wanted and not target then
            target = { index = index, part = part, was = piece }
        end
    end
end
if not target then return "no spot for a shelf" end

local part = target.part
if part:getItemContainer() then part:getItemContainer():clear() end
part:setInventoryItem(nil)
P.applyPiece(vehicle, part)
part:setInventoryItem(instanceItem("Base.MELensRV_Shelf"))
P.applyPiece(vehicle, part)
vehicle:transmitPartItem(part)

local report = { string.format("shelf at spot %d (was %s)", target.index, target.was) }
local wanted = { shelf1 = { "Base.Hammer", 90 }, shelf2 = { "Base.Spiffo", 0 }, top = { "Base.Pot", 0 } }
for _, surface in ipairs(L.surfaces(vehicle, profile)) do
    local job = surface.piece == "shelf" and surface.s == target.index and wanted[surface.name]
    if job then
        local item = instanceItem(job[1])
        floor:AddItem(item)
        L.set(vehicle, item, (surface.x0 + surface.x1) / 2, surface.y, (surface.z0 + surface.z1) / 2, job[2], surface.s)
        report[#report + 1] = string.format("%s on %s y=%.2f", job[1], surface.name, surface.y)
    end
end
return report

-- Developer test driver: spawn one of every vehicle ME: LENS has an inside for, in a row
-- east of the player (facing east, 4 tiles apart), repaired, unlocked and with keys.
-- MELensTest.all[name] = vehicle.
MELensTest = MELensTest or {}
MELensTest.all = {}
local player = getPlayer()
if not player then return "no player" end
local names = {
    "Base.Trailer54FlyingCloud22", "Base.Trailer61Bambi16", "Base.Trailer61Airflyte", "Base.Trailer61Astrodome",
    "Base.Trailer87Scamp13", "Base.Trailer87Scamp16", "Base.87fordB700school", "Base.87fordF700box",
    "Base.TrailerKI5cargoSmall", "Base.TrailerKI5cargoMedium", "Base.TrailerKI5cargoLarge",
}
local out = {}
for i, name in ipairs(names) do
    local sq = getCell():getGridSquare(math.floor(player:getX()) + 8, math.floor(player:getY()) + (i - 1) * 4, 0)
    local vehicle = sq and addVehicleDebug(name, IsoDirections.E, 0, sq)
    if vehicle then
        vehicle:repair()
        for p = 0, vehicle:getPartCount() - 1 do
            local door = vehicle:getPartByIndex(p):getDoor()
            if door then door:setLocked(false) end
        end
        player:getInventory():AddItem(vehicle:createVehicleKey())
        MELensTest.all[name] = vehicle
        out[#out + 1] = string.format("%s id=%d seat=%d", name, vehicle:getId(), MELens.cabinSeat(vehicle))
    else
        out[#out + 1] = name .. " FAILED"
    end
end
return table.concat(out, " | ")

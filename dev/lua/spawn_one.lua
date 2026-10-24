-- Developer test driver: spawn one vehicle (replace NAME with its script name, e.g.
-- "Base.87fordB700school") OFFSET tiles east of the player (negative: west), facing east, repaired, unlocked
-- and with its key, as MELensTest.vehicle; the previous test vehicle is removed.
-- MELensTest.all[NAME] = the vehicle (for loot_check.lua).
MELensTest = MELensTest or {}
MELensTest.all = MELensTest.all or {}
local HEADING = "E"           -- which way the vehicle faces (N, E, S or W; dev/review_interiors.ps1 sets it)
local OFFSET = tonumber("7")      -- tiles east of the player (dev/preview_interiors.ps1 uses -9: grass, no power lines)
local player = getPlayer()
local old = MELensTest.vehicle
if old and player:getVehicle() == old then return "leave the vehicle first" end
if old then
    for name, v in pairs(MELensTest.all) do
        if v == old then MELensTest.all[name] = nil end
    end
    old:permanentlyRemove()
    MELensTest.vehicle = nil
end
local sq = getCell():getGridSquare(math.floor(player:getX()) + OFFSET, math.floor(player:getY()), 0)
-- a clean spot for the capture: no bushes, flowers or tall plants in and around where the
-- vehicle stands, and no grass tufts right under it (plants under an open vehicle poke through
-- its floor; the test world is disposable)
if sq then
    local cx, cy = sq:getX(), sq:getY()
    for x = cx - 8, cx + 8 do
        for y = cy - 8, cy + 8 do
            local s = getCell():getGridSquare(x, y, 0)
            if s then
                for i = s:getObjects():size() - 1, 1, -1 do
                    local o = s:getObjects():get(i)
                    local name = o:getSprite() and o:getSprite():getName() or ""
                    local underneath = math.abs(x - cx) <= 6 and math.abs(y - cy) <= 6
                    if name:find("^f_bushes") or name:find("^d_plants") or name:find("^vegetation_")
                            or name:find("^boulders") or name:find("^e_[a-z]*JUMBO") or name:find("^e_[a-z]*tree")
                            or (underneath and (name:find("^e_newgrass") or name:find("^d_generic"))) then
                        s:RemoveTileObject(o)
                    end
                end
            end
        end
    end
end
-- This fixture supplies its own key below. Avoid the engine's EasyUse key
-- spawn, which can abort addToWorld for a factory trailer's empty glovebox.
local script = getScriptManager():getVehicle("NAME")
local neverKey = script and script:neverSpawnKey()
-- Explicit audit/media spawns must retain their requested identity. The
-- ordinary world spawner may replace profession vans with random variants.
local professionKey = script and script:getName()
local profession = ProfessionVehicles and ProfessionVehicles[professionKey]
if profession then ProfessionVehicles[professionKey] = nil end
if script then script:Load(script:getName(), "{ neverSpawnKey = true, }") end
local vehicle = sq and addVehicleDebug("NAME", IsoDirections[HEADING], 0, sq)
if script then script:Load(script:getName(), "{ neverSpawnKey = " .. tostring(neverKey) .. ", }") end
if profession then ProfessionVehicles[professionKey] = profession end
if not vehicle then return "NAME FAILED" end
assert(vehicle:getScript():getFullName() == "NAME", "explicit spawn changed vehicle identity")
vehicle:repair()
-- Keep the stock repair result intact: the production script must preserve bare
-- furniture spots itself. Clearing them here previously hid overfilled F700 stacks.
for p = 0, vehicle:getPartCount() - 1 do
    local door = vehicle:getPartByIndex(p):getDoor()
    if door then door:setLocked(false) end
end
player:getInventory():AddItem(vehicle:createVehicleKey())
MELensTest.vehicle = vehicle
MELensTest.all["NAME"] = vehicle
return string.format("NAME id=%d at %.1f,%.1f seat=%d", vehicle:getId(), vehicle:getX(), vehicle:getY(), MELens.cabinSeat(vehicle))

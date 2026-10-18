-- Developer test driver (disposable test world only): zombies standing around the vehicle the player is in
-- (the test spot MELensTest.start, or the player), to see them with the cutaway interior. COUNT zombies on a
-- ring of RADIUS tiles. They are real zombies: they notice the player and walk up to the vehicle. Run it
-- again to clear the ones it placed first.
local COUNT, RADIUS = tonumber("COUNT") or 6, tonumber("RADIUS") or 4
MELensTest = MELensTest or {}
for _, z in ipairs(MELensTest.zombies or {}) do
    pcall(function() z:removeFromWorld(); z:removeFromSquare() end)
end
MELensTest.zombies = {}
local p = getPlayer()
local v = p:getVehicle()
local cx, cy = p:getX(), p:getY()
if v then cx, cy = v:getX(), v:getY() end
local made = 0
for i = 1, COUNT do
    local a = (i / COUNT) * 2 * math.pi
    local x, y = cx + math.cos(a) * RADIUS, cy + math.sin(a) * RADIUS
    local list = addZombiesInOutfit(x, y, 0, 1, nil, 50)
    if list and list:size() > 0 then
        local z = list:get(0)
        table.insert(MELensTest.zombies, z)
        made = made + 1
    end
end
return string.format("zombies %d around %.1f,%.1f vehicle=%s", made, cx, cy, tostring(v ~= nil))

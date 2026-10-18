local p = getPlayer()
local v = p and p:getVehicle()
assert(v and MELens.isStanding(p), "player must be standing inside the saved camper")
MELensTest = {vehicle = v, all = {}}
local seats, parts = {}, {}
for i = 0, v:getMaxPassengers() - 1 do
    local part = v:getAllSeatParts():get(i)
    seats[tostring(i)] = {passenger = v:getScript():getPassenger(i):getId(),
                         part = part and part:getId() or "MISSING"}
end
for _, id in ipairs(MELens.standingIds(MELens.profileFor(v))) do
    local part = v:getPartById("Seat" .. id)
    assert(part and not part:getItemContainer(), "metadata part has storage")
end
for i = 0, v:getPartCount() - 1 do
    local part = v:getPartByIndex(i)
    parts[tostring(i)] = {id = part:getId(),
                         item = part:getInventoryItem() and part:getInventoryItem():getFullType()}
end
local sentinel = v:getPartById("MELensFloor"):getItemContainer():containsType("TinOpener")
assert(sentinel, "stored test item lost")
local console = UIManager.getDebugConsole()
if console then console:setVisible(false) end
return {standing = true, seats = seats, parts = parts, storedItemPreserved = sentinel,
        metadataStorageAbsent = true, world = getWorld():getWorld()}

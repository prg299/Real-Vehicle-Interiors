-- Production geometry, capacity repair and added-seat lifecycle with engine doubles.
do
    local M, P = MELens, MELens.Parts
    local profile = M.Profiles["Base.87fordF700box"]
    check(#profile.spots == 83, "F700 cargo/furniture place count")
    for i = 1, 63 do check(profile.spots[i].cargo, "saved box ID moved: " .. i) end
    for i = 64, 81 do check(profile.spots[i].length == 1, "released furniture place moved: " .. i) end
    check(P.fits(profile.spots[82], "bed") and P.fits(profile.spots[83], "dinette"), "salvaged bed/dinette cannot fit truck")
    check(P.fits(profile.spots[82], "dinette") and P.fits(profile.spots[83], "bed"), "truck furniture cannot swap sides")
    check(P.roomFor(profile, { [82] = "bed" }, 83, "dinette"), "bed and dinette overlap across aisle")
    local collision = false
    for i = 1, 63 do
        if not P.roomFor(profile, { [i] = "box" }, 82, "bed") then collision = true end
    end
    check(collision, "new bed ignores existing cargo")
    check(not P.fits(profile.spots[1], "bed"), "bed accepted in stacked cargo slot")
    check(#M.interiorSeatIds(profile) + 2 <= M.MAX_SEATS, "new truck seats exceed multiplayer limit")
    for i, id in ipairs(M.standingIds(profile)) do
        check(M.interiorSeatIds(profile)[i] == id, "released standing passenger index moved")
    end

    local oldClient, oldServer, oldBridge, oldInstance = isClient, isServer, MELensRV, instanceItem
    isClient, isServer, MELensRV = function() return false end, function() return false end, nil
    local function item(piece, capacity)
        local it = { capacity = capacity or 0, full = piece == "marker" and "Base.MELensRV_Seat" or P.itemType(piece) }
        function it:getFullType() return self.full end
        function it:getMaxCapacity() return self.capacity end
        function it:setMaxCapacity(n) self.capacity = n end
        return it
    end
    instanceItem = function() return item("marker") end
    local v = { parts = {} }
    function v:getScript() return { getFullName = function() return "Base.87fordF700box" end } end
    function v:getPartById(id) return self.parts[id] end
    local function part(id, piece, capacity)
        local c = { capacity = capacity or 0, contents = { { original = true } } }
        function c:getCapacity() return self.capacity end
        function c:setCapacity(n) self.capacity = n end
        function c:setType(n) self.kind = n end
        function c:setCustomTemperature(n) self.temperature = n end
        function c:setExplored(n) self.explored = n end
        function c:setAcceptItemFunction(n) self.accept = n end
        local p = { id = id, item = piece and item(piece), container = c }
        function p:getId() return self.id end
        function p:getInventoryItem() return self.item end
        function p:setInventoryItem(n) self.item = n end
        function p:getItemContainer() return self.container end
        function p:setContainerCapacity(n) self.container:setCapacity(n) end
        v.parts[id] = p
        return p
    end
    for _, id in ipairs(profile.extraSeats) do part("Seat" .. id) end
    for _, row in ipairs({ { 1, "box", 20 }, { 64, "fridge", 30 }, { 82, "bed", 20 } }) do
        local p = part(P.SPOT .. row[1], row[2], 1)
        local installed, contents = p.item, p.container.contents
        P.applyPiece(v, p)
        check(p.item == installed and p.container.contents == contents, "capacity repair replaced furniture or contents")
        check(p.container.capacity == row[3] and p.item.capacity == row[3], "1kg capacity not repaired")
        p.container.capacity = 0
        P.showPiece(p)
        check(p.container.capacity == row[3], "0kg live capacity not repaired on refresh")
    end
    check(v.parts.SeatMELensFurnitureLeft1.item ~= nil, "bed has no usable passenger")
    check(v.parts.SeatMELensFurnitureLeft2.item == nil, "bed exposes a second occupant")
    local dining = part(P.SPOT .. 83, "dinette")
    P.applyPiece(v, dining)
    check(v.parts.SeatMELensFurnitureRight1.item and v.parts.SeatMELensFurnitureRight2.item, "dinette lacks two seats")
    check(P.seatPose(v, profile, "MELensFurnitureLeft1").kind == "bed", "new bed has wrong pose")
    check(P.seatKindAt(v, profile, "MELensFurnitureRight2") == "seat", "new dinette has wrong pose")
    dining.item = nil
    P.applyPiece(v, dining)
    check(not v.parts.SeatMELensFurnitureRight1.item and not v.parts.SeatMELensFurnitureRight2.item,
        "removed dinette leaves phantom passengers")
    local placeholder = part(P.SPOT .. 65, "marker", 1)
    local cargo = placeholder.container.contents
    P.applyPiece(v, placeholder)
    check(placeholder.item == nil and placeholder.container.contents == cargo,
        "repair placeholder became furniture or discarded orphaned storage")
    isClient, isServer, MELensRV, instanceItem = oldClient, oldServer, oldBridge, oldInstance
end

-- Component audit inside the native test process. Detached vehicles are never added
-- to the world; user-input entry evidence comes from the separate keyboard/mouse run.
local function signature(script)
    local p = script:getPassenger(0)
    local pos = p and p:getPositionById("inside")
    return table.concat({script:getPartCount(), script:getPassengerCount(),
        tostring(script:getExtents()), tostring(script:getModel():getOffset()),
        pos and tostring(pos:getOffset()) or "none"}, "|")
end
local before, count = {}, 0
for name in pairs(MELens.Profiles) do
    local script = getScriptManager():getVehicle(name)
    if script then before[name] = signature(script) end
end
local control = getScriptManager():getVehicle("Base.CarNormal")
local controlBefore = signature(control)
MELens.addStandingPositions()
MELens.addStandingPositions()
local results = {}
for name, expected in pairs(before) do
    local script = getScriptManager():getVehicle(name)
    assert(signature(script) == expected, "non-idempotent or scaled: " .. name)
    local vehicle = BaseVehicle.new(getCell())
    vehicle:setScript(name)
    local seats = {}
    for _, id in ipairs(MELens.standingIds(MELens.Profiles[name])) do
        local index = script:getPassengerIndex(id)
        local part = vehicle:getAllSeatParts():get(index)
        assert(part and part:getId() == "Seat" .. id, name .. ": missing " .. id)
        assert(part:getContainerSeatNumber() == index, name .. ": wrong index")
        -- Repair the old missing-container state and retain native combat's
        -- unguarded capacity-weight read across repeated initialization.
        MELens.initStandingPart(vehicle, part)
        local container = part:getItemContainer()
        MELens.initStandingPart(vehicle, part)
        assert(container and part:getItemContainer() == container, name .. ": unstable combat container")
        assert(container:getCapacity() == 0 and container:getCapacityWeight() == 0,
            name .. ": standing seat must have an empty zero-capacity container")
        assert(not vehicle:canAccessContainer(part:getIndex(), getPlayer()), name .. ": metadata exposed as loot")
        assert(not MELens.standingContainerTest(vehicle, part, getPlayer()))
        seats[id] = index
        count = count + 1
    end
    results[name] = seats
end
assert(signature(control) == controlBefore, "ordinary car changed")
return {bindings = count, profiles = results, repeatInitialization = "unchanged",
        ordinaryCar = "unchanged"}

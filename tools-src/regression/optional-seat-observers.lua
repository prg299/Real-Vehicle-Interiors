-- Engine-double coverage of independent seated observers and cleanup. Actual
-- multiplayer replication and rendered peers require a native two-client run.
do
    local M, P = MELens, MELens.Parts
    local old = { rv = MELensRV, mods = getActivatedMods, online = getOnlinePlayers,
        profile = M.profileFor, standing = M.isStandingSeat, vanilla = M.isVanillaSeat,
        facing = M.seatedFacing }
    local enabled, facing, cleared, placements = false, {}, {}, 0
    MELensRV = completeJava({
        setFacing = function(p, turn) facing[p] = turn end,
        clearFacingOf = function(p) cleared[p] = true; facing[p] = nil end,
    })
    getActivatedMods = function() return { contains = function(_, id) return enabled and id == "damnlib" end } end
    local profile = { floorY = .2, spots = {{ x = .8, z = -.5, wall = "left", seats = { "bench" } }} }
    local part = { getInventoryItem = function() return { getFullType = function() return P.itemType("medbench") end } end }
    local passenger = { getId = function() return "bench" end,
        getPositionById = function() return { getOffset = function() return Vector3f.new() end } end }
    local vehicle = { getSeat = function() return 0 end,
        getScript = function() return { getPassenger = function() return passenger end } end,
        getPartById = function(_, id) if id == P.SPOT .. "1" then return part end end }
    function vehicle:setPassenger(_, p, vec)
        placements = placements + 1
        p.placed = { x = vec:x(), y = vec:y(), z = vec:z() }
    end
    local function player(localPlayer)
        local p = { vehicle = vehicle, vars = {} }
        function p:getVehicle() return self.vehicle end
        function p:isLocalPlayer() return localPlayer end
        function p:getVariableString(k) return self.vars[k] end
        function p:setVariable(k, value) self.vars[k] = value end
        function p:clearVariable(k) self.vars[k] = nil end
        return p
    end
    local remote, localPlayer = player(false), player(true)
    getOnlinePlayers = function() return { size = function() return 2 end,
        get = function(_, i) return i == 0 and remote or localPlayer end } end
    M.profileFor = function(v) return v == vehicle and profile end
    M.isStandingSeat, M.isVanillaSeat = function() return false end, function() return false end
    M.seatedFacing = nil
    M.updateIndependentSeatObservers()
    local expected = P.seatPose(vehicle, profile, "bench")
    check(remote.vars.damnPosition == "MELensSeat", "observer derives independent pose from replicated seat")
    check(remote.placed.y == expected.y and facing[remote] == expected.turn, "observer applies independent position/facing")
    check(placements == 1 and not localPlayer.placed, "observer does not overwrite local seated control")
    check(M.seatedFacing == nil, "remote pose does not claim local facing ownership")
    remote.vehicle = nil
    M.updateIndependentSeatObservers()
    check(remote.vars.damnPosition == nil and cleared[remote], "remote departure clears only its owned fallback pose/facing")
    remote.vehicle, remote.vars.damnPosition, enabled = vehicle, "facingLeft", true
    M.updateIndependentSeatObservers()
    check(placements == 1 and remote.vars.damnPosition == "facingLeft", "enabled damnlib keeps observer ownership")
    MELensRV, getActivatedMods, getOnlinePlayers = old.rv, old.mods, old.online
    M.profileFor, M.isStandingSeat, M.isVanillaSeat, M.seatedFacing = old.profile, old.standing, old.vanilla, old.facing
end

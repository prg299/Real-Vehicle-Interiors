-- Shared interior lookup only. Panic mutation awaits a source-specific engine hook.
do
    local M, F = MELens, MELens.Phobia
    local oldNow = now

    local function vehicle(profileName, passengerIds)
        local script = {}
        function script:getFullName() return profileName end
        function script:getPassengerIndex(id) return passengerIds[id] or -1 end
        local value = {}
        function value:getScript() return script end
        function value:getSeat(_) return self.seat end
        value.seat = -1
        return value
    end

    check(type(F.roomArea) == "function" and type(F.interiorSeat) == "function",
          "shared phobia geometry/seat helpers were not loaded")
    local function hasCallback(event, callback)
        for _, registered in ipairs(event.callbacks) do
            if registered == callback then return true end
        end
        return false
    end
    check(hasCallback(Events.OnGameBoot, F.registerEnclosures)
          and hasCallback(Events.OnInitWorld, F.registerEnclosures),
          "native enclosure registrations are not retried after scripts/world initialize")
    check(type(F.onPlayerUpdate) == "function"
          and hasCallback(Events.OnPlayerUpdate, F.onPlayerUpdate),
          "server PANIC sync callback is not registered")

    local f700 = M.Profiles["Base.87fordF700box"]
    local f700Vehicle = vehicle("Base.87fordF700box", {
        MELensCabin = 1, FrontLeft = 0, FrontRight = 2,
    })
    local f700Area = F.roomArea(f700)
    check(f700Area and f700Area > 0,
          "F700 enclosed floor area was not measured from its room ring")
    check(F.interiorSeat(f700Vehicle, f700, 1) == "standing",
          "server-side F700 standing seat was not classified from the shared profile")
    check(F.interiorSeat(f700Vehicle, f700, 0) == nil,
          "F700 vanilla cab seat was incorrectly treated as an enclosed interior")
    check(F.interiorSeat(f700Vehicle, f700, -1) == nil,
          "unseated F700 player was incorrectly treated as inside")

    local bus = M.Profiles["Base.87fordB700school"]
    local busVehicle = vehicle("Base.87fordB700school", { P1 = 1, FrontLeft = 0 })
    local busArea = F.roomArea(bus)
    check(busArea and busArea > 0 and busArea ~= f700Area,
          "supported vehicles did not retain distinct enclosed floor areas")
    check(F.interiorSeat(busVehicle, bus, 1) == "P1",
          "B700 mapped passenger seat was not classified")
    check(F.interiorSeat(busVehicle, bus, 0) == nil,
          "B700 vanilla cab seat was incorrectly treated as an enclosed interior")

    local oldBridge = MELensRV
    local registrations = {}
    MELensRV = { registerPhobiaEnclosure = function(scriptName, passengerId, area)
        registrations[scriptName .. "/" .. passengerId] = area
    end }
    F.registerEnclosures()
    check(registrations["Base.87fordF700box/MELensCabin"] == f700Area
          and registrations["Base.87fordB700school/P1"] == busArea,
          "native bridge did not receive supported interior passenger positions")
    check(registrations["Base.87fordF700box/FrontLeft"] == nil
          and registrations["Base.87fordB700school/FrontLeft"] == nil,
          "native bridge registered a vanilla cab position as enclosed interior")

    local function player(panic, traits)
        local stats = { value = panic }
        function stats:get(_) return self.value end
        function stats:add(_, amount) self.value = self.value + amount end
        function stats:remove(_, amount) self.value = self.value - amount end
        local characterTraits = { values = traits }
        function characterTraits:get(id) return self.values[id] == true end
        local p = { stats = stats, traits = characterTraits, syncs = {}, vehicle = f700Vehicle }
        function p:getVehicle() return self.vehicle end
        function p:getCharacterTraits() return self.traits end
        function p:getStats() return self.stats end
        function p:recordSync(mask) table.insert(self.syncs, mask) end
        p.vehicle.seat = 1
        return p
    end

    -- With no Java bridge the native source is unchanged and this adapter is a no-op.
    local withJava = MELensRV
    local oldSyncPlayerStats = syncPlayerStats
    syncPlayerStats = function(character, mask) character:recordSync(mask) end
    local noJava = player(16, { Agoraphobic = true })
    MELensRV = nil
    F.onPlayerUpdate(noJava)
    check(noJava.stats.value == 16 and #noJava.syncs == 0 and F.lastSync[noJava] == nil,
          "no-Java server changed panic or sent a sync")

    MELensRV = withJava
    local oldIsServer = isServer
    local client = player(17, { Claustrophobic = true })
    isServer = function() return false end
    F.onPlayerUpdate(client)
    isServer = oldIsServer
    check(client.stats.value == 17 and #client.syncs == 0 and F.lastSync[client] == nil,
          "client-side callback sent an authoritative PANIC sync")

    local synced = player(20, { Agoraphobic = true })
    now = 1000
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 1 and synced.syncs[1] == 0x2000 and synced.stats.value == 20,
          "server did not sync only PANIC after native processing")
    now = 1050
    synced.stats.value = 20.2
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 1,
          "small PANIC changes were sent more often than five times per second")
    now = 1200
    synced.stats.value = 20.5
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 2 and synced.syncs[2] == 0x2000,
          "pending PANIC change was not sent at the five-hertz interval")
    now = 1250
    synced.stats.value = 21.6
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 3,
          "large PANIC change was not sent immediately")
    now = 1450
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 3,
          "unchanged PANIC was sent again")
    now = 1460
    synced.stats.value = 21.8
    synced.vehicle = nil
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 4 and synced.syncs[4] == 0x2000 and F.lastSync[synced] ~= nil,
          "exit did not send changed PANIC while retaining owner-sync tracking")
    now = 1700
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 4,
          "unchanged exited-player PANIC was sent again")
    now = 1710
    synced.stats.value = 21.5
    synced.traits.values.Agoraphobic = false
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 5 and F.lastSync[synced] ~= nil,
          "tracked PANIC decay stopped after exit or trait removal")
    now = 1720
    synced.stats.value = 23
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 6,
          "large post-exit PANIC change was not forwarded promptly")
    now = 1800
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 6 and F.lastSync[synced] ~= nil,
          "unchanged post-exit PANIC emitted a packet or lost tracking")
    now = 1900
    synced.stats.value = 0
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 7 and synced.syncs[7] == 0x2000 and F.lastSync[synced] ~= nil,
          "PANIC zero was not synced while retaining weak tracking for later rises")
    now = 2100
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 7,
          "unchanged zero-PANIC character emitted an extra sync")
    now = 2300
    synced.stats.value = 0.4
    F.onPlayerUpdate(synced)
    check(#synced.syncs == 8 and synced.syncs[8] == 0x2000,
          "later outside PANIC rise stopped syncing after a zero receipt")

    MELensRV = oldBridge
    now = oldNow
    syncPlayerStats = oldSyncPlayerStats
end

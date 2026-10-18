-- Shared geometry and seat classification for the enclosed-interior phobia adapter.
-- Panic mutation is deliberately not performed here: OnPlayerUpdate runs after the
-- engine's trait additions, independent panic sources, caps, and beta-blocker step.

MELens = MELens or {}
MELens.Phobia = MELens.Phobia or {}

local M, F = MELens, MELens.Phobia
local AREA_CACHE = {}

local function roomArea(profile)
    local key = profile and profile.walkGrid
    if not key then return nil end
    if AREA_CACHE[key] ~= nil then return AREA_CACHE[key] end
    local ring = M.RoomRings and M.RoomRings[key]
    if not ring or #ring < 3 then return nil end
    local twice = 0
    for i, point in ipairs(ring) do
        local nextPoint = ring[i % #ring + 1]
        if type(point[1]) ~= "number" or type(point[2]) ~= "number"
                or type(nextPoint[1]) ~= "number" or type(nextPoint[2]) ~= "number" then
            return nil
        end
        twice = twice + point[1] * nextPoint[2] - nextPoint[1] * point[2]
    end
    local area = math.floor(math.abs(twice) * 0.5 + 0.5)
    if area < 1 then return nil end
    AREA_CACHE[key] = area
    return area
end

local function interiorSeat(vehicle, profile, seat)
    if not vehicle or not profile or not profile.shell or not profile.walkGrid
            or seat == nil or seat < 0 then return nil end
    local script = vehicle:getScript()
    -- Cabin.lua is client-only, so classify seats from the shared profile/script
    -- contract instead of relying on its M.isStandingSeat helper.
    for _, id in ipairs(M.standingIds and M.standingIds(profile) or {}) do
        if script:getPassengerIndex(id) == seat then return "standing" end
    end
    for _, id in ipairs(profile.vanillaSeats or {}) do
        if script:getPassengerIndex(id) == seat then return nil end
    end
    for _, spot in ipairs(profile.spots or {}) do
        for _, id in ipairs(spot.seats or {}) do
            if script:getPassengerIndex(id) == seat then return id end
        end
    end
    return nil
end

F.roomArea = roomArea
F.interiorSeat = interiorSeat

-- The optional Java hook needs a shared, script-ID mapping; actual seat occupancy is
-- checked against the vehicle every player update. Passenger IDs are registered even
-- before the appended standing seats have been merged into the runtime script.
function F.registerEnclosures()
    local bridge = MELensRV
    if not bridge or type(bridge.registerPhobiaEnclosure) ~= "function" then return end
    for scriptName, profile in pairs(M.Profiles or {}) do
        local area = profile.shell and roomArea(profile)
        if area then
            local vanilla = {}
            for _, id in ipairs(profile.vanillaSeats or {}) do vanilla[id] = true end
            local ids = {}
            for _, id in ipairs(M.standingIds and M.standingIds(profile) or {}) do
                ids[id] = true
            end
            for _, spot in ipairs(profile.spots or {}) do
                for _, id in ipairs(spot.seats or {}) do ids[id] = true end
            end
            for id in pairs(ids) do
                if not vanilla[id] then
                    bridge.registerPhobiaEnclosure(scriptName, id, area)
                end
            end
        end
    end
end

Events.OnGameBoot.Add(F.registerEnclosures)
Events.OnInitWorld.Add(F.registerEnclosures)

-- A dedicated server with the native hook must forward its resulting panic value
-- to the owning client. The hook itself owns all panic changes; this only syncs PANIC.
local PANIC = CharacterStat.PANIC
local PANIC_MASK = 0x2000
local SYNC_INTERVAL_MS = 200
local LARGE_CHANGE = 1.0
local SYNC_EPSILON = 0.0001
F.lastSync = F.lastSync or setmetatable({}, { __mode = "k" })

function F.onPlayerUpdate(character)
    local bridge = MELensRV
    if not isServer() or not bridge or type(bridge.registerPhobiaEnclosure) ~= "function" then return end

    local vehicle = character and character:getVehicle()
    local profile = M.profileFor(vehicle)
    local seat = vehicle and vehicle:getSeat(character) or -1
    local seatId = interiorSeat(vehicle, profile, seat)
    local enclosed = seatId ~= nil and roomArea(profile) ~= nil
    local traits = character and character:getCharacterTraits()
    local targeted = traits ~= nil
            and (traits:get(CharacterTrait.AGORAPHOBIC) or traits:get(CharacterTrait.CLAUSTROPHOBIC))
    local prior = F.lastSync[character]
    local active = enclosed and targeted

    -- Once an enclosed phobia character has been tracked, keep forwarding the
    -- native stat as it decays/changes outside too. GameClient skips this native
    -- trait path and has no later owner-stat sync; dropping state on exit leaves
    -- the owner's displayed PANIC frozen at its last server receipt.
    if not active and not prior then return end

    local value = character:getStats():get(PANIC)
    local now = getTimestampMs()
    local changed = not prior or math.abs(value - prior.value) > SYNC_EPSILON
    local large = prior and math.abs(value - prior.value) >= LARGE_CHANGE
    local reachedZero = not active and value <= SYNC_EPSILON
    if changed and (not prior or now - prior.sentAt >= SYNC_INTERVAL_MS or large or reachedZero) then
        syncPlayerStats(character, PANIC_MASK)
        F.lastSync[character] = { value = value, sentAt = now }
    end
end

Events.OnPlayerUpdate.Add(F.onPlayerUpdate)

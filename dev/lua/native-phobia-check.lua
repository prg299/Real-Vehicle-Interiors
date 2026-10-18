-- Single-player native-tick phobia acceptance for an enclosed RVI cabin.
-- Fixture setup changes only this disposable test character's traits/stats;
-- observed effects come from IsoGameCharacter.updateInternal and the Java probe.
local M = assert(MELens, "ME: LENS is not loaded")
local T = {
    status = "running",
    scope = "single-player native phobia lookups in the F700 cabin; no multiplayer claim",
    cases = {},
}
M.MELensNativePhobiaTest = T

local PHASE_MS, SAMPLE_MS, PHASE_TIMEOUT_MS = 1400, 80, 15000
local player, vehicle, profile, callback
local state, phaseAt, sampleAt, phaseDeadline
local original, phaseIndex, expectedSeat
local phases = {
    { name = "inside-no-phobia-control", agora = false, claustro = false, panic = 25, beta = 0, betaDelta = 0, duration = PHASE_MS },
    { name = "inside-agoraphobic-suppressed", agora = true, claustro = false, panic = 25, beta = 0, betaDelta = 0, duration = PHASE_MS },
    { name = "inside-claustrophobic-control", agora = false, claustro = false, panic = 25, beta = 0, betaDelta = 0, duration = PHASE_MS },
    { name = "inside-claustrophobic-cabin-rate", agora = false, claustro = true, panic = 25, beta = 0, betaDelta = 0, duration = PHASE_MS },
    { name = "inside-near-cap-agoraphobic", agora = true, claustro = false, panic = 99.8, beta = 0, betaDelta = 0, duration = PHASE_MS },
    { name = "inside-agoraphobic-beta-active", agora = true, claustro = false, panic = 25, beta = 60, betaDelta = 0.001, duration = PHASE_MS },
    { name = "inside-agoraphobic-beta-expiring", agora = true, claustro = false, panic = 25, beta = 12, betaDelta = 0.01, duration = 5000 },
    { name = "inside-near-cap-claustrophobic", agora = false, claustro = true, panic = 99.8, beta = 0, betaDelta = 0, duration = PHASE_MS },
    { name = "inside-claustrophobic-beta-active", agora = false, claustro = true, panic = 25, beta = 60, betaDelta = 0.001, duration = PHASE_MS },
}

local function timestamp()
    return getTimestampMs()
end

local function trait(id)
    return player:getCharacterTraits():get(id) == true
end

local function jsonNumber(raw, key)
    if type(raw) ~= "string" then return nil end
    local value = string.match(raw, '"' .. key .. '":([^,}]+)')
    if not value or value == "null" then return nil end
    return tonumber(value)
end

local function jsonTrue(raw, key)
    return type(raw) == "string" and string.find(raw, '"' .. key .. '":true', 1, true) ~= nil
end

local function phobiaInfo()
    local ok, value = pcall(function() return MELensRV.phobiaInfo(player) end)
    if not ok then error("MELensRV.phobiaInfo failed: " .. tostring(value)) end
    if type(value) ~= "string" or value == "" then error("MELensRV.phobiaInfo returned no native receipt") end
    return value
end

local function release()
    pcall(function() MEMCNativeLab.releaseKeys() end)
end

local function restore()
    if not original or not player then return end
    local traits = player:getCharacterTraits()
    traits:set(CharacterTrait.AGORAPHOBIC, original.agora)
    traits:set(CharacterTrait.CLAUSTROPHOBIC, original.claustro)
    player:getStats():set(CharacterStat.PANIC, original.panic)
    player:setBetaEffect(original.beta)
    player:setBetaDelta(original.betaDelta)
    player:setGodMod(original.godMode)
    T.fixtureRestored = true
    T.restored = {
        agoraphobic = trait(CharacterTrait.AGORAPHOBIC),
        claustrophobic = trait(CharacterTrait.CLAUSTROPHOBIC),
        panic = player:getStats():get(CharacterStat.PANIC),
        beta = player:getBetaEffect(),
        betaDelta = player:getBetaDelta(),
        godMode = player:isGodMod(),
    }
end

local function stop(status, err)
    release()
    if callback then
        pcall(function() Events.OnTick.Remove(callback) end)
        callback = nil
    end
    local restoreOk, restoreErr = pcall(restore)
    T.status = status
    if err then T.error = tostring(err) end
    if not restoreOk then T.restoreError = tostring(restoreErr) end
    T.finishedAt = timestamp()
    return T
end

local function fail(message)
    return stop("failed", message)
end

local function assertFixture()
    if not player or not vehicle or player:getVehicle() ~= vehicle or not M.isStanding(player) then
        error("player left the F700 standing cabin during " .. tostring(state))
    end
end

local function beginPhase(index)
    local spec = phases[index]
    if not spec then
        T.acceptance = {
            nativeUpdateSequenceAdvanced = true,
            insideAgoraphobiaSuppressed = true,
            insideClaustrophobiaUsesCabinArea = true,
            nearCapStayedBelowMaximum = true,
            betaPositiveAndExpiryObserved = true,
            otherPanicContribution = "pre-existing panic baseline held; no independent threat source injected",
            crossProfileSizeComparison = "not run; this fixture measures the F700 registered cabin area",
            singlePlayerOnly = true,
        }
        stop("passed")
        return
    end
    local traits = player:getCharacterTraits()
    traits:set(CharacterTrait.AGORAPHOBIC, spec.agora)
    traits:set(CharacterTrait.CLAUSTROPHOBIC, spec.claustro)
    player:getStats():set(CharacterStat.PANIC, spec.panic)
    player:setBetaEffect(spec.beta)
    player:setBetaDelta(spec.betaDelta)
    state = "sample"
    local raw = phobiaInfo()
    local start = timestamp()
    phaseIndex = index
    phaseAt = start
    sampleAt = start
    phaseDeadline = start + PHASE_TIMEOUT_MS
    T.currentPhase = spec.name
    T.cases[index] = {
        name = spec.name,
        expectedAgora = spec.agora,
        expectedClaustrophobic = spec.claustro,
        initialPanic = spec.panic,
        initialBeta = spec.beta,
        betaDelta = spec.betaDelta,
        durationMs = spec.duration,
        vehicleId = vehicle:getId(),
        profile = profile.name,
        profileScript = vehicle:getScript():getFullName(),
        areaAtStart = jsonNumber(raw, "area"),
        samples = {},
        start = { t = start, panic = player:getStats():get(CharacterStat.PANIC),
                  beta = player:getBetaEffect(), x = player:getX(), y = player:getY(),
                  info = raw, sequence = jsonNumber(raw, "sequence") },
    }
end

local function sample()
    local raw = phobiaInfo()
    local now = timestamp()
    local row = {
        t = now,
        panic = player:getStats():get(CharacterStat.PANIC),
        beta = player:getBetaEffect(),
        betaDelta = player:getBetaDelta(),
        agoraphobic = trait(CharacterTrait.AGORAPHOBIC),
        claustrophobic = trait(CharacterTrait.CLAUSTROPHOBIC),
        inside = jsonTrue(raw, "inside"),
        agoraSuppressed = jsonTrue(raw, "agoraSuppressed"),
        claustroAdded = jsonNumber(raw, "claustroAdded") or 0,
        area = jsonNumber(raw, "area"),
        multiplier = jsonNumber(raw, "multiplier"),
        sequence = jsonNumber(raw, "sequence"),
        panicBefore = jsonNumber(raw, "panicAtLookupBefore"),
        panicAfter = jsonNumber(raw, "panicAtLookupAfter"),
        profileMatches = string.find(raw, '"profile":"' .. vehicle:getScript():getFullName() .. '"', 1, true) ~= nil,
        seatMatches = string.find(raw, '"seat":"' .. expectedSeat .. '"', 1, true) ~= nil,
        info = raw,
    }
    local spec = phases[phaseIndex]
    if not spec then error("internal phobia phase index error") end
    if row.agoraphobic ~= spec.agora or row.claustrophobic ~= spec.claustro then
        error(spec.name .. " trait fixture changed during native tick sampling")
    end
    if not row.inside or not row.profileMatches or not row.seatMatches then
        error(spec.name .. " receipt is not for the expected enclosed vehicle/seat: " .. raw)
    end
    if row.sequence == nil then error(spec.name .. " receipt has no native update sequence: " .. raw) end
    T.cases[#T.cases].samples[#T.cases[#T.cases].samples + 1] = row
    sampleAt = now
end

local function finishPhase(index)
    local spec, c = phases[index], T.cases[index]
    c.finish = { t = timestamp(), panic = player:getStats():get(CharacterStat.PANIC),
                 beta = player:getBetaEffect(), x = player:getX(), y = player:getY() }
    c.elapsedMs = c.finish.t - phaseAt
    c.panicDelta = c.finish.panic - c.start.panic
    c.samplesCount = #c.samples
    c.disturbedTiles = math.sqrt((c.finish.x-c.start.x)^2 + (c.finish.y-c.start.y)^2)
    if c.elapsedMs < spec.duration - 100 or c.elapsedMs > spec.duration + 700 then
        error(spec.name .. " native sample duration outside acceptance window: " .. c.elapsedMs)
    end
    if c.samplesCount < 8 then error(spec.name .. " collected too few native-update samples: " .. c.samplesCount) end
    if c.disturbedTiles > .04 then error(spec.name .. " actor moved during stationary trait test: " .. c.disturbedTiles) end
    local first, last, suppressed, added, maxPanic, sawBeta, sawExpired
    for _, s in ipairs(c.samples) do
        if not first then first = s end
        last = s
        maxPanic = math.max(maxPanic or -math.huge, s.panic)
        suppressed = suppressed or s.agoraSuppressed
        added = math.max(added or 0, s.claustroAdded)
        sawBeta = sawBeta or s.beta > 0
        sawExpired = sawExpired or s.beta <= 0
        if s.claustroAdded > 0 then
            local expected = .6 * math.max(0, 1 - s.area / 70) * s.multiplier
            if s.panicBefore == nil or s.panicAfter == nil or
               math.abs(s.panicAfter-math.min(100, s.panicBefore+s.claustroAdded)) > 1e-4 then
                error(spec.name .. " native panic receipt did not include the Claustrophobic addition: " .. s.info)
            end
            if math.abs(s.claustroAdded-expected) > 1e-4 then
                error(spec.name .. " Claustrophobic rate does not follow registered cabin area: " .. s.info)
            end
        end
    end
    c.distinctNativeUpdates = last.sequence - first.sequence
    if c.distinctNativeUpdates < 5 then error(spec.name .. " phobia probe did not advance with native updates") end
    if spec.agora and not suppressed then error(spec.name .. " native Agoraphobic lookup was not suppressed") end
    if not spec.agora and suppressed then error(spec.name .. " control unexpectedly suppressed Agoraphobic") end
    if spec.claustro and added <= 0 then error(spec.name .. " native Claustrophobic lookup added no cabin panic") end
    if not spec.claustro and added > 0 then error(spec.name .. " control unexpectedly added Claustrophobic panic") end
    if spec.name == "inside-near-cap-agoraphobic" and maxPanic >= 100 then
        error("near-cap Agoraphobic fixture reached panic cap")
    end
    if spec.beta > 0 and c.start.beta <= 0 then error(spec.name .. " beta fixture did not start active") end
    if string.find(spec.name, "beta-active", 1, true) and c.finish.beta <= 0 then
        error(spec.name .. " beta fixture expired before the active test finished")
    end
    if spec.name == "inside-agoraphobic-beta-expiring" and not (sawBeta and sawExpired) then
        error("beta-expiry case did not observe both positive and expired beta")
    end
    if spec.name == "inside-claustrophobic-beta-active" and not sawBeta then
        error("Claustrophobic beta-active case did not observe positive beta")
    end
    if spec.name == "inside-agoraphobic-suppressed" then
        local control = T.cases[1]
        if math.abs(c.panicDelta - control.panicDelta) > .15 then
            error("Agoraphobic trait changed the fixed-panic cabin control beyond tolerance")
        end
    elseif spec.name == "inside-claustrophobic-cabin-rate" then
        local control = T.cases[3]
        if c.panicDelta <= control.panicDelta then
            error("Claustrophobic native tick did not add panic over the same-time unchanged control")
        end
    elseif spec.name == "inside-near-cap-claustrophobic" then
        local cappedAtSource = false
        for _, s in ipairs(c.samples) do cappedAtSource = cappedAtSource or s.panicAfter == 100 end
        if not cappedAtSource then error("near-cap Claustrophobic fixture did not exercise the native cap") end
    end
    c.nativeHookEvidence = { firstSequence = first.sequence, lastSequence = last.sequence,
                             agoraSuppressedObserved = suppressed, maximumClaustroAdded = added,
                             area = first.area, multiplier = first.multiplier,
                             firstReceipt = first.info, lastReceipt = last.info }
    T.currentPhase = nil
    beginPhase(index + 1)
end

local function tick()
    assertFixture()
    local now = timestamp()
    if now > phaseDeadline then error("timed out in native phobia phase " .. tostring(T.currentPhase)) end
    if now - sampleAt >= SAMPLE_MS then sample() end
    local index = phaseIndex
    if now - phaseAt >= phases[index].duration then finishPhase(index) end
end

local ok, err = pcall(function()
    assert(not isClient() and not isServer(), "this acceptance fixture requires single-player mode")
    assert(MELensRV and MELensRV.phobiaInfo, "native phobia diagnostic probe is unavailable")
    assert(MEMCNativeLab and MEMCNativeLab.releaseKeys, "isolated native test helper is unavailable")
    player = getPlayer()
    assert(player, "no local player")
    vehicle = MELensTest and MELensTest.vehicle
    assert(vehicle and player:getVehicle() == vehicle and M.isStanding(player),
        "enter MELensTest.vehicle and stand in its cabin before loading this fixture")
    profile = M.profileFor(vehicle)
    assert(profile and profile.kind == "cargo" and vehicle:getScript():getFullName() == "Base.87fordF700box",
        "expected the prepared F700 cargo scenario")
    local traits = player:getCharacterTraits()
    local godOk, godMode = pcall(function() return player:isGodMod() end)
    assert(godOk, "cannot capture the disposable player's God Mode state")
    original = {
        agora = traits:get(CharacterTrait.AGORAPHOBIC) == true,
        claustro = traits:get(CharacterTrait.CLAUSTROPHOBIC) == true,
        panic = player:getStats():get(CharacterStat.PANIC),
        beta = player:getBetaEffect(), betaDelta = player:getBetaDelta(), godMode = godMode,
    }
    T.original = original
    -- Screenshot setup enables God Mode; disable it so native panic updates run.
    player:setGodMod(false)
    T.vehicleId = vehicle:getId()
    T.profile = profile.name
    T.profileScript = vehicle:getScript():getFullName()
    expectedSeat = vehicle:getScript():getPassenger(vehicle:getSeat(player)):getId()
    T.expectedSeatId = expectedSeat
    T.startedAt = timestamp()
    beginPhase(1)
    callback = function()
        local tickOk, tickErr = pcall(tick)
        if not tickOk then fail(tickErr) end
    end
    Events.OnTick.Add(callback)
end)

if not ok then
    stop("failed", err)
end

return { status = T.status, vehicleId = T.vehicleId, profile = T.profile }

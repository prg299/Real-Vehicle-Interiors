-- Single-player native keyboard acceptance for cabin idle, walk and run.
-- Load with the isolated developer endpoint after the test player entered the F700.
-- Positioning uses the authored walk path; movement trials use only native key events.
local M = assert(MELens, "ME: LENS is not loaded")
local T = {
    status = "running",
    scope = "single-player native keyboard idle/walk/run; not multiplayer evidence",
    cases = {},
    samples = {},
}
M.MELensNativeMotionTest = T

local MOVE_MS, SETTLE_MS, PHASE_TIMEOUT_MS = 1200, 400, 60000
local START_X, START_Z, APPROACH_Z = 0, -0.3, 0.3
local player, vehicle, profile, runKey
local selected, state, stateAt, stateDeadline, phaseStart
local directionKeys = {}
local callback

local function timestamp()
    return getTimestampMs()
end

local function binding(name)
    local core = getCore()
    local key = core:getKey(name)
    if key and key > 0 then return key end
    if core.getAltKey then
        key = core:getAltKey(name)
        if key and key > 0 then return key end
    end
    return 0
end

local function current()
    local d = M.debugState()
    local cabin = player:getVariableString("MELensCabin")
    local animOk, anim = pcall(function() return MELensRV.animInfo(player) end)
    return {
        t = timestamp(),
        x = d.x,
        z = d.z,
        facing = d.facing,
        standing = d.standing == true,
        moving = d.moving == true,
        running = d.running == true,
        pose = d.pose or "",
        cabin = cabin or "",
        animationInfoOk = animOk,
        animationInfo = animOk and anim or tostring(anim),
        vehicleId = player:getVehicle() and player:getVehicle():getId() or -1,
        sessionVehicleId = vehicle and vehicle:getId() or -1,
    }
end

local function release()
    pcall(function() MEMCNativeLab.releaseKeys() end)
end

local function stop(status, err)
    release()
    if callback then
        pcall(function() Events.OnTick.Remove(callback) end)
        callback = nil
    end
    T.status = status
    if err then T.error = tostring(err) end
    T.finishedAt = timestamp()
    return T
end

local function fail(message)
    return stop("failed", message)
end

local function checkOccupancy()
    if not player or not vehicle or player:getVehicle() ~= vehicle or not M.isStanding(player) then
        error("player left the F700 standing position during " .. tostring(state))
    end
end

local function distance(a, b)
    local dx, dz = (a.x or 0) - (b.x or 0), (a.z or 0) - (b.z or 0)
    return math.sqrt(dx * dx + dz * dz)
end

local function recordSample()
    local s = current()
    T.samples[#T.samples + 1] = s
    if state == "active-walk" and s.pose == "Walk" and s.cabin == "Walk" then
        T.cases.walk.walkPoseObserved = true
    elseif state == "active-run" and s.pose == "Run" and s.cabin == "Run" then
        T.cases.run.runPoseObserved = true
    end
    return s
end

local function beginState(name)
    state = name
    stateAt = timestamp()
    stateDeadline = stateAt + PHASE_TIMEOUT_MS
end

local function startTrial(name)
    release()
    T.currentCase = name
    T.currentCaseSetup = "approach"
    T.currentTarget = { x = START_X, z = APPROACH_Z }
    beginState("preparing") -- consume the native key-up before starting fixture pathing
end

local function requestPath(x, z, stepName)
    M.walkTo(player, x, z)
    T.currentCaseSetup = stepName
    T.currentTarget = { x = x, z = z }
    stateAt = timestamp()
    stateDeadline = stateAt + PHASE_TIMEOUT_MS
end

local function chooseDirection()
    local combos = {
        { names = { "Forward" }, ix = 0, iy = -1 },
        { names = { "Backward" }, ix = 0, iy = 1 },
        { names = { "Left" }, ix = -1, iy = 0 },
        { names = { "Right" }, ix = 1, iy = 0 },
        { names = { "Forward", "Left" }, ix = -1, iy = -1 },
        { names = { "Forward", "Right" }, ix = 1, iy = -1 },
        { names = { "Backward", "Left" }, ix = -1, iy = 1 },
        { names = { "Backward", "Right" }, ix = 1, iy = 1 },
    }
    local rows = {}
    for _, combo in ipairs(combos) do
        local wx, wy = combo.iy + combo.ix, combo.iy - combo.ix
        local length = math.sqrt(wx * wx + wy * wy)
        wx, wy = wx / length, wy / length
        local a, b = Vector3f.new(), Vector3f.new()
        vehicle:getLocalPos(player:getX(), player:getY(), 0, a)
        vehicle:getLocalPos(player:getX() + wx, player:getY() + wy, 0, b)
        local dx, dz = b:x() - a:x(), b:z() - a:z()
        local magnitude = math.sqrt(dx * dx + dz * dz)
        if magnitude > 1e-6 then dx, dz = dx / magnitude, dz / magnitude end
        local free = 0
        for step = 0.04, 3.2, 0.04 do
            if not M.walkableAt(profile, START_X + dx * step, START_Z + dz * step) then break end
            free = step
        end
        local codes = {}
        local enabled = true
        for _, name in ipairs(combo.names) do
            local code = binding(name)
            codes[#codes + 1] = code
            if code <= 0 or code >= 256 then enabled = false end
        end
        local row = {
            names = combo.names, codes = codes, ix = combo.ix, iy = combo.iy,
            localX = dx, localZ = dz, free = free, enabled = enabled,
        }
        rows[#rows + 1] = row
        -- Exclude near-diagonal motion and routes shorter than the timed run trial.
        if enabled and dz < -0.94 and math.abs(dx) < 0.34 and free >= 3.0 then
            if not selected or free > selected.free then selected = row end
        end
    end
    T.routeCandidates = rows
    if not selected then error("no configured key/chord maps to a clear, nearly straight local -Z route") end
    directionKeys = selected.codes
    runKey = binding(KeybindId and KeybindId.RUN or "Run")
    if runKey <= 0 or runKey >= 256 then error("configured Run key is unavailable") end
    T.selectedRoute = selected
    T.runKey = runKey
end

local function beginActive(name)
    release()
    if name ~= "idle" then
        for _, code in ipairs(directionKeys) do MEMCNativeLab.holdKey(code, MOVE_MS) end
        if name == "run" then MEMCNativeLab.holdKey(runKey, MOVE_MS) end
    end
    local sample = current()
    local c = {
        durationMs = MOVE_MS,
        start = sample,
        startAt = sample.t,
        elapsedMs = 0,
        walkPoseObserved = false,
        runPoseObserved = false,
    }
    T.cases[name] = c
    phaseStart = sample.t
    beginState("active-" .. name)
    stateDeadline = stateAt + MOVE_MS + 1500
end

local function finishActive(name)
    release()
    local c = T.cases[name]
    c.finish = current()
    c.elapsedMs = c.finish.t - c.startAt
    c.distance = distance(c.finish, c.start)
    c.samples = 0
    for _, sample in ipairs(T.samples) do
        if sample.t >= c.startAt and sample.t <= c.finish.t then c.samples = c.samples + 1 end
    end
    if c.elapsedMs < 1050 or c.elapsedMs > 1500 then
        error(string.format("%s trial elapsed %d ms, outside the 1200 ms acceptance window", name, c.elapsedMs))
    end
    if name == "idle" then
        if c.distance > 0.04 then error("idle control drift exceeded 0.04 tiles: " .. c.distance) end
        startTrial("walk")
    elseif name == "walk" then
        if c.distance < 0.25 then error("native walking input produced too little movement: " .. c.distance) end
        if not c.walkPoseObserved then error("Walk pose was not observed during the native walk trial") end
        startTrial("run")
    else
        if c.distance < 0.25 then error("native Run input produced too little movement: " .. c.distance) end
        if not c.runPoseObserved then error("Run pose was not observed during the native Run trial") end
        c.walkDistance = T.cases.walk.distance
        c.runToWalkRatio = c.distance / math.max(c.walkDistance, 1e-6)
        if c.runToWalkRatio < 1.30 then
            error(string.format("run displacement %.3f was less than 1.30x walk %.3f", c.distance, c.walkDistance))
        end
        T.acceptance = {
            idleDriftAtMost = 0.04,
            walkDistanceAtLeast = 0.25,
            runDistanceAtLeast = 0.25,
            runToWalkRatioAtLeast = 1.30,
            walkPoseObserved = T.cases.walk.walkPoseObserved,
            runPoseObserved = c.runPoseObserved,
            standaloneOnly = true,
        }
        beginState("release")
    end
end

local function tick()
    checkOccupancy()
    local now = timestamp()
    if now > stateDeadline then error("timed out in state " .. tostring(state)) end

    if state == "preparing" then
        if now - stateAt < SETTLE_MS then return end
        M.walkTo(player, START_X, APPROACH_Z)
        beginState("setup")
        return
    end

    if state == "setup" then
        local d = M.debugState()
        if d.pathing then return end
        local target = T.currentTarget
        if math.abs((d.x or 999) - target.x) > 0.10 or math.abs((d.z or 999) - target.z) > 0.10 then
            error(string.format("path setup stopped short of target %.2f,%.2f (at %.2f,%.2f)",
                target.x, target.z, d.x or -999, d.z or -999))
        end
        if T.currentCaseSetup == "approach" then
            requestPath(START_X, START_Z, "start")
            return
        end
        local facing = math.abs(math.abs(d.facing or 0) - math.pi)
        if facing > 0.05 then return end -- let the ordinary turn finish before measuring either trial
        T.setupPosition = { x = d.x, z = d.z, facing = d.facing }
        beginState("settle")
        stateDeadline = stateAt + PHASE_TIMEOUT_MS
        return
    end

    if state == "settle" then
        if now - stateAt < SETTLE_MS then return end
        local name = T.currentCase
        if name == "idle" then
            beginActive("idle")
        elseif name == "walk" then
            beginActive("walk")
        else
            beginActive("run")
        end
        return
    end

    if state == "release" then
        if now - stateAt < SETTLE_MS then return end
        local s = current()
        assert(s.pose == "Idle" and not s.moving and not s.running,
            "releasing native movement keys did not return to Idle")
        T.release = s
        stop("passed")
        return
    end

    if state == "active-idle" or state == "active-walk" or state == "active-run" then
        recordSample()
        local name = string.sub(state, 8)
        if now - phaseStart >= MOVE_MS then finishActive(name) end
        return
    end

    error("unknown FSM state " .. tostring(state))
end

local ok, err = pcall(function()
    assert(not isClient() and not isServer(), "this fixture is single-player only")
    player = getPlayer()
    assert(player, "no local player")
    vehicle = MELensTest and MELensTest.vehicle
    assert(vehicle and player:getVehicle() == vehicle and M.isStanding(player),
        "enter MELensTest.vehicle and stand in its cabin before loading this fixture")
    profile = M.profileFor(vehicle)
    assert(profile and profile.kind == "cargo", "expected the F700 cargo profile")
    assert(MEMCNativeLab and MEMCNativeLab.holdKey and MEMCNativeLab.releaseKeys,
        "isolated native keyboard adapter is unavailable")
    assert(MELensRV and MELensRV.animInfo, "ME: LENS animation diagnostics are unavailable")
    chooseDirection()
    T.vehicleId = vehicle:getId()
    T.profile = profile.name
    T.startedAt = timestamp()
    startTrial("idle")
    callback = function()
        local tickOk, tickErr = pcall(tick)
        if not tickOk then fail(tickErr) end
    end
    Events.OnTick.Add(callback)
end)

if not ok then
    stop("failed", err)
end

return { status = T.status, vehicleId = T.vehicleId, route = T.selectedRoute }

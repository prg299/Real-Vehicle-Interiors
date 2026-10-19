-- Play the game's bed clips before committing sleep or switching back to standing.
MELens = MELens or {}
local M = MELens
local B = { states = {}, gettingUp = {} }
M.Bed = B

local function phase(s, value)
    s.phase = value
    s.player:setVariable("MELensBed", value)
    s.player:setVariable("MELensBedFinished_" .. value, false)
end

function B.clear(player)
    B.states[player] = nil
    player:clearVariable("MELensBed")
    for _, name in ipairs({ "Enter", "Awake", "Sleep", "Asleep", "Wake", "Exit" }) do
        player:clearVariable("MELensBedFinished_" .. name)
    end
    player:clearVariable("MELensBedSide")
end

function B.reset(player)
    B.clear(player)
    B.gettingUp[player] = nil
    player:clearVariable("MELensBedGetUp")
    player:clearVariable("MELensBedGetUpReady")
end

function B.begin(player, vehicle, seat, place, onSleep, standX, standZ, floorY)
    local angle = math.atan2(place.headZ, place.headX)
    -- The left/right clips turn 90 degrees as the character sits onto the mattress.
    local turn = angle - math.pi
    local dx, dz = -math.sin(turn) * 0.2739 * 1.5, math.cos(turn) * 0.2739 * 1.5
    local side = "Left"
    if dx * place.outX + dz * place.outZ > 0 then
        side, turn = "Right", angle
        dx, dz = -math.sin(turn) * 0.2739 * 1.5, math.cos(turn) * 0.2739 * 1.5
    end
    local s = { player = player, vehicle = vehicle, seat = seat, place = place,
        entryTurn = turn, dx = dx, dz = dz, side = side, onSleep = onSleep,
        standX = standX or place.x - dx, standZ = standZ or place.z - dz, floorY = floorY or place.y }
    B.states[player] = s
    player:setVariable("MELensBedSide", side)
    phase(s, "Enter")
end

function B.ensure(player, vehicle, seat, place)
    local s = B.states[player]
    if s and s.vehicle == vehicle and s.seat == seat then return s end
    -- A saved occupant resumes on the bed; replaying get-in would start them standing.
    B.begin(player, vehicle, seat, place)
    s = B.states[player]
    phase(s, player:isAsleep() and "Asleep" or "Awake")
    return s
end

function B.getUp(player, after)
    local s = B.states[player]
    if not s then return false end
    if not s.after then s.after = after end
    if M.seatStandPoint and M.nearestWalkableAt then
        local profile = M.profileFor(s.vehicle)
        local x, z = M.seatStandPoint(s.vehicle, profile, s.seat)
        if x then s.standX, s.standZ = M.nearestWalkableAt(profile, x, z) end
    end
    if s.phase == "Sleep" then s.onSleep = nil end
    if s.phase == "Awake" then phase(s, "Exit") end
    return true
end

function B.sleep(player, after)
    local s = B.states[player]
    if not s or s.phase ~= "Awake" then return false end
    s.onSleep = after
    phase(s, "Sleep")
    return true
end

function B.placement(player, vehicle, seat, place)
    local s = B.ensure(player, vehicle, seat, place)
    local progress = 0
    if MELensRV and MELensRV.animationProgress then
        local clip = s.phase == "Enter" and ("Bob_GetInBed_" .. s.side)
            or s.phase == "Exit" and ("Bob_GetOutBed" .. s.side)
        if clip then progress = math.max(0, math.min(1, MELensRV.animationProgress(player, clip))) end
    end
    if s.phase == "Enter" then
        return { pose = place.pose,
            x = s.standX + (place.x - s.dx - s.standX) * progress,
            y = s.floorY + (place.y - s.floorY) * progress,
            z = s.standZ + (place.z - s.dz - s.standZ) * progress, turn = s.entryTurn }
    elseif s.phase == "Exit" then
        local rx = s.side == "Left" and 0.2205 or -0.2869
        local rz, turn = 0.2094, place.turn
        local dx, dz = (math.cos(turn) * rx - math.sin(turn) * rz) * 1.5,
                       (math.sin(turn) * rx + math.cos(turn) * rz) * 1.5
        return { pose = place.pose,
            x = place.x + (s.standX - dx - place.x) * progress,
            y = place.y + (s.floorY - place.y) * progress,
            z = place.z + (s.standZ - dz - place.z) * progress, turn = turn }
    end
    return place
end

function B.update(player)
    local s = B.states[player]
    if not s then return end
    if player:isDead() or player:getVehicle() ~= s.vehicle or s.vehicle:getSeat(player) ~= s.seat then
        B.clear(player)
        return
    end
    local finished = player:getVariableBoolean("MELensBedFinished_" .. s.phase)
    if finished and s.phase == "Enter" then
        phase(s, "Awake")
        if s.after then phase(s, "Exit")
        elseif s.onSleep then phase(s, "Sleep") end
    elseif finished and s.phase == "Sleep" then
        local after = s.onSleep
        s.onSleep = nil
        phase(s, "Asleep")
        if after then after() end
        if not player:isAsleep() then phase(s, "Wake") end
    elseif s.phase == "Asleep" and not player:isAsleep() then
        phase(s, "Wake")
    elseif finished and s.phase == "Wake" then
        phase(s, s.after and "Exit" or "Awake")
    elseif finished and s.phase == "Exit" then
        local after = s.after
        local turn = s.place.turn + (s.side == "Left" and -math.pi / 2 or math.pi / 2)
        B.clear(player)
        B.gettingUp[player] = true
        player:setVariable("MELensBedGetUp", true)
        player:setVariable("MELensBedGetUpReady", false)
        if after then after(turn) end
    end
end

Events.OnTick.Add(function()
    for player in pairs(B.states) do B.update(player) end
    for player in pairs(B.gettingUp) do
        if player:isDead() or not player:getVehicle() or player:getVariableBoolean("MELensBedGetUpReady") then
            player:clearVariable("MELensBedGetUp")
            player:clearVariable("MELensBedGetUpReady")
            B.gettingUp[player] = nil
        end
    end
end)

if Events.OnGameStart then
    Events.OnGameStart.Add(function()
        B.states, B.gettingUp = {}, {}
        local player = getSpecificPlayer(0)
        if player then B.reset(player) end
    end)
end

-- Developer test endpoint, server side (test servers only, never shipped): spawns a vehicle for a
-- multiplayer test, as an admin's client asks (sendClientCommand(player, "MELensDev", "spawn",
-- { name = "Base.Trailer54FlyingCloud22", x = ..., y = ... })). The steps of the game's own /addvehicle
-- command (AddVehicleCommand): a new vehicle on the square, added to the world and to the vehicle database.
local function spawn(name, x, y)
    local map = ServerMap and ServerMap.instance
    local square = map and map:getGridSquare(x, y, 0) or getCell():getGridSquare(x, y, 0)
    if not square then return nil, "no square" end
    local v = BaseVehicle.new(getWorld():getCell())
    v:setScriptName(name)
    v:setX(x - 1.0)
    v:setY(y - 0.1)
    v:setZ(0.2)
    if not IsoChunk.doSpawnedVehiclesInInvalidPosition(v) then return nil, "invalid position" end
    v:setSquare(square)
    square:getChunk():getVehicles():add(v)
    v:setChunk(square:getChunk())
    v:addToWorld()
    VehiclesDB2.instance:addVehicle(v)
    v:setCurrentKey(v:createVehicleKey())
    v:repair()
    -- unlocked for the test, and the players told (they got the vehicle with its doors as it was made)
    for i = 0, v:getPartCount() - 1 do
        local part = v:getPartByIndex(i)
        local door = part:getDoor()
        if door and door:isLocked() then
            door:setLocked(false)
            v:transmitPartDoor(part)
        end
    end
    return v
end

-- Runs a piece of Lua here for an admin's client and sends the answer back, so a multiplayer test can look at what
-- the server holds: sendClientCommand(player, "MELensDev", "eval", { id = 1, code = "return 1" }); the answer
-- arrives as the server command "result" with the same id (the client side stores it in MELensDevResult).
local function eval(player, args)
    local chunk, err = loadstring(tostring(args.code or ""))
    local text
    if not chunk then
        text = "compile error: " .. tostring(err)
    else
        local ok, value = pcall(chunk)
        text = ok and tostring(value) or ("error: " .. tostring(value))
    end
    print("[RealVehicleInteriors_Dev] eval " .. tostring(args.id) .. " -> " .. text)
    sendServerCommand(player, "MELensDev", "result", { id = args.id, text = text })
end

local function onClientCommand(module, command, player, args)
    if module ~= "MELensDev" or type(args) ~= "table" then return end
    if not player or player:getAccessLevel() ~= "admin" then return end
    if command == "eval" then
        eval(player, args)
        return
    end
    if command ~= "spawn" then return end
    if MELensDevSpawn then
        -- the game's own steps, in the endpoint's Java (needs ZombieBuddy on the server: dev\mp_server.ps1)
        print("[RealVehicleInteriors_Dev] spawn " .. tostring(args.name) .. " -> " .. tostring(MELensDevSpawn.add(tostring(args.name),
            math.floor(tonumber(args.x) or 0), math.floor(tonumber(args.y) or 0))))
        return
    end
    -- the first free place on rings round the asked one (houses and fences make most of a town invalid)
    local x0, y0 = math.floor(tonumber(args.x) or 0), math.floor(tonumber(args.y) or 0)
    local ok, v, why
    for r = 0, 30, 3 do
        for dx = -r, r, 3 do
            for _, dy in ipairs({ -r, r }) do
                ok, v, why = pcall(spawn, tostring(args.name), x0 + dx, y0 + dy)
                if ok and v then break end
            end
            if ok and v then break end
        end
        if ok and v then break end
    end
    print("[RealVehicleInteriors_Dev] serverMap=" .. tostring(ServerMap ~= nil) .. " spawn " .. tostring(args.name) .. " ok=" .. tostring(ok) .. " -> " .. tostring(ok and v and v:getId() or v) .. " " .. tostring(why))
end
Events.OnClientCommand.Add(onClientCommand)

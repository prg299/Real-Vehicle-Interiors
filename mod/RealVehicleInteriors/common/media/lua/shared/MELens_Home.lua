--
-- ME: LENS home comforts, the things that make a vehicle yours:
--
--   * a name (vehicle modData MELensName), shown on the dashboard;
--   * the paint on its walls (vehicle modData MELensPaint = { r, g, b }), applied by the Java part's shell shader;
--   * rain running into the water tank, when the vehicle stands outside (every ten minutes, where the game runs
--     vehicle Lua: single player or the server), as tainted water like the game's rain barrels;
--   * shore power: a generator running within a few tiles powers the fridge, stove and heater, as a plug would.
--
require "MELens_Utilities"

MELens = MELens or {}
local M = MELens
M.Home = M.Home or {}
local H = M.Home
local U = M.Utilities

H.NAME_KEY = "MELensName"
H.PAINT_KEY = "MELensPaint"
H.NAME_MAX = 24

------------------------------------------------------------------------------------
-- Name
------------------------------------------------------------------------------------

-- A name as it may be kept: no control characters, trimmed, at most NAME_MAX characters.
function H.cleanName(text)
    text = tostring(text or "")
    text = string.gsub(text, "[%c]", "")
    text = string.gsub(text, "^%s+", "")
    text = string.gsub(text, "%s+$", "")
    if string.len(text) > H.NAME_MAX then
        text = string.sub(text, 1, H.NAME_MAX)
    end
    return text
end

-- The name given to a vehicle, or nil.
function H.givenName(vehicle)
    local name = vehicle:getModData()[H.NAME_KEY]
    if type(name) == "string" and name ~= "" then return name end
    return nil
end

-- What it is called: its name, else the kind of vehicle it is.
function H.name(vehicle, profile)
    return H.givenName(vehicle) or (profile or M.profileFor(vehicle) or {}).name or ""
end

-- Sets (or with an empty text, removes) the name. On a server the vehicle's data goes out to everyone.
function H.setName(vehicle, text)
    local name = H.cleanName(text)
    vehicle:getModData()[H.NAME_KEY] = name ~= "" and name or nil
    if isServer() then
        vehicle:transmitModData()
    end
    return name
end

------------------------------------------------------------------------------------
-- Paint
------------------------------------------------------------------------------------

-- The colour of the walls (0..1), or nil for the walls it came with.
function H.paint(vehicle)
    local p = vehicle:getModData()[H.PAINT_KEY]
    if type(p) == "table" and tonumber(p.r) and tonumber(p.g) and tonumber(p.b) then
        return tonumber(p.r), tonumber(p.g), tonumber(p.b)
    end
    return nil
end

function H.setPaint(vehicle, r, g, b)
    if r == nil then
        vehicle:getModData()[H.PAINT_KEY] = nil
    else
        local function clamp(v) return math.max(0, math.min(1, tonumber(v) or 0)) end
        vehicle:getModData()[H.PAINT_KEY] = { r = clamp(r), g = clamp(g), b = clamp(b) }
    end
    if isServer() then
        vehicle:transmitModData()
    end
end

-- Units of paint one coat of the walls takes (a can holds ten).
H.PAINT_USES = 4

-- The paints the game knows (ISPaintMenu), for the dashboard: { paint = "PaintRed", text, color = { r, g, b } }.
function H.paints()
    require "BuildingObjects/ISPaintMenu"
    return ISPaintMenu and ISPaintMenu.PaintMenuItems or {}
end

function H.isBrush(item)
    local t = item and item:getType()
    return t == "Paintbrush" or t == "PaintbrushCrafted"
end

-- A paintbrush you carry, or nil.
function H.brushOf(player)
    return player:getInventory():getFirstEvalRecurse(function(item) return H.isBrush(item) end)
end

------------------------------------------------------------------------------------
-- Shore power: a generator running beside the vehicle
------------------------------------------------------------------------------------

H.SHORE_RANGE = 4        -- tiles round the vehicle's middle
local shore = {}

local function nowMs()
    return getTimestampMs and getTimestampMs() or 0
end

-- Whether a generator (the game's own, on the ground) with petrol is running within reach of the vehicle.
function H.shorePower(vehicle)
    if not M.sandbox("ShorePower", true) then return false end
    local id = vehicle:getId()
    local now = nowMs()
    local cached = shore[id]
    if cached and now - cached.t < 2000 then
        return cached.on
    end
    local on = false
    local square = vehicle:getSquare()
    local cell = getCell()
    if square and cell then
        local cx, cy, cz = square:getX(), square:getY(), square:getZ()
        local r = H.SHORE_RANGE
        for dx = -r, r do
            for dy = -r, r do
                local sq = cell:getGridSquare(cx + dx, cy + dy, cz)
                local generator = sq and sq:getGenerator()
                if generator and generator:isActivated() and generator:getFuel() > 0 then
                    on = true
                    break
                end
            end
            if on then break end
        end
    end
    shore[id] = { t = now, on = on }
    return on
end

------------------------------------------------------------------------------------
-- Rain
------------------------------------------------------------------------------------

-- Litres a roof takes in ten minutes of the heaviest rain, by kind of vehicle.
local ROOF = { camper = 2.5, bus = 4.0, cargo = 3.5 }

-- Every ten minutes: vehicles standing outside collect rain. Where the game runs vehicle Lua.
function H.rainTick()
    if isClient() then return end
    if not M.sandbox("RainFillsTank", true) then return end
    local climate = getClimateManager()
    local rain = climate and climate:getRainIntensity() or 0
    if rain <= 0.02 then return end
    local cell = getCell()
    if not cell then return end
    local it = cell:getVehicles():iterator()
    while it:hasNext() do
        local vehicle = it:next()
        local profile = M.profileFor(vehicle)
        local square = profile and vehicle:getSquare()
        if square and square:isOutside() and U.part(vehicle, M.Parts.WATER) then
            -- Roof runoff may refill an empty/dirty tank, but must not silently
            -- contaminate potable water the player deliberately stored.
            local tank = U.waterState(vehicle)
            if tank.water <= 0 or tank.tainted then
                U.changeWater(vehicle, rain * (ROOF[profile.kind] or 2.5), true)
            end
        end
    end
end

-- Every minute: a vehicle whose shore power came or went is woken (its fridge cools or warms at once, as when its
-- own generator starts or stops). Where the game runs vehicle Lua.
function H.shoreTick()
    if isClient() then return end
    local cell = getCell()
    if not cell then return end
    local it = cell:getVehicles():iterator()
    while it:hasNext() do
        local vehicle = it:next()
        local profile = M.profileFor(vehicle)
        if profile then
            shore[vehicle:getId()] = nil                  -- look again, not at the last two seconds
            local on = H.shorePower(vehicle)
            local data = vehicle:getModData()
            if on ~= (data.MELensShore == true) then
                data.MELensShore = on or nil
                if on then
                    U.wake(vehicle)
                    for index = 1, #(profile.spots or {}) do
                        local part = M.Parts.spotPart(vehicle, index)
                        if M.Parts.pieceAt(part) == "fridge" and part:getItemContainer() then
                            part:getItemContainer():setCustomTemperature(U.FRIDGE_COLD)
                        end
                    end
                elseif not U.hasPower(vehicle) then
                    U.powerLost(vehicle)
                end
            end
        end
    end
end

if not H.hooked then
    H.hooked = true
    Events.EveryTenMinutes.Add(function() H.rainTick() end)
    Events.EveryOneMinute.Add(function() H.shoreTick() end)
end

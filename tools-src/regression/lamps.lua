-- Server/SP lamp authority with engine doubles; not native input or live MP proof.
do
    local U = MELens.Utilities
    local names = { "isClient", "isServer", "getGameTime", "getTimestampMs", "getCell", "VehicleUtils" }
    local saved = {}; for _, name in ipairs(names) do saved[name] = _G[name] end
    local client, server, hour, milliseconds = false, true, 100, 10000
    isClient, isServer = function() return client end, function() return server end
    getGameTime = function() return { getWorldAgeHours = function() return hour end } end
    getTimestampMs = function() return milliseconds end
    VehicleUtils = { chargeBattery = function() error("Lamp used the native double-delta helper") end }
    local loaded, cell = {}, {}
    local vehicles = {}
    function vehicles:size() return #loaded end
    function vehicles:iterator()
        local index = 0
        return { hasNext = function() return index < #loaded end,
            next = function() index = index + 1; return loaded[index] end }
    end
    function cell:getVehicles() return vehicles end
    getCell = function() return cell end
    local nextId = 20000
    local function fixture()
        nextId = nextId + 1
        local item = { charge = 0.5, sets = 0, changes = 0 }
        function item:getCurrentUsesFloat() return self.charge end
        -- Native inventory items quantize usedDelta to 1e-5. Tiny continuous
        -- lamp ticks can therefore be rounded away unless production carries
        -- the unapplied fraction between observations.
        function item:setUsedDelta(n)
            local quantized = math.floor(n * 100000 + 0.5) / 100000
            if quantized ~= self.charge then self.changes = self.changes + 1 end
            self.charge = quantized
            self.sets = self.sets + 1
        end
        local battery = { getInventoryItem = function() return item end }
        local v = { id = nextId, data = { MELensLightsHour = -500 }, passengers = {}, wakes = 0, packets = 0 }
        function v:getId() return self.id end
        function v:getScript() return { getFullName = function() return "Base.87fordF700box" end } end
        function v:getSquare() if self.unloaded then return nil end; return {} end
        function v:getModData() return self.data end
        function v:getBattery() if self.noBattery then return nil end; return battery end
        function v:getMaxPassengers() return 4 end
        function v:getCharacter(seat) return self.passengers[seat] end
        function v:getPartById(_) return nil end
        function v:setNeedPartsUpdate(value) self.awake = value; self.wakes = self.wakes + 1 end
        function v:transmitPartUsedDelta(part) check(part == battery, "wrong lamp battery transmitted"); self.packets = self.packets + 1 end
        function v:transmitModData() end
        local p = { vehicle = v }
        function p:getVehicle() return self.vehicle end
        function p:isDead() return self.dead == true end
        v.passengers[2] = p
        return { v = v, item = item, p = p }
    end
    local function near(actual, expected, label)
        check(math.abs(actual - expected) < 0.00000001, label .. ": " .. tostring(actual))
    end
    local f = fixture(); loaded = { f.v }
    emit("OnTick")
    check(f.v.awake and U.busy(f.v), "occupied lamps did not wake parked utility updates")
    near(f.item.charge, 0.5, "first observation catches up saved light-hour value")
    hour, milliseconds = 101, 10100; emit("OnTick")
    near(f.item.charge, 0.5, "lamp scan ignores throttle")
    milliseconds = 10500; emit("OnTick")
    near(f.item.charge, 0.4982, "one authoritative hour drains incorrect amount")
    check(f.item.sets == 1 and f.v.packets == 1, "server battery mutation/replication count")
    emit("OnTick")
    near(f.item.charge, 0.4982, "duplicate tick double drains")

    -- Multiple people and sync-position keepalives still share one clock.
    f = fixture(); hour = 200; U.observeLamps(f.v)
    local second = { getVehicle = function() return f.v end, isDead = function() return false end }
    f.v.passengers[3] = second
    hour = 201; U.primeLamps(f.v)
    near(f.item.charge, 0.5, "sync keepalive mutated battery")
    U.observeLamps(f.v); U.observeLamps(f.v)
    near(f.item.charge, 0.4982, "two occupants or duplicate observation multiply lamp drain")
    f.v.passengers[2], f.v.passengers[3] = nil, nil
    hour = 202; U.observeLamps(f.v)
    near(f.item.charge, 0.4982, "unoccupied vehicle drained")
    check(not U.busy(f.v), "empty vehicle remains busy only for lamps")
    f.v.passengers[2] = f.p; hour = 500; U.observeLamps(f.v)
    near(f.item.charge, 0.4982, "entry catches up time spent away")
    hour = 501; U.observeLamps(f.v)
    near(f.item.charge, 0.4964, "re-entry failed to resume drain")

    f.v.data.MELensLightsOff = true; hour = 502; U.observeLamps(f.v, true)
    local before = f.item.charge
    hour = 600; U.observeLamps(f.v)
    near(f.item.charge, before, "switched-off lamps drained")
    f.v.data.MELensLightsOff = nil; U.observeLamps(f.v, true)
    near(f.item.charge, before, "switch-on catches up switched-off time")
    hour = 601; U.observeLamps(f.v)
    near(f.item.charge, before - 0.0018, "switch-on failed to resume lamps")

    -- Native usedDelta quantization must not discard sub-quantum drain every
    -- tick. One continuous game-hour across many 3.6-second observations should
    -- aggregate to the configured rate within one native 1e-5 step.
    f = fixture(); hour = 0; U.observeLamps(f.v)
    local startCharge = f.item.charge
    for i = 1, 1000 do
        hour = i / 1000
        U.observeLamps(f.v)
    end
    local aggregateDebit = startCharge - f.item.charge
    check(math.abs(aggregateDebit - U.LAMP_DRAIN_PER_HOUR) <= 0.00001,
        "quantized battery setter discarded continuous lamp drain: " .. tostring(aggregateDebit))
    check(f.v.packets == f.item.changes and f.item.changes > 1 and f.item.sets >= f.item.changes,
        "quantized lamp drain did not replicate only actual battery changes")

    -- Pending sub-quantum drain belongs only to a continuous occupied/on period.
    -- Leaving or switching off discards it; re-entry/on begins a fresh baseline.
    f = fixture(); hour = 0; U.observeLamps(f.v)
    for i = 1, 2 do hour = i / 1000; U.observeLamps(f.v) end
    local pendingCharge = f.item.charge
    f.v.passengers[2] = nil; hour = 0.004; U.observeLamps(f.v)
    hour = 100; U.observeLamps(f.v)
    f.v.passengers[2] = f.p; U.observeLamps(f.v)
    for i = 1, 2 do hour = 100 + i / 1000; U.observeLamps(f.v) end
    near(f.item.charge, pendingCharge, "unoccupied gap carried pending sub-quantum drain into re-entry")
    f.v.data.MELensLightsOff = true; U.observeLamps(f.v, true)
    hour = 200; U.observeLamps(f.v)
    f.v.data.MELensLightsOff = nil; U.observeLamps(f.v, true)
    for i = 1, 2 do hour = 200 + i / 1000; U.observeLamps(f.v) end
    near(f.item.charge, pendingCharge, "switched-off gap carried pending sub-quantum drain into next on period")

    before = f.item.charge; hour = 10; U.observeLamps(f.v)
    near(f.item.charge, before, "backwards world time changed battery")
    hour = 11; U.observeLamps(f.v)
    near(f.item.charge, before - 0.0018, "backwards world time failed to rebase")

    f.item.charge = 0.0001; hour = 12; U.observeLamps(f.v)
    check(f.item.charge == 0, "lamp drain underflows battery")
    hour = 800; U.observeLamps(f.v)
    check(f.item.charge == 0 and not U.busy(f.v), "empty battery drains/keeps parked vehicle busy")
    f.item.charge = 0.5; U.observeLamps(f.v)
    near(f.item.charge, 0.5, "new battery catches up empty-battery time")
    f.v.unloaded = true; hour = 801; U.observeLamps(f.v)
    f.v.unloaded = nil; hour = 900; U.observeLamps(f.v)
    near(f.item.charge, 0.5, "unloaded vehicle retained old lamp clock")
    f.p.dead = true; hour = 901; U.observeLamps(f.v)
    near(f.item.charge, 0.5, "dead passenger drains lamps")
    f.p.dead = nil; f.p.vehicle = nil; U.observeLamps(f.v)
    check(not U.lampsActive(f.v), "stale passenger membership counts as occupied")

    -- Client calls do not mutate either the battery or authority clock.
    f = fixture(); hour = 1000; U.observeLamps(f.v)
    client = true; hour = 1001
    U.observeLamps(f.v); U.lampTick()
    check(f.item.sets == 0 and not U.lampsActive(f.v), "client mutated lamp battery")
    client = false; U.observeLamps(f.v)
    near(f.item.charge, 0.4982, "client call altered authoritative baseline")
    server = false; hour = 1002; local packets = f.v.packets
    U.observeLamps(f.v)
    near(f.item.charge, 0.4964, "single-player authority did not drain")
    check(f.v.packets == packets, "single player sent server battery packet")

    -- Real light-switch completion rebases even if already on; confirmation never
    -- drains the preceding interval or catches up an off interval.
    f = fixture(); hour = 1100; U.observeLamps(f.v)
    local switch = setmetatable({ character = f.p, vehicle = f.v, which = "lights", on = true }, { __index = MELensSwitch })
    hour = 1200
    check(switch:complete(), "lights switch completion failed")
    near(f.item.charge, 0.5, "forced switch boundary drains old interval")
    hour = 1201; U.observeLamps(f.v)
    near(f.item.charge, 0.4982, "forced switch boundary did not rebase clock")

    -- End-of-pass cleanup discards absent vehicles; work is capped per frame.
    server = true; hour, milliseconds = 2000, 50000
    before = f.item.charge
    loaded = {}; emit("OnTick")
    loaded = { f.v }; hour, milliseconds = 3000, 50500; emit("OnTick")
    near(f.item.charge, before, "returning unloaded vehicle catches up")
    local many = {}; for i = 1, 65 do many[i] = fixture() end
    loaded = {}; for i, value in ipairs(many) do loaded[i] = value.v end
    hour, milliseconds = 4000, 51000; emit("OnTick")
    check(many[64].v.wakes == 1 and many[65].v.wakes == 0, "lamp scan exceeds 64 vehicles per frame")
    emit("OnTick")
    check(many[65].v.wakes == 1, "bounded lamp scan never reaches later vehicles")
    for _, name in ipairs(names) do _G[name] = saved[name] end
end

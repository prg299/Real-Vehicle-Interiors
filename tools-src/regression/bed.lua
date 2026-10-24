-- Production bed sequencing with engine doubles; native clips/input are checked separately.
do
    local B = MELens.Bed
    local oldJava = MELensRV
    local progress = 0
    MELensRV = { animationProgress = function() return progress end }
    local function fixture()
        local p = { vars = {}, asleep = false }
        local v = { getSeat = function() return 3 end }
        p.vehicle = v
        function p:getVehicle() return self.vehicle end
        function p:isDead() return false end
        function p:isAsleep() return self.asleep end
        function p:setVariable(k, x) self.vars[k] = x end
        function p:clearVariable(k) self.vars[k] = nil end
        function p:getVariableBoolean(k) return self.vars[k] == true end
        local place = { pose = "MELensBed", kind = "bed", x = 1, y = -0.0634, z = 2,
            headX = 0, headZ = 1, outX = -1, outZ = 0, turn = math.pi }
        return p, v, place
    end
    local function finish(p)
        p.vars["MELensBedFinished_" .. p.vars.MELensBed] = true
        B.update(p)
    end
    local p, v, place = fixture()
    local slept, stood = 0, 0
    B.begin(p, v, 3, place, function() slept = slept + 1; p.asleep = true end, 0, 2, 0)
    check(p.vars.MELensBed == "Enter" and slept == 0, "sleep started before get-in")
    progress = 0
    local start = B.placement(p, v, 3, place)
    check(start.x == 0 and start.z == 2 and start.y == 0, "get-in teleports from its starting point")
    finish(p)
    check(p.vars.MELensBed == "Sleep" and slept == 0, "get-in skipped falling-asleep clip")
    finish(p)
    check(p.vars.MELensBed == "Asleep" and slept == 1, "native sleep not committed exactly once")
    B.update(p)
    check(slept == 1, "native sleep committed twice")
    p.asleep = false
    B.update(p)
    check(p.vars.MELensBed == "Wake", "waking skips wake animation")
    check(B.getUp(p, function() stood = stood + 1 end), "get-up request rejected")
    check(p.vars.MELensBed == "Wake" and stood == 0, "get-up interrupted wake clip")
    finish(p)
    check(p.vars.MELensBed == "Exit" and stood == 0, "wake skips get-out clip")
    finish(p)
    check(stood == 1 and B.states[p] == nil and p.vars.MELensBed == nil, "get-out did not clean up")
    B.update(p)
    check(stood == 1, "get-out callback repeated")
    B.reset(p)
    check(not p.vars.MELensBedGetUp and B.gettingUp[p] == nil, "get-up marker survived reset")

    p, v, place = fixture()
    B.begin(p, v, 3, place)
    B.getUp(p, function() stood = stood + 1 end)
    finish(p)
    check(p.vars.MELensBed == "Exit", "queued movement did not wait for get-in to finish")
    p.vehicle = nil
    B.update(p)
    check(B.states[p] == nil and p.vars.MELensBed == nil, "leaving vehicle retained bed state")

    p, v, place = fixture()
    B.begin(p, v, 3, place, function() slept = slept + 1; p.asleep = true end)
    p.vars.MELensBedFinished_Exit = true -- a fading-out clip from an earlier bed use
    B.update(p)
    check(p.vars.MELensBed == "Enter", "stale get-out event skipped get-in")
    finish(p)
    B.getUp(p, function() end)
    finish(p)
    check(not p.asleep and slept == 1 and p.vars.MELensBed == "Wake", "movement did not cancel falling asleep")
    B.clear(p)

    p, v, place = fixture()
    B.ensure(p, v, 3, place)
    check(p.vars.MELensBed == "Awake", "saved occupant replays get-in")
    B.clear(p)
    p.asleep = true
    B.ensure(p, v, 3, place)
    check(p.vars.MELensBed == "Asleep", "saved sleeper replays get-in")
    B.clear(p)
    MELensRV = oldJava
end

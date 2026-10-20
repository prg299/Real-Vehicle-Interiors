-- Production MELensEnterCabin plus the installed game's inherited perform/stop.
-- No animation event is emitted: standing entry must finish without one.
do
    local function fixture(distance, reject)
        local p = character(900)
        p.xx, p.yy = 0, 0
        function p:getPlayerNum() return 0 end
        p.SetVariable, p.ClearVariable = p.setVariable, p.clearVariable
        function p:triggerMusicIntensityEvent() end
        local position = { getOffset = function() return Vector3f.new() end }
        local v = { seat = 3, animations = 0, sounds = 0, transmissions = 0 }
        function v:getCharacter(seat) return seat == self.seat and self.occupant or nil end
        function v:getScript() return { getFullName = function() return "Base.87fordF700box" end } end
        function v:getPassengerPosition() return position end
        function v:getPassengerPositionWorldPos(_, point) return point:set(distance or 0, 0, 0) end
        function v:enter(seat, chr, offset)
            if reject then return false end
            check(seat == self.seat and offset ~= nil, "walk-in bypassed native offset entry")
            self.occupant, chr.vehicle = chr, self
            return true
        end
        function v:playPassengerSound() self.sounds = self.sounds + 1 end
        function v:playPassengerAnim(_, name)
            check(name == "idle", "walk-in still waits for a seated entry animation")
            self.animations = self.animations + 1
        end
        function v:setCharacterPosition() self.positioned = true end
        function v:transmitCharacterPosition() self.transmissions = self.transmissions + 1 end
        function v:exit(chr) self.occupant, chr.vehicle = nil, nil end
        local a = MELensEnterCabin:new(p, v, 3)
        a.action = { setBlockMovementEtc = function() end }
        return p, v, a
    end
    local p, v, a = fixture()
    check(a:isValid(), "empty standing seat is not enterable")
    p.vars.EnterAnimationFinished = "true"
    a:update()
    check(not a.forced, "stale animation event completed entry from outside")
    a:start()
    check(a:isValid() and p.vars.EnterAnimationFinished == nil, "entry retained stale completion flag")
    check(p.vars.bEnteringVehicle == "true", "entry did not set transition flag")
    local events = #entryEvents
    a:update()
    check(a.forced == 1 and a.performed == 1, "standing entry hangs without an animation event")
    check(p.vars.bEnteringVehicle == nil and p.vars.EnterAnimationFinished == nil,
        "completed entry still blocks standing sync")
    check(v.positioned and v.transmissions == 1 and v.animations == 1,
        "entry skipped native position/idle handoff")
    check(#entryEvents == events + 1 and entryEvents[#entryEvents].name == "OnEnterVehicle",
        "entry did not notify other vehicle mods")

    p, v, a = fixture()
    a:start()
    a:stop() -- Escape retains the game's exit/queue cleanup.
    check(p:getVehicle() == nil and v.occupant == nil and a.stopped == 1, "cancel failed to leave standing seat")
    check(p.vars.bEnteringVehicle == nil and p.vars.EnterAnimationFinished == nil, "cancel retained entry flags")

    p, v, a = fixture(3)
    a:start()
    a:update()
    check(not a:isValid() and not a.forced and p:getVehicle() == nil, "entry from beyond door reach completed")

    p, v, a = fixture(0, true)
    MELens.pendingStand = nil
    a:start()
    a:update()
    check(not a:isValid() and not a.forced and p:getVehicle() == nil, "rejected native entry completed")
    check(p.vars.bEnteringVehicle == nil and MELens.pendingStand == nil, "rejected entry created a standing session")

    p, v, a = fixture()
    v.occupant = character(901)
    check(not a:isValid(), "occupied standing seat accepted another passenger")
    a:update()
    check(not a.forced, "entry completed into someone else's seat")

    p, v, a = fixture()
    a:start()
    p.vehicle = nil -- authoritative rejection after local entry
    check(not a:isValid(), "lost vehicle membership kept entry valid")
    a:update()
    check(not a.forced, "entry completed after vehicle membership was lost")
end

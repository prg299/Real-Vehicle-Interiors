-- Virtual furniture has no IsoObject for the engine's ordinary world picker.
-- Keep normal world clicks on their normal path; fill the same context menu
-- only for an unconsumed short click on interior content with no world pick.
require "MELens_Interact"
MELens = MELens or {}
if not MELens.InteriorContext then
    local C = {}
    MELens.InteriorContext = C
    function C.press()
        C.pressedAt = getTimestampMs()
    end
    function C.release(x, y)
        local pressed = C.pressedAt
        C.pressedAt = nil
        if not pressed or getTimestampMs() - pressed >= 500 then return end
        local player = getSpecificPlayer(0)
        if not player or player:isDead() or player:isAsleep() or player:isAiming()
                or getCore():isDoingTextEntry() or isGamePaused() then return end
        local vehicle = player:getVehicle()
        local profile = MELens.profileFor(vehicle)
        if not profile or MELens.inVanillaSeat(player, vehicle, profile) then return end
        -- ClickObject is Java userdata; its fields are not exposed to Lua.
        -- Any native pick keeps this click on the engine's normal path.
        if UIManager.getPicked() then return end
        local hit = MELens.Interact.pick(vehicle, profile, getMouseXScaled(), getMouseYScaled())
        if not hit then return end
        local context = ISContextMenu.get(0, x, y)
        MELens.Interact.fillMenu(player, context)
        context:setVisible(not context:isEmpty())
    end
    Events.OnRightMouseDown.Add(C.press)
    Events.OnRightMouseUp.Add(C.release)
end

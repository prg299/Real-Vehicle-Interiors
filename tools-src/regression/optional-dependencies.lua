-- A vanilla-only install must retain functional furniture seating. Optional
-- damnlib keeps its original placement when that mod is actually enabled.
do
    local P = MELens.Parts
    local oldActivated, oldDamn = getActivatedMods, DAMN
    local enabled = false
    getActivatedMods = function() return { contains = function(_, id) return id == "damnlib" and enabled end } end
    DAMN = { EnterAnimations = {} } -- stale globals must not activate an absent dependency
    local piece = "dinette"
    local part = { getInventoryItem = function() return { getFullType = function() return P.itemType(piece) end } end }
    local v = { getPartById = function(_, id) if id == P.SPOT .. "1" then return part end end }
    local profile = { floorY = .2, spots = {{ x = 0, z = 0, wall = "left", seats = {"one", "two"} }} }
    check(not P.hasDamnSeats(), "downloaded/stale damnlib globals cannot create a dependency")
    for _, kind in ipairs({"dinette", "medbench", "busseat", "busseat2"}) do
        piece = kind
        enabled = true
        local legacy = P.seatPose(v, profile, "one")
        check(legacy and legacy.pose == "facingLeft", kind .. " retains optional damnlib pose")
        enabled = false
        local native = P.seatPose(v, profile, "one")
        check(native and native.pose == "MELensSeat", kind .. " has an independent seated animation")
        check(native.x == legacy.x and native.z == legacy.z, kind .. " preserves furniture footprint and seat location")
        check(math.abs(native.y + .3154 * 1.5 - legacy.y) < .000001, kind .. " aligns vanilla pelvis to the old seat surface")
        check(math.abs(native.turn - legacy.turn + math.pi / 2) < .000001, kind .. " aligns the vanilla clip's forward axis")
    end
    piece = "bed"
    local bed = P.seatPose(v, profile, "one")
    check(bed and bed.pose == "MELensBed" and bed.kind == "bed", "existing native bed animation stays independent")
    getActivatedMods, DAMN = oldActivated, oldDamn
end

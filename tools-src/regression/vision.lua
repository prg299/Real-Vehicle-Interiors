-- Metadata and lifecycle contracts; native sight/hearing are checked in-game.
do
    local M, saved = MELens, MELensRV
    local received = {}
    MELensRV = { registerVisionHull = function(name, ring, openings)
        check(type(ring)=="string" and string.find(ring,";"),"vision hull serializes its measured outline")
        check(type(openings)=="string","vision openings are explicit even for an opaque body")
        received[name] = true
    end }
    M.Vision.register()
    local count = 0
    for name, profile in pairs(M.Profiles) do
        if profile.shell and profile.walkGrid then
            check(M.VisionGeometry[name] ~= nil and received[name],"missing sight geometry for "..name)
            count = count + 1
        end
    end
    check(count==203,"vision registration lost a supported variant")
    check(received["Base.CarNormal"]==nil,"unsupported car acquired interior concealment")
    check(string.find(M.VisionGeometry["Base.VanSeats"],"WindowMiddleLeft,window",1,true)
        and string.find(M.VisionGeometry["Base.VanSeats"],"WindowMiddleRight,window",1,true),
        "stock passenger windows must inherit the owning door's native area")
    MELensRV = nil
    check(pcall(M.Vision.register),"optional Java absence must leave vanilla detection running")
    MELensRV = saved
end

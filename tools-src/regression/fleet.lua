-- Shared furniture transforms and optional fleet layout contracts; no native renderer/input claims.
do
    local M,P=MELens,MELens.Parts
    local old=M.modelOffset(.45,.51,.84)
    check(math.abs(old[1]-.5)<1e-8 and math.abs(old[2]-.5)<1e-8 and math.abs(old[3]-1)<1e-8,
        "released KI5 furniture transform changed")
    local representatives={"Base.Van","Base.VanSeats","Base.VanAmbulance","Base.VanRadio","Base.StepVan",
        "Base.86fordE150","Base.86fordE150long","Base.86fordE150longW","Base.85chevyStepVan",
        "Base.87fordF700bank","Base.87fordF700swat","Base.90fordF350ambulance"}
    local seen={}
    for _,name in ipairs(representatives) do
        local pr=assert(M.Profiles[name])
        check(not seen[pr],"duplicate fleet representative")
        seen[pr]=true
        check(M.WalkGrids[pr.walkGrid]~=nil,"missing generated walk grid: "..name)
        check(M.RoomRings[pr.walkGrid]~=nil,"missing shell outline: "..name)
        check(pr.ki5Storage==nil and pr.loot==nil,"fleet conversion replaces factory cargo: "..name)
        check(P.fits(pr.spots[1],"bed") and P.fits(pr.spots[1],"dinette"),"large furniture rejected: "..name)
        check(P.roomFor(pr,{},1,"bed"),"bed cannot be installed in empty compartment: "..name)
        if #pr.spots==3 then
            check(not P.roomFor(pr,{[1]="bed"},2,"kitchen"),"small van accepts overlapping kitchen: "..name)
        else
            check(P.roomFor(pr,{[1]="bed"},2,"dinette"),"wide vehicle blocks opposite furnishing wall: "..name)
        end
        for _,spot in ipairs(pr.spots) do check(spot.empty,"new optional fleet invents furnished loot: "..name) end
        local scale=pr.vehicleScale or .9
        local offset=M.modelOffset(.45,.51,.84,pr)
        local shift=pr.modelShift or {0,-.06,.06}
        check(math.abs(offset[1]*scale-(.45+shift[1]))<1e-8 and math.abs(offset[2]*scale-(.51+shift[2]))<1e-8,
            "furniture offset does not normalize parent scale: "..name)
        -- Compare emitted pieces and their previews: both need the same scale.
        local chunks={}
        local script={getName=function() return name end,Load=function(_,_,text) chunks[#chunks+1]=text end}
        local bridge=MELensRV;MELensRV={}
        P.extendScript(script,pr)
        MELensRV=bridge
        local text=table.concat(chunks)
        local modelScale=string.format("scale = %.7f",.9/scale)
        check(text:find(modelScale,1,true)~=nil,"models miss parent scale normalization: "..name)
        check(text:find("model ghost_bed",1,true)~=nil,"bed preview missing: "..name)
    end
    local count=0
    for _,pr in pairs(M.Profiles) do if seen[pr] then count=count+1 end end
    check(count==193,"fleet identifier coverage changed unexpectedly")
    check(#M.Profiles["Base.87fordF700box"].spots==83,"released cargo slots changed")
    local manager=getScriptManager
    getScriptManager=function() return {getVehicle=function() return nil end} end
    check(pcall(M.addStandingPositions),"optional vehicle packs cannot be absent")
    getScriptManager=manager
end

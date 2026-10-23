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
            check(P.roomFor(pr,{[1]="bed"},2,"kitchen"),"small van rejects adjacent bed and kitchen: "..name)
            check(P.roomFor(pr,{[2]="kitchen"},1,"bed"),"bed/kitchen placement order matters: "..name)
            check(not P.roomFor(pr,{[2]="kitchen"},3,"fridge"),"front kitchen accepts overlapping fridge: "..name)
            check(P.roomFor(pr,{[1]="bed"},3,"fridge"),"small van rejects bed and fridge: "..name)
            check(pr.aisleX==-.25 and pr.standing.inside[1]==-.25,"narrow van entry misses clear aisle: "..name)
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
    for name,use in pairs(P.VEHICLE_USE) do
        local pr=assert(M.Profiles[name])
        local v={getScript=function() return {getFullName=function() return name end} end}
        local fitted={}
        for index,piece in pairs(use.fittings) do
            check(P.factoryPiece(v,index,pr.spots[index])==piece,"wrong service fitting: "..name)
            check(P.fits(pr.spots[index],piece),"service fitting does not fit: "..name..":"..piece)
            check(P.roomFor(pr,fitted,index,piece),"service fittings overlap: "..name)
            fitted[index]=piece
            check(piece~="bed" and piece~="kitchen","service vehicle receives residential furniture")
        end
        check(pr.loot==nil and pr.ki5Storage==nil,"service fittings overwrite native vehicle loot")
    end
    for name,pr in pairs(M.Profiles) do
        if pr.shell.models[1]:find("fleet_",1,true) or name=="Base.87fordF700box" then
            check(pr.shell.models[3] and pr.shell.models[3]:find("_bulkhead",1,true),"unsealed cargo cab: "..name)
        end
    end
    for name,roof in pairs({["Base.87fordF700bank"]=1.295,["Base.87fordF700swat"]=1.142}) do
        check(M.Profiles[name].cutFrontTop>roof,"armored truck cab roof is cut away: "..name)
    end
    local payday=M.Profiles["Base.86fordE150pd"].hideKI5
    for _,model in ipairs({"86fordE150pd1","86fordE150pd2","86fordE150pd3","86fordE150pdinterior"}) do
        local rule=payday[model]
        check(type(rule)=="table" and rule.plane and rule.plane[2]==-1,
            "variant factory chairs/liner are absent from shared rear-compartment clipping: "..model)
    end
    local oldX,oldY,oldProject=getMouseXScaled,getMouseYScaled,M.Interact.screenToCamper
    getMouseXScaled=function() return 0 end;getMouseYScaled=function() return 0 end
    local px,pz=0,0
    M.Interact.screenToCamper=function() return px,pz end
    local a={index=2,rise=0,x0=-.5,x1=.5,z0=-1,z1=0}
    local b={index=3,rise=0,x0=-.5,x1=.5,z0=-.7,z1=.3}
    local mode={profile={floorY=0},places={a,b}}
    pz=-.2
    check(M.Placement.Mode.placeUnderMouse(mode)==b,"overlapping marker chooses earlier slot over nearest centre")
    pz=-.5
    check(M.Placement.Mode.placeUnderMouse(mode)==a,"nearest marker selection is reversed")
    mode.places={b,a}
    check(M.Placement.Mode.placeUnderMouse(mode)==a,"marker selection depends on list order")
    local upper={index=4,rise=.8,x0=-.5,x1=.5,z0=-1,z1=0}
    mode.places={a,upper}
    check(M.Placement.Mode.placeUnderMouse(mode)==upper,"nearest marker ignores stacked floor priority")
    pz=4
    check(M.Placement.Mode.placeUnderMouse(mode)==nil,"off-marker click selects furniture slot")
    getMouseXScaled,getMouseYScaled,M.Interact.screenToCamper=oldX,oldY,oldProject
    local manager=getScriptManager
    getScriptManager=function() return {getVehicle=function() return nil end} end
    check(pcall(M.addStandingPositions),"optional vehicle packs cannot be absent")
    getScriptManager=manager
end

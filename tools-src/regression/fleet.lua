-- Shared furniture transforms and optional fleet layout contracts; no native renderer/input claims.
do
    local M,P=MELens,MELens.Parts
    local cargoSides={left=0,right=0}
    for _,s in ipairs(M.Profiles["Base.StepVan"].spots) do
        if s.factory and s.default=="parcels" then cargoSides[s.wall]=cargoSides[s.wall]+1 end
    end
    check(cargoSides.left==3 and cargoSides.right==3,"step van lost a cargo row at a floating-point boundary")
    for _,name in ipairs({"Base.87fordF700swat","Base.90fordF350SWAT","Base.85chevyStepVanSWAT","Base.StepVan_LouisvilleSWAT"}) do
        local pr=M.Profiles[name];local benches,seats=0,{}
        for _,s in ipairs(pr.spots) do if s.factory and s.default=="medbench" then
            benches=benches+1
            for _,id in ipairs(s.seats or {}) do check(not seats[id],"SWAT bench duplicates passenger ID");seats[id]=true end
        end end
        check(pr.factoryRole=="swat" and benches==2,"SWAT vehicle lacks opposing rear crew benches: "..name)
        for _,id in ipairs(pr.extraSeats) do check(seats[id],"SWAT bench loses released passenger ID: "..name) end
    end
    for _,name in ipairs({"Base.StepVan","Base.85chevyStepVan"}) do
        local bridge=MELensRV; MELensRV=completeJava()
        local pr=M.Profiles[name];check(pr.shell.entryModel==4,"missing rear door interior skin: "..name)
        local open,item,shown=false,{},nil
        local door={isOpen=function() return open end}
        local leaf={getDoor=function() return door end,getInventoryItem=function() return item end}
        local part={setModelVisible=function(_,model,value)
            if model=="MELensShell4" then shown=value
            else
                local index=tonumber(model:match("MELensShell(%d+)"))
                if index==pr.shell.nativePanelModel or index==pr.shell.legacyPanelModel then
                    check(value==(index==pr.shell.legacyPanelModel),"older bridge chose native utility panel")
                    return
                end
                for _,trim in ipairs(pr.shell.windowReturns or {}) do
                    if index==trim.model then
                        check(value==false,"older bridge exposes native window surround")
                        return
                    end
                end
                check(index==pr.shell.wheelCoversModel or index==pr.shell.wheelFloorModel or index==pr.shell.wheelWallModel
                    or index==pr.shell.nativeFloorModel,
                    "unexpected model in door/fallback synchronization")
                check(value==(index==pr.shell.wheelCoversModel),"older bridge lost fallback wheel covers")
            end
        end}
        local v={getPartById=function(_,id) return id==P.SHELL and part or leaf end}
        P.syncShellDoors(v,pr);check(shown==true,"closed rear door is transparent")
        open=true;P.syncShellDoors(v,pr);check(shown==false,"open rear door retains closed lining")
        open=false;P.syncShellDoors(v,pr);check(shown==true,"closing rear door does not restore lining")
        item=nil;P.syncShellDoors(v,pr);check(shown==false,"missing rear door retains lining")
        MELensRV=bridge
    end
    local old=M.modelOffset(.45,.51,.84)
    check(math.abs(old[1]-.5)<1e-8 and math.abs(old[2]-.5)<1e-8 and math.abs(old[3]-1)<1e-8,
        "released KI5 furniture transform changed")
    local representatives={"Base.Van","Base.VanSeats","Base.VanAmbulance","Base.VanRadio","Base.StepVan",
        "Base.86fordE150","Base.86fordE150long","Base.86fordE150longW","Base.85chevyStepVan",
        "Base.87fordF700bank","Base.87fordF700swat","Base.90fordF350ambulance"}
    local seen={}
    for _,name in ipairs(representatives) do
        local pr=assert(M.Profiles[name])
        check(not seen[pr.walkGrid],"duplicate fleet representative")
        seen[pr.walkGrid]=true
        check(M.WalkGrids[pr.walkGrid]~=nil,"missing generated walk grid: "..name)
        check(M.RoomRings[pr.walkGrid]~=nil,"missing shell outline: "..name)
        check(pr.ki5Storage==nil and pr.loot==nil,"fleet conversion replaces factory cargo: "..name)
        check(P.fits(pr.spots[1],"bed") and P.fits(pr.spots[1],"dinette"),"large furniture rejected: "..name)
        check(P.roomFor(pr,{},1,"bed"),"bed cannot be installed in empty compartment: "..name)
        if (pr.legacySpotCount or #pr.spots)==3 then
            check(P.roomFor(pr,{[1]="bed"},2,"kitchen"),"small van rejects adjacent bed and kitchen: "..name)
            check(P.roomFor(pr,{[2]="kitchen"},1,"bed"),"bed/kitchen placement order matters: "..name)
            check(not P.roomFor(pr,{[2]="kitchen"},3,"fridge"),"front kitchen accepts overlapping fridge: "..name)
            check(P.roomFor(pr,{[1]="bed"},3,"fridge"),"small van rejects bed and fridge: "..name)
            check(pr.standing.inside[1]==-.25,"narrow van entry misses clear aisle: "..name)
        else
            check(P.roomFor(pr,{[1]="bed"},2,"dinette"),"wide vehicle blocks opposite furnishing wall: "..name)
        end
        for index,spot in ipairs(pr.spots) do
            if index<=pr.legacySpotCount then check(spot.empty,"released placement slot changed: "..name) end
        end
        local scale=pr.vehicleScale or .9
        local offset=M.modelOffset(.45,.51,.84,pr)
        local shift=pr.modelShift or {0,-.06,.06}
        check(math.abs(offset[1]*scale-(.45+shift[1]))<1e-8 and math.abs(offset[2]*scale-(.51+shift[2]))<1e-8,
            "furniture offset does not normalize parent scale: "..name)
        -- Compare emitted pieces and their previews: both need the same scale.
        local chunks={}
        local script={getName=function() return name end,Load=function(_,_,text) chunks[#chunks+1]=text end}
        local bridge=MELensRV;MELensRV=completeJava()
        P.extendScript(script,pr)
        MELensRV=bridge
        local text=table.concat(chunks)
        local modelScale=string.format("scale = %.7f",.9/scale)
        check(text:find(modelScale,1,true)~=nil,"models miss parent scale normalization: "..name)
        check(text:find("model ghost_bed",1,true)~=nil,"bed preview missing: "..name)
    end
    local count=0
    for _,pr in pairs(M.Profiles) do if seen[pr.walkGrid] then count=count+1 end end
    check(count==193,"fleet identifier coverage changed unexpectedly")
    local supported,plainWalls,ki5Walls=0,0,0
    -- Exact source-qualified living leaves plus the previously approved panels.
    -- Cab doors and exterior storage lids must never enter this classifier.
    local bodyAliases={
        Airflyte={"TrailerKI5shastaAirflytetop","TrailerKI5shastaAstrodometop","61shastaCamperToolboxLid2","61shastaCamperToolboxLid3","61shastaCamperDoorfr"},
        B700={"87fordB700Doorr","87fordB700Doorfr"},Bambi16={"61bambiCamperToolboxLid","61bambiCamperDoorfr"},
        ChevyStepVan={"85chevyStepVantrunkDoor"},
        E150Long={"86fordE150PanelLeft","86fordE150PanelRight","86fordE150doorrr","86fordE150trunkDoor"},
        E150Short={"86fordE150PanelLeft","86fordE150PanelRight","86fordE150doorrl","86fordE150doorrr","86fordE150doorrrw","86fordE150trunkDoor"},
        E150Windows={"86fordE150PanelLeft","86fordE150PanelRight","86fordE150doorrlw","86fordE150doorrrw","86fordE150trunkDoor"},
        F350Ambulance={"90fordF350ambulancedoorrr","90fordF350ambulancedoorr"},
        F700Bank={"87fordF700TrunkDoor"},F700Swat={"87fordF700TrunkDoor","87fordF700Doorrr"},
        F700box={"87fordF700TrunkDoorX"},Scamp13={"87scampCamperDoorfr"},Scamp16={"87scampCamperDoorfr"},
        FlyingCloud22={"54cloudCamperDoorfr"},
    }
    local vanillaGrids={}
    for i=1,5 do vanillaGrids[M.Profiles[representatives[i]].walkGrid]=true end
    for name,pr in pairs(M.Profiles) do
        supported=supported+1
        local vanilla=vanillaGrids[pr.walkGrid]==true
        check((pr.nativePlainFinish==true)==vanilla,"plain finish escaped vanilla scope: "..name)
        check(pr.nativeBodyWalls==true,"supported vehicle lost native curved walls: "..name)
        local sideEdges=pr.walkGrid=="MELens.VanillaPassengerVan.shell" or pr.walkGrid=="MELens.VanillaVan.shell"
        check((#(pr.nativeNearFaces or {})==2)==sideEdges,"side edge classifier escaped qualified source families: "..name)
        if #(pr.wheelWells or {})>0 then
            check(pr.nativeWheelArch and pr.shell.wheelCoversModel and pr.shell.wheelFloorModel,
                "supported interior still lacks the flat wheel-floor contract: "..name)
        end
        if vanilla then check(pr.nativeWheelWellTrim and #pr.nativeWheelWellTrim.sides==2,
            "stock inner wheel skin retained behind the replacement floor: "..name) end
        local partition=pr.kind=="cargo" and pr.walkGrid~="MELens.F350Ambulance.shell"
        check((pr.nativeCabPartition==true)==partition,"measured cargo cab partition scope changed: "..name)
        local fenderPrefix=pr.walkGrid=="MELens.F700Bank.shell" and "87fordF700bank"
            or pr.walkGrid=="MELens.F700Swat.shell" and "87fordF700swat" or nil
        if fenderPrefix then
            local fittings=pr.nativeArchTrimModels or {}
            check(#fittings==2 and fittings[1]==fenderPrefix.."FenderL" and fittings[2]==fenderPrefix.."FenderR",
                "rear fitting trim lost exact native aliases: "..name)
        else
            check(pr.nativeArchTrimModels==nil,"rear fitting trim escaped measured truck scope: "..name)
        end
        if vanilla then
            plainWalls=plainWalls+1
            local metal=pr.nativeStockMetal
            local step=pr.walkGrid=="MELens.VanillaStepVan.shell"
            check(metal and metal.texture=="vehicle_vanseatsshell"
                and metal.paintUV[1]==(step and .546875 or .56640625)
                and metal.paintUV[2]==(step and .4296875 or .35546875)
                and metal.panelUV[1]==.3427734375 and metal.panelUV[2]==.2861328125
                and metal.panelUV[3]==.4970703125 and metal.panelUV[4]==.3896484375
                and metal.panelWidth==1.10 and metal.panelHeight==.7425,
                "stock metal lost qualified game pixels or physical scale: "..name)
            local material=pr.nativeWallMaterial
            check(material and material.texture=="MELensShell_f700box_walls"
                and material.height>=.5 and material.height<=4
                and material.perimeter>=2 and material.perimeter<=40,
                "stock native walls lost their measured partition material: "..name)
        else
            ki5Walls=ki5Walls+1
            check(pr.nativeStockMetal==nil,"stock metal escaped vanilla scope: "..name)
            local colour=pr.kind=="cargo" and {.64,.66,.67} or pr.kind=="bus" and {.78,.76,.70} or {.80,.76,.66}
            check(pr.nativeBodyLining[1]==colour[1] and pr.nativeBodyLining[2]==colour[2] and pr.nativeBodyLining[3]==colour[3],
                "approved KI5 finish changed: "..name)
            local scamp=name=="Base.Trailer87Scamp13" or name=="Base.Trailer87Scamp16"
            local family=pr.walkGrid:match("MELens%.(.-)%.shell") or "FlyingCloud22"
            local expected=bodyAliases[family]
            check(expected and #pr.nativeBodyModels==#expected,"native structural alias coverage changed: "..name)
            local actual={}
            for _,alias in ipairs(pr.nativeBodyModels) do actual[alias]=true end
            for _,alias in ipairs(expected) do check(actual[alias],"native leaf/panel alias mismatch: "..name..":"..alias) end
            if pr.kind=="bus" then check(pr.nativeCabModels and #pr.nativeCabModels==4
                and pr.nativeCabModels[1]=="87fordB700Interior" and pr.nativeCabModels[3]=="87fordB700Engine",
                "bus lost its actual cab controls: "..name) end
            if family=="Airflyte" then check(pr.nativeRoofCuts and #pr.nativeRoofCuts==5,"Airflyte lost measured roof cuts") end
            check((pr.nativeBodyTrim~=nil)==scamp,"measured hitch trim escaped Scamp scope: "..name)
            check(pr.nativeEntryOpening==nil and pr.nativeDoorOpenings==nil,
                "later generic wall controls replace approved KI5 details: "..name)
            local material=pr.nativeWallMaterial
            if material then
                check(material.texture:match("^MELensShell_[a-z0-9_]+_walls$")~=nil
                    and material.height>=.5 and material.height<=4 and material.perimeter>=2 and material.perimeter<=40,
                    "curved material exceeds the existing atlas/physical bounds contract: "..name)
            end
        end
        local support=false
        for _,model in ipairs(pr.shell.models) do
            if model:find("_support$",1) then support=true end
        end
        check(support,"native body hides utility/wheel supports with lining: "..name)
    end
    check(supported==203,"interior coverage includes disabled or missing scripts")
    check(plainWalls==96 and ki5Walls==107,"vanilla/KI5 finish coverage changed")
    check(#M.Profiles["Base.87fordF700box"].spots==83,"released cargo slots changed")
    for name,pr in pairs(M.Profiles) do
      if pr.factoryLayout then
        local v={getScript=function() return {getFullName=function() return name end} end}
        local fitted={}
        for index,spot in ipairs(pr.spots) do
          if spot.factory then
            local piece=spot.default
            check(P.factoryPiece(v,index,pr.spots[index])==(not spot.empty and piece or nil),"wrong service fitting: "..name)
            check(P.fits(pr.spots[index],piece),"service fitting does not fit: "..name..":"..piece)
            check(P.roomFor(pr,fitted,index,piece),"service fittings overlap: "..name)
            if not spot.empty then fitted[index]=piece end
            check(piece~="bed" and (piece~="kitchen" or pr.factoryRole=="catering"),"service vehicle receives inappropriate residential furniture")
          end
        end
        check(pr.loot==nil and pr.ki5Storage==nil,"service fittings overwrite native vehicle loot")
        local fittedCount=0;for _ in pairs(fitted) do fittedCount=fittedCount+1 end
        check(fittedCount>0,"empty factory cargo layout: "..name)
        check(#pr.extraSeats<=4,"factory layout changes released passenger budget: "..name)
      end
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

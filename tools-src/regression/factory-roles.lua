-- Role contracts derived from the all-variant native E/G visual audit.
-- These check generated layouts/stock, not final pixels or native item interaction.
do
    local profiles=MELens.Profiles
    local function factoryPieces(pr)
        local pieces={}
        for _,spot in ipairs(pr.spots) do if spot.factory and not spot.empty then
            pieces[spot.default]=(pieces[spot.default] or 0)+1
        end end
        return pieces
    end
    local function hasStock(pr,piece,item)
        for _,pack in ipairs(pr.factoryUse.stock[piece] or {}) do
            if pack[1]==item and pack[2]>0 then return true end
        end
        return false
    end
    for _,name in ipairs({"Base.VanAmbulance","Base.86fordE150med","Base.90fordF350ambulance"}) do
        local pr=assert(profiles[name]);local stretcher,bench
        for _,spot in ipairs(pr.spots) do if spot.factory then
            if spot.default=="stretcher" then stretcher=spot end
            if spot.default=="medbench" then bench=spot end
        end end
        check(stretcher and stretcher.wall=="right" and stretcher.x<0,"ambulance stretcher is on the wrong side: "..name)
        check(bench and bench.wall=="left" and bench.x>0,"ambulance attendant bench must oppose the stretcher: "..name)
        check(stretcher.z<pr.door.z+1.1,"ambulance stretcher moved away from the rear door: "..name)
    end
    local ambulance=profiles["Base.90fordF350ambulance"]
    local stepVan=profiles["Base.85chevyStepVan"]
    local emptyFront=0
    local stepVehicle={getScript=function() return {getFullName=function() return "Base.85chevyStepVan" end} end}
    for index,spot in ipairs(stepVan.spots) do
        if spot.factory and spot.wall=="front" and spot.default=="metalcase" then
            emptyFront=emptyFront+1
            check(spot.empty and MELens.Parts.factoryPiece(stepVehicle,index,spot)==nil,
                "Chevrolet Step Van centre cabinet still factory-fills")
            check(MELens.Parts.fits(spot,"metalcase"),"empty Step Van bay lost its saved placement contract")
        end
    end
    check(emptyFront==1,"Step Van centre cabinet bay identity changed")
    local v={getScript=function() return {getFullName=function() return "Base.90fordF350ambulance" end} end}
    check(#ambulance.spots==12 and ambulance.legacySpotCount==4,"ambulance placement slot IDs changed")
    for _,index in ipairs({7,8}) do
        local spot=ambulance.spots[index]
        check(spot.wall=="front" and spot.default=="medlocker" and spot.factory,
            "front cabinet correction changed installed slot identity")
        -- Native bulkhead rear face and the kit's maximum 14mm rear trim.
        check(spot.z+.014 <= -.4294017-.01,
            "front cabinet back intersects native F350 bulkhead")
    end
    for _,index in ipairs({11,12}) do
        local spot=ambulance.spots[index]
        check(spot.wall=="right" and spot.default=="medlocker" and spot.factory and spot.empty,
            "KI5 side-door shelves must start empty")
        check(MELens.Parts.factoryPiece(v,index,spot)==nil,"KI5 side-door shelves still auto-fill")
        check(MELens.Parts.fits(spot,"medlocker"),"empty KI5 shelf slot no longer accepts its furniture")
    end
    -- Native labels whose shortened/script-specific spellings used to silently
    -- fall back to tool freight, or to unrelated books/canned-food distributions.
    local cases={
        {"Base.85chevyStepVanGenuine","beer","CrateBeer"},
        {"Base.Van_KnoxDisti","liquor","CrateLiquor"},
        {"Base.VanBrewsterHarbin","coffee","CrateCoffee"},
        {"Base.StepVan_Citr8","softdrinks","CrateSodaBottles"},
        {"Base.85chevyStepVanSunBallz","cereal","CrateCereal"},
        {"Base.VanOldMill","water","CrateWaterBottle"},
        {"Base.Van_Perfick_Potato","snacks","CrateChips"},
        {"Base.86fordE150perfick","snacks","CrateChips"},
        {"Base.VanMail","postal","PostOfficeParcels"},
        {"Base.StepVan_Heralds","newspaper","PostOfficeNewspapers"},
        {"Base.StepVan_HuangsLaundry","laundry","CrateLinens"},
        {"Base.StepVan_Florist","florist","GardenStoreMisc"},
        {"Base.Van_HeritageTailors","tailoring","CrateTailoring"},
        {"Base.Van_Leather","leather","CrateLeather"},
        {"Base.StepVan_SmartKut","tailoring","CrateTailoring"},
        {"Base.85chevyStepVanSmartCut","tailoring","CrateTailoring"},
        {"Base.StepVan_Jorgensen","carpentry","CrateCarpentry"},
        {"Base.StepVan_Scarlet","liquor","CrateLiquor"},
        {"Base.Van_CraftSupplies","craft","CratePottery"},
        {"Base.Van_Locksmith","locksmith","ToolStoreKeymaking"},
        {"Base.VanKnoxCom","electrical","CrateElectronics"},
        {"Base.Van_VoltMojo","electrical","CrateElectronics"},
        {"Base.StepVan_LouisvilleMotorShop","mechanic","CrateMechanics"},
        {"Base.86fordE150korshunovs","mechanic","CrateMechanics"},
        {"Base.86fordE150kyTransit","mechanic","CrateMechanics"},
        {"Base.Van_Transit","mechanic","CrateMechanics"},
        {"Base.86fordE150treyBaines","garden","GardenStoreTools"},
        {"Base.VanTreyBaines","garden","GardenStoreTools"},
        {"Base.86fordE150massGenfac","metalwork","CrateMetalwork"},
        {"Base.Van_MassGenFac","metalwork","CrateMetalwork"},
        {"Base.86fordE150zenith","glasswork","GlassWorkshopTools"},
        {"Base.Van_Glass","glasswork","GlassWorkshopTools"},
        {"Base.VanMicheles","carpentry","CrateCarpentry"},
        {"Base.VanSchwabSheetMetal","metalwork","CrateMetalwork"},
        {"Base.VanUncloggers","plumbing","CrateMetalPipes"},
        {"Base.Van_Masonry","masonry","CrateMasonry"},
        {"Base.StepVan_SouthEasternPaint","painting","CratePaint"},
        {"Base.Van_Blacksmith","blacksmith","CrateBlacksmithing"},
        {"Base.StepVan_MarineBites","seafood","ButcherFish"},
        {"Base.VanPennSHam","ham","ButcherSmoked"},
    }
    for _,case in ipairs(cases) do
        local pr=assert(profiles[case[1]],case[1])
        check(pr.factoryRole==case[2],"wrong signwritten business role: "..case[1])
        local found=false
        for _,distribution in pairs(pr.factoryUse.loot) do if distribution==case[3] then found=true end end
        check(found,"missing native role loot: "..case[1])
    end
    for _,name in ipairs({"Base.StepVan_Propane","Base.VanKnobCreekGas",
            "Base.85chevyStepVanPropane","Base.86fordE150knobCreek"}) do
        local pr=assert(profiles[name]);local pieces=factoryPieces(pr)
        local cargo=pr.factoryFloor or {}
        check(pr.factoryRole=="propane" and pieces.metalcase==1 and not pieces.equipmentrack and not pieces.parcels,
            "propane belongs on open floor with one tool case: "..name)
        check(#cargo>=2 and #cargo<=6,"propane floor quantity is not modest: "..name)
        check(pr.factoryUse.loot.metalcase==nil and hasStock(pr,"metalcase","Base.Wrench")
            and hasStock(pr,"metalcase","Base.Gloves_LeatherGloves")
            and not hasStock(pr,"metalcase","Base.PropaneTank"),"propane tool case contains cylinders/random freight")
        local solids={}
        for _,spot in ipairs(pr.spots) do if spot.factory then
            local x0,x1,z0,z1=math.huge,-math.huge,math.huge,-math.huge
            for _,a in ipairs({-spot.length/2,spot.length/2}) do for _,d in ipairs({0,spot.depth}) do
                local x,z=MELens.Parts.spotPoint(spot,a,d)
                x0,x1,z0,z1=math.min(x0,x),math.max(x1,x),math.min(z0,z),math.max(z1,z)
            end end
            solids[#solids+1]={x0,x1,z0,z1}
        end end
        for _,w in ipairs(pr.wheelWells or {}) do solids[#solids+1]={math.min(w.x[1],w.x[2]),math.max(w.x[1],w.x[2]),w.z[1],w.z[2]} end
        for _,b in ipairs(pr.blocked or {}) do solids[#solids+1]={b.x1,b.x2,b.z1,b.z2} end
        for _,c in ipairs(cargo) do
            check(c.t=="Base.PropaneTank" and c.r==0 and c.hx==.17 and c.hz==.17,"wrong real propane cargo contract")
            check(math.abs(c.x)-c.hx>=.175,"propane narrows the center aisle")
            for _,x in ipairs({c.x-c.hx,c.x+c.hx}) do for _,z in ipairs({c.z-c.hz,c.z+c.hz}) do
                check(MELens.Loose.inRoom(pr,x,z),"full propane footprint crosses measured room: "..name)
            end end
            for _,b in ipairs(solids) do
                check(not (c.x-c.hx<b[2] and c.x+c.hx>b[1] and c.z-c.hz<b[4] and c.z+c.hz>b[3]),
                    "propane intersects furniture, wheel well or another cylinder: "..name)
            end
            solids[#solids+1]={c.x-c.hx,c.x+c.hx,c.z-c.hz,c.z+c.hz}
        end
    end
    for _,name in ipairs({"Base.VanRadio","Base.VanRadio_3N","Base.86fordE150LBMWradio"}) do
        local pr=assert(profiles[name]);local pieces=factoryPieces(pr)
        check(pr.factoryRole=="radio" and pieces.workbench==1 and pieces.medbench==1,
            "broadcast van needs a workstation and operator bench: "..name)
        check(hasStock(pr,"workbench","Base.HamRadio1") and hasStock(pr,"workbench","Base.Headphones"),
            "broadcast desk must hold real radio inventory: "..name)
        check(pr.factoryUse.loot.workbench==nil,"radio desk receives random hardware after its fixed radio kit")
    end
    for _,name in ipairs({"Base.StepVan_MobileLibrary","Base.85chevyStepVanLibrary"}) do
        local pr=assert(profiles[name]);local pieces=factoryPieces(pr)
        check(pr.factoryRole=="library" and (pieces.equipmentrack or 0)>=2 and not pieces.parcels,
            "mobile library books must be on accessible shelves: "..name)
        check(hasStock(pr,"equipmentrack","Base.Book"),"library shelves lack real books")
    end
    for _,name in ipairs({"Base.86fordE150mm","Base.86fordE150creatureCruiser","Base.86fordE150dnd",
            "Base.86fordE150mesmerWagon","Base.86fordE150quantumVessel",
            "Base.86fordE150theLadyDelighter","Base.86fordE150valkyriesSpear"}) do
        local pr=assert(profiles[name]);local pieces=factoryPieces(pr)
        check(pr.factoryRole=="passenger" and pieces.medbench==2 and not pieces.parcels and not pieces.equipmentrack,
            "leisure van is packed with delivery freight: "..name)
        check(hasStock(pr,"medbench","Base.WaterBottle") and hasStock(pr,"medbench","Base.BathTowel"),
            "leisure van lacks modest native day-trip supplies: "..name)
    end
    for name,pr in pairs(profiles) do if pr.factoryLayout then
        local pieces=factoryPieces(pr)
        check(not pieces.freightcrate and not pieces.luggagecase,"unwanted new cargo furniture: "..name)
        check(pr.factoryRole=="propane" or #(pr.factoryFloor or {})==0,"unexpected factory floor cargo: "..name)
        if pr.factoryRole=="passenger" or pr.factoryRole=="prisoner" then
            check(pieces.medbench==2 and not pieces.parcels and not pieces.equipmentrack,
                "passenger rear floor is filled with freight or tool racks: "..name)
            if pr.factoryRole=="prisoner" then
                check(#pr.factoryUse.stock.medbench==0,"prisoner bench contains accessible equipment")
            end
        elseif pr.factoryRole=="catering" then
            check(pieces.kitchen==1 and pieces.fridge==1,"caterer lacks preparation/cold storage: "..name)
            check(hasStock(pr,"kitchen","Base.Saucepan"),"caterer kitchen lacks preparation inventory")
        elseif pr.factoryRole=="coldfood" or pr.factoryRole=="seafood" or pr.factoryRole=="ham" or pr.factoryRole=="eggs" then
            check((pieces.fridge or 0)>=1 and not pieces.kitchen,"cold delivery needs refrigeration: "..name)
            check(pr.factoryUse.loot.equipmentrack==nil,"cold delivery puts meat/eggs on uncooled shelves")
        end
        check(pr.factoryLayout=="cargo-service-1","role polish changed the existing saved layout stamp")
        check(pr.legacySpotCount>0,"role polish lost the released empty furniture slots")
    end end
end

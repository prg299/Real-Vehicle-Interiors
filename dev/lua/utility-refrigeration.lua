-- Server-owned native components in a disposable multiplayer world. UI actions
-- are driven separately; clock/climate and new contents are explicit fixtures.
MELensUtilityProbe = {}
local T, U, P = MELensUtilityProbe, MELens.Utilities, MELens.Parts
function T.bind(vehicle)
    T.vehicle = assert(vehicle)
    T.fridge = assert(P.spotPart(vehicle, 4))
    assert(P.pieceAt(T.fridge) == "fridge")
end
function T.snapshot()
    local v, p = T.vehicle, T.fridge
    local c, g, w = p:getItemContainer(), U.generatorState(v), U.waterState(v)
    local r = { id=v:getId(), sqlId=v:getSqlId(), script=v:getScriptName(), hours=getGameTime():getWorldAgeHours(),
        fuel=g.fuel, on=g.on, rate=U.generatorFuelRate(v), clock=g.part:getModData().MELensGeneratorHour,
        water=w.water, tainted=w.tainted, fridgeId=p:getInventoryItem():getID(),
        type=c:getType(), temperature=c:getTemperature(), fridge=c:isFridge(), powered=c:isPowered(),
        gridElectricity=v:getSquare():haveElectricity(), foods={}, parts={} }
    for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i);r.parts[#r.parts+1]=part:getId() end
    for _,box in ipairs({c, assert(v:getPartById(P.FLOOR)):getItemContainer()}) do
        for i=0,box:getItems():size()-1 do local item=box:getItems():get(i)
            if instanceof(item,"Food") then r.foods[#r.foods+1]={id=item:getID(),age=item:getAge(),heat=item:getHeat(),cold=box==c} end
        end
    end
    table.sort(r.foods,function(a,b)return a.id<b.id end)
    return r
end
function T.foodControls()
    local v,cold = T.vehicle,T.fridge:getItemContainer()
    local warm = v:getPartById(P.FLOOR):getItemContainer()
    T.cold, T.warm = assert(cold:AddItem("Base.Apple")), assert(warm:AddItem("Base.Apple"))
    for _,food in ipairs({T.cold,T.warm}) do food:setAge(0);food:setHeat(1);food:updateAge(true) end
    local r=T.snapshot();r.controlColdId=T.cold:getID();r.controlWarmId=T.warm:getID();return r
end
function T.advance(hours)
    local time=getGameTime();assert(time:getTimeOfDay()+hours<24,"bounded same-day clock fixture")
    time:setTimeOfDay(time:getTimeOfDay()+hours)
    return time:getWorldAgeHours()
end
function T.ageControls()
    local square=T.vehicle:getSquare();local before=square:haveElectricity()
    T.cold:updateAge(true);T.warm:updateAge(true)
    assert(square:haveElectricity()==before,"fridge advice leaked square power")
    for _,food in ipairs({T.cold,T.warm}) do sendAddItemToContainer(food:getContainer(),food) end
    return T.snapshot()
end
function T.overlap()
    local g=U.generatorState(T.vehicle);local before=g.fuel
    U.updateGenerator(T.vehicle,g.part,7200)
    U.updateGenerator(T.vehicle,g.part,7200)
    return {before=before,after=U.generatorState(T.vehicle).fuel}
end
function T.rain()
    local water=U.waterState(T.vehicle);water.part:getModData().water=20;water.part:getModData().tainted=false
    local cf=getClimateManager():getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY)
    local enabled,value=cf:isEnableAdmin(),cf:getAdminValue()
    local others={};local it=getCell():getVehicles():iterator()
    while it:hasNext() do local v=it:next();local w=U.waterState(v)
        if v~=T.vehicle and w then others[#others+1]={v=v,p=w.part,water=w.water,tainted=w.tainted} end end
    local ok,err=pcall(function()
        cf:setAdminValue(1);cf:setEnableAdmin(true);getClimateManager():update()
        MELens.Home.rainTick();assert(U.waterState(T.vehicle).water==20 and not U.waterState(T.vehicle).tainted)
    end)
    cf:setAdminValue(value);cf:setEnableAdmin(enabled);getClimateManager():update()
    for _,w in ipairs(others) do w.p:getModData().water=w.water;w.p:getModData().tainted=w.tainted;U.transmit(w.v,w.p) end
    U.transmit(T.vehicle,water.part)
    assert(ok,err);return T.snapshot()
end

-- Actual native Food.update cooking in the RV oven. Component evidence, not UI input.
-- Two paired atomic runs use the same minute sequence, initially hot raw bacon,
-- oven heat and propane. The stove switch is the causal difference. Only owned
-- tagged food is created/removed; existing oven contents and settings are preserved.
local v=MELensFoodProbeVehicleID and getVehicleById(MELensFoodProbeVehicleID)
    or (MELensFeatureTest and MELensFeatureTest.vehicle)
    or (MELensMPFeatureTest and MELensMPFeatureTest.vehicle)
    or (getPlayer() and getPlayer():getVehicle())
assert(v and v:isStopped(),"native food probe needs stopped furnished camper")
assert(not isClient(),"run this probe in single player or on dedicated-server authority")
local U=MELens.Utilities
local state=assert(U.ovenState(v),"native oven part missing")
assert(state.kitchen,"native kitchen missing")
local oven=assert(state.part:getItemContainer(),"native oven container missing")
local data=state.part:getModData()
local time=getGameTime()
SandboxVars.MELens=SandboxVars.MELens or {}
local saved={on=data.on,heat=data.heat,temperature=oven:getCustomTemperature(),
    propane=U.propaneLevel(v),propaneOption=SandboxVars.MELens.PropaneAppliances,timeOfDay=time:getTimeOfDay()}
local results,owned={},{}
local function snapshot(item)
    return {id=item:getID(),type=item:getFullType(),inOven=item:getContainer()==oven,
        nativeFood=instanceof(item,"Food"),heat=item:getHeat(),cookingTime=item:getCookingTime(),
        minutesToCook=item:getMinutesToCook(),minutesToBurn=item:getMinutesToBurn(),
        cooked=item:isCooked(),burnt=item:isBurnt(),frozen=item:isFrozen(),
        ovenHeat=data.heat,ovenTemperature=oven:getTemperature(),propane=U.propaneLevel(v)}
end
local function removeOwned()
    for _,item in ipairs(owned) do
        local container=item:getContainer()
        if container then
            container:Remove(item)
            if isServer() then sendRemoveItemFromContainer(container,item) end
        end
    end
end
local function restore()
    removeOwned()
    data.on,data.heat=saved.on,saved.heat
    oven:setCustomTemperature(saved.temperature)
    U.setPropane(v,saved.propane,true)
    SandboxVars.MELens.PropaneAppliances=saved.propaneOption
    time:setTimeOfDay(saved.timeOfDay)
    U.transmit(v,state.part)
end
local ok,err=pcall(function()
    SandboxVars.MELens.PropaneAppliances=true
    local function run(on,name)
        time:setTimeOfDay(saved.timeOfDay)
        data.on,data.heat=on,2
        oven:setCustomTemperature(2)
        U.setPropane(v,.5,true)
        local item=assert(oven:AddItem("Base.Bacon"),"installed Base.Bacon missing")
        owned[#owned+1]=item
        assert(instanceof(item,"Food") and item:isCookable(),"fixture is not cookable native Food")
        item:setName("Native cooking probe "..name)
        item:getModData().MELensFoodProbe=name
        item:setAge(0)
        item:setFreezingTime(0)
        item:setCookingTime(0)
        item:setCooked(false)
        item:setBurnt(false)
        item:setHeat(2) -- paired preheated raw-food fixture; natural heating is a separate component check
        item:setLastCookMinute(time:getMinutes())
        if isServer() then sendAddItemToContainer(oven,item) end
        local before=snapshot(item)
        local samples={}
        for minute=1,30 do
            time:setTimeOfDay(saved.timeOfDay+minute/60)
            U.updateOven(v,state.part,1)
            -- Native Food uses the actual engine minute gate. Cooking/cooked fields
            -- are never changed after setup; the stock Java update must produce them.
            item:update()
            if minute==1 or minute%5==0 then
                local sample=snapshot(item);sample.minute=minute;samples[#samples+1]=sample
            end
        end
        local after=snapshot(item)
        assert(after.id==before.id and after.inOven,"native cooking replaced/lost bacon identity")
        local result={name=name,stoveOn=on,before=before,after=after,samples=samples,
            sameMinuteSequence=true,simulationMinutes=30,preheatedFoodFixture=true,
            nativeFoodUpdate=true,uiInputVerified=false}
        results[#results+1]=result
        oven:Remove(item)
        if isServer() then sendRemoveItemFromContainer(oven,item) end
        return after
    end
    local off=run(false,"stove-off-cooking-control")
    local on=run(true,"stove-on-cooks-native-food")
    assert(not off.cooked and not off.burnt,"off control unexpectedly cooked/burned")
    assert(on.cooked and not on.burnt,"powered native oven did not cook bacon without burning it")
    assert(on.cookingTime>off.cookingTime+5,"native cooking did not respond to stove input")
    assert(on.propane<.5 and math.abs(off.propane-.5)<.0001,"cooking propane/control conservation failed")
end)
restore()
if not ok then error(err) end
return {passed=true,vehicleId=v:getId(),world=getWorld():getWorld(),results=results,
    authority=isServer() and "dedicated-server" or "single-player",
    engineSource="installed 42.21 Food.update minute-gated native cooking",
    fixtureState="paired preheated raw bacon and oven; atomic same-minute sequences",
    originalStateRestored=true,uiInputVerified=false}

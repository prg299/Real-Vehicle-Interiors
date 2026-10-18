-- Deterministic component probes in the disposable native game. These use real
-- vehicle parts, fluid containers, climate and IsoGenerator objects. They do not
-- establish mouse/UI acceptance; the separate feature drivers cover that path.
local F = assert(MELensFeatureTest, "native feature fixture missing")
local v, p, U, P, H = F.vehicle, F.player, MELens.Utilities, MELens.Parts, MELens.Home
assert(#ISTimedActionQueue.getTimedActionQueue(p).queue == 0, "wait for timed actions")
local results = {}
local function near(a,b,t) assert(math.abs(a-b) < (t or .0001), tostring(a).." != "..tostring(b)) end
local function record(name, values) values.name=name; values.passed=true; results[#results+1]=values end
local gen, tank, oven = U.generatorState(v).part, U.waterState(v).part, U.ovenState(v).part
local heater, pc = U.heaterPart(v), v:getPartById("PassengerCompartment")
local battery = assert(v:getBattery():getInventoryItem(), "native battery missing")
local gd, wd, od, pd = gen:getModData(), tank:getModData(), oven:getModData(), pc:getModData()
local hd = assert(heater, "native heater missing"):getModData()
local saved = {fuel=gd.fuel,on=gd.on,wear=gd.wear,condition=gen:getCondition(),battery=battery:getCurrentUsesFloat(),
    water=wd.water,tainted=wd.tainted,propane=U.propaneLevel(v),ovenOn=od.on,heat=od.heat,
    heaterOn=hd.on,temperature=pd.temperature,lights=v:getModData().MELensLightsOff,
    timeOfDay=getGameTime():getTimeOfDay(),
    fuelOption=SandboxVars.MELens and SandboxVars.MELens.GeneratorFuelUse,
    wearOption=SandboxVars.MELens and SandboxVars.MELens.GeneratorWear}
local groundGenerator
local rain = getClimateManager():getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY)
local rainAdmin, rainValue = rain:isEnableAdmin(), rain:getAdminValue()
local function restore()
    gd.fuel,gd.on,gd.wear=saved.fuel,saved.on,saved.wear; gen:setCondition(saved.condition)
    battery:setUsedDelta(saved.battery)
    wd.water,wd.tainted=saved.water,saved.tainted; U.setPropane(v,saved.propane,true)
    od.on,od.heat=saved.ovenOn,saved.heat; hd.on=saved.heaterOn; pd.temperature=saved.temperature
    v:getModData().MELensLightsOff=saved.lights
    getGameTime():setTimeOfDay(saved.timeOfDay); U.observeLamps(v,true)
    if SandboxVars.MELens then
        SandboxVars.MELens.GeneratorFuelUse=saved.fuelOption
        SandboxVars.MELens.GeneratorWear=saved.wearOption
    end
    if groundGenerator then groundGenerator:setActivated(false); groundGenerator:setFuel(0) end
    rain:setAdminValue(rainValue); rain:setEnableAdmin(rainAdmin); getClimateManager():update()
    H.shoreTick(); U.powerLost(v); U.updateOven(v,oven,.00001)
end
local ok, err = pcall(function()
    assert(MELens.VERSION=="2.0.6", "wrong native release")
    v:getModData().MELensLightsOff=true
    SandboxVars.MELens = SandboxVars.MELens or {}
    SandboxVars.MELens.GeneratorFuelUse=1; SandboxVars.MELens.GeneratorWear=1
    gd.fuel=.1; gd.on=false; gd.wear=0; gen:setCondition(100); battery:setUsedDelta(.3)
    local unchanged=battery:getCurrentUsesFloat(); U.runGenerator(v,gen,60)
    near(gd.fuel,.1); near(battery:getCurrentUsesFloat(),unchanged)
    record("generator-off-same-tick-control",{fuel=gd.fuel,battery=battery:getCurrentUsesFloat()})
    gd.on=true; U.runGenerator(v,gen,60)
    near(gd.fuel,0); assert(gd.on==false); near(gd.wear,.03125)
    near(battery:getCurrentUsesFloat()-unchanged,.015)
    record("generator-fuel-exhaustion-bounds-native-battery",{fuel=gd.fuel,on=gd.on,wear=gd.wear,
        actualNativeBatteryDelta=battery:getCurrentUsesFloat()-unchanged,requestedHelperDelta=.0075})
    gd.fuel=5; gd.on=true; gd.wear=.9; gen:setCondition(1); battery:setUsedDelta(.3)
    unchanged=battery:getCurrentUsesFloat(); U.runGenerator(v,gen,60)
    near(gd.fuel,4.68); near(gd.wear,0); assert(gen:getCondition()==0 and gd.on==false)
    near(battery:getCurrentUsesFloat()-unchanged,.048)
    record("generator-condition-exhaustion-bounds-output",{fuel=gd.fuel,on=gd.on,condition=gen:getCondition(),
        actualNativeBatteryDelta=battery:getCurrentUsesFloat()-unchanged})
    gd.on=false; gd.fuel=0; gen:setCondition(100)
    battery:setUsedDelta(.3); U.observeLamps(v,true)
    local hour=getGameTime():getWorldAgeHours()
    getGameTime():setTimeOfDay(saved.timeOfDay+1); U.observeLamps(v)
    near(battery:getCurrentUsesFloat(),.3)
    record("native-lamps-off-time-control",{battery=battery:getCurrentUsesFloat()})
    v:getModData().MELensLightsOff=false; U.observeLamps(v,true)
    hour=getGameTime():getWorldAgeHours()
    getGameTime():setTimeOfDay(saved.timeOfDay+2); U.observeLamps(v)
    local elapsed=getGameTime():getWorldAgeHours()-hour
    near(battery:getCurrentUsesFloat(),.3-.0018*elapsed)
    assert(elapsed>.99 and elapsed<1.01)
    record("native-occupied-lamps-drain-once",{elapsedHours=elapsed,battery=battery:getCurrentUsesFloat()})
    getGameTime():setTimeOfDay(saved.timeOfDay); v:getModData().MELensLightsOff=true; U.observeLamps(v,true)
    U.setPropane(v,.5,true); od.on=false; od.heat=1; hd.on=false; pd.temperature=0
    U.updateOven(v,oven,10); U.updateHeater(v,heater,10)
    near(U.propaneLevel(v),.5); near(od.heat,1); near(pd.temperature,0)
    record("appliances-off-same-tick-control",{propane=U.propaneLevel(v),heat=od.heat,temperature=pd.temperature})
    od.on=true; hd.on=true; U.updateOven(v,oven,10); U.updateHeater(v,heater,10)
    near(U.propaneLevel(v),.4875); near(od.heat,2); near(pd.temperature,5)
    near(oven:getItemContainer():getCustomTemperature(),2)
    record("native-stove-heater-consume-and-heat",{propane=U.propaneLevel(v),heat=od.heat,temperature=pd.temperature})
    od.on=false; hd.on=false; U.updateOven(v,oven,10); U.updateHeater(v,heater,10)
    near(od.heat,1.5); near(pd.temperature,4); near(U.propaneLevel(v),.4875)
    record("native-appliance-cooldown",{propane=U.propaneLevel(v),heat=od.heat,temperature=pd.temperature})
    U.setPropane(v,.00001,true); od.on=true; hd.on=true; U.updateOven(v,oven,10)
    near(U.propaneLevel(v),0); assert(not od.on and not hd.on)
    U.addPropane(v,.25); assert(not od.on and not hd.on)
    record("propane-exhaustion-stops-both-without-refill-restart",{propane=U.propaneLevel(v),stove=od.on,heater=hd.on})
    local fridge
    for i=1,#MELens.profileFor(v).spots do
        local part=P.spotPart(v,i); if P.pieceAt(part)=="fridge" then fridge=part; break end
    end
    assert(fridge and fridge:getItemContainer(), "native fridge missing")
    local sq=v:getSquare(); local ground=getCell():getGridSquare(sq:getX()+3,sq:getY(),sq:getZ())
    assert(ground and not ground:getGenerator(), "shore fixture square occupied")
    local item=instanceItem("Base.Generator"); item:setCondition(100); item:getModData().fuel=50
    groundGenerator=IsoGenerator.new(item,getCell(),ground); groundGenerator:setFuel(50); groundGenerator:setConnected(true)
    groundGenerator:setActivated(false); H.shoreTick(); U.updateFridge(v,fridge,0)
    assert(not U.hasPower(v)); near(fridge:getItemContainer():getCustomTemperature(),0)
    groundGenerator:setActivated(true); H.shoreTick(); U.updateFridge(v,fridge,0)
    assert(U.hasPower(v)); near(fridge:getItemContainer():getCustomTemperature(),.2)
    gd.on=true; gd.fuel=.1; U.setSwitch(v,"generator",false)
    assert(U.hasPower(v)); near(fridge:getItemContainer():getCustomTemperature(),.2)
    record("native-shore-generator-and-onboard-handoff",{shorePower=true,fridgeTemperature=fridge:getItemContainer():getCustomTemperature()})
    groundGenerator:setActivated(false); H.shoreTick(); assert(not U.hasPower(v))
    near(fridge:getItemContainer():getCustomTemperature(),0)
    record("shore-power-loss-stops-cooling",{shorePower=false,fridgeTemperature=fridge:getItemContainer():getCustomTemperature()})
    assert(v:getSquare():isOutside(), "rain fixture must be outdoors")
    rain:setEnableAdmin(true); rain:setAdminValue(0); getClimateManager():update()
    wd.water=0; wd.tainted=false; H.rainTick(); near(wd.water,0)
    record("native-no-rain-same-tick-control",{rain=getClimateManager():getRainIntensity(),water=wd.water})
    rain:setAdminValue(.5); getClimateManager():update()
    local intensity=getClimateManager():getRainIntensity(); assert(intensity>.02,"native rain override failed")
    H.rainTick(); near(wd.water,intensity*2.5); assert(wd.tainted)
    record("native-rain-collects-tainted-water",{rain=intensity,water=wd.water,tainted=wd.tainted})
end)
restore()
assert(ok,err)
return {passed=true,scope="native component probes; real engine objects; direct update calls; no UI claim",cases=results}

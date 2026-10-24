-- Production animal authority, needs and quiet-time checks with engine doubles.
-- Actual animation clips, input, rendering and replication require native tests.
do
    local M,A,L,P=MELens,MELens.Animals,MELens.Loose,MELens.Parts
    local saved={}
    for _,k in ipairs({'isClient','isServer','getGameTime','ZombRand','ZombRandFloat',
            'AnimalDefinitions','CharacterStat','Fluid','CompanionDogs','instanceof',
            'getCell','getNumActivePlayers','getSpecificPlayer'}) do saved[k]=_G[k] end
    local oldPoints,oldFloor,oldList,oldPrune,oldCharacter,oldFits=L.floorPoints,L.floorContainer,L.list,L.prune,P.characterAt,L.fitsSurface
    local hour=100
    getGameTime=function() return {getWorldAgeHours=function() return hour end} end
    isClient,isServer=function() return false end,function() return false end
    ZombRand=function() return 0 end
    ZombRandFloat=function(a,b) return b end
    CharacterStat={HUNGER='hunger',THIRST='thirst'}
    Fluid={Water='water',TaintedWater='tainted'}
    CompanionDogs=nil
    AnimalDefinitions={animals={hen={canBePicked=true,eatTypeTrough='Vegetables',thirstHungerTrigger=.1}}}
    instanceof=function(o,c) return o and o.class==c end
    local function list(values)
        local l=values or {};function l:size() return #self end;function l:get(i) return self[i+1] end;return l
    end
    local function animal(id)
        local a={id=id,class='IsoAnimal',values={hunger=0,thirst=0},data={}}
        function a:getAnimalID() return self.id end
        function a:getAnimalType() return 'hen' end
        function a:getAnimalTrailerSize() return 30 end
        function a:isDead() return false end
        function a:getHealth() return 100 end
        function a:getModData() return self.data end
        function a:getVehicle() return self.vehicle end
        function a:getStats() return {get=function(_,k) return a.values[k] end,set=function(_,k,v) a.values[k]=v end} end
        function a:getData() return {eatItem=function(_,item) a.values.hunger=0;item.eaten=true end} end
        return a
    end
    local profile={floorY=0,vanillaSeats={},door={x=0,z=0}}
    M.Profiles['Base.AnimalsRegression']=profile
    local v={data={},animals=list(),adds=0,partUpdates=0,transmits=0,passenger='MELensCabin'}
    function v:getScriptName() return 'Base.AnimalsRegression' end
    function v:getAnimals() return self.animals end
    function v:getModData() return self.data end
    function v:getSeat() return 0 end
    function v:getScript() return {getFullName=function() return 'Base.AnimalsRegression' end,
        getPassenger=function() return {getId=function() return v.passenger end} end} end
    function v:getAnimalById(id) for _,a in ipairs(self.animals) do if a.id==id then return a end end end
    function v:updateParts() self.partUpdates=self.partUpdates+1 end
    function v:transmitModData() self.transmits=self.transmits+1 end
    local points={{0,0},{.6,0},{1.2,0}}
    L.floorPoints=function() return points end
    local items,entries={},{}
    L.floorContainer=function() return {getItemById=function(_,id) return items[id] end} end
    L.list=function() return entries end
    L.prune=function() return nil end
    L.fitsSurface=function() return true end
    local hen=animal(1);v.animals[1]=hen
    local r=A.place(v,hen,0,0,0)
    check(r.nextMove>=hour+A.REST_MINUTES/60,'new animal does not receive a quiet interval')
    for i=1,19 do hour=100+i/60;A.updateVehicle(v,profile) end
    check(r.x==0 and r.z==0,'satisfied animal paces during its quiet interval')
    hour=100+21/60;A.updateVehicle(v,profile)
    local x,z=r.x,r.z
    check(x~=0 or z~=0,'movement fixture did not exercise voluntary movement')
    for i=1,10 do A.updateVehicle(v,profile) end
    check(r.x==x and r.z==z,'same-time updates repeatedly move a satisfied animal')
    r.nextMove=nil;A.updateVehicle(v,profile)
    check(r.x==x and r.z==z and r.nextMove>hour,'old saved record starts a quiet interval without wandering')
    L.fitsSurface=function(_,_,_,x) return x<.25 or x>.45 end
    check(not A.clearStep(v,profile,0,0,.6,0),'free endpoints permit walking through furniture')
    check(A.clearStep(v,profile,0,0,0,.6),'clear short step rejected')
    L.fitsSurface=function() return true end

    local fluid={amount=.25}
    function fluid:isEmpty() return self.amount<=0 end
    function fluid:getRatioForFluid(kind) return kind=='water' and 1 or 0 end
    function fluid:getAmount() return self.amount end
    function fluid:removeFluid(n) self.amount=math.max(0,self.amount-n) end
    local dish={class='InventoryItem'}
    function dish:getFullType() return 'Base.WaterDish' end
    function dish:getFluidContainer() return fluid end
    function dish:isSealed() return false end
    r.x,r.z,r.p,r.u=0,0,'idle',nil
    hen.values.thirst=.6;items[10]=dish;entries={{id=10,x=.3,z=0,s=0}}
    A.updateVehicle(v,profile)
    check(math.abs(hen.values.thirst-.1)<.000001 and fluid.amount==0,'drink does not conserve water/restore thirst')
    check(r.x==0 and r.z==0 and r.p=='drink','animal already at a bowl unnecessarily shuffles')
    check(r.nextMove>=r.u+A.REST_MINUTES/60,'feeding does not postpone voluntary wandering')
    local food={class='Food'}
    function food:getFullType() return 'Base.Corn' end
    function food:isRotten() return false end
    function food:isBurnt() return false end
    function food:getFoodType() return 'Vegetables' end
    function food:getAnimalFeedType() return nil end
    items[11]=food;entries[#entries+1]={id=11,x=.3,z=0,s=0}
    hen.values.hunger=.6;r.u=nil
    A.updateVehicle(v,profile)
    check(food.eaten and hen.values.hunger==0 and r.p=='eat','no water prevents a hungry animal from eating')

    -- Queued operations must revalidate authority before changing the list.
    local inv={items={}}
    function inv:getItemWithID(id) return self.items[id] end
    function inv:containsID(id) return self.items[id]~=nil end
    local p={}
    function p:getInventory() return inv end
    function p:getVehicle() return v end
    function p:isTimedActionInstant() return true end
    P.characterAt=function() return 0,0 end
    local carried=animal(2);local item={class='AnimalInventoryItem'}
    function item:getAnimal() return carried end
    function item:getID() return 99 end
    function v:addAnimalFromHandsInTrailer(a) self.adds=self.adds+1;self.animals[#self.animals+1]=a;inv.items[99]=nil end
    v.animals=list();v.data={};inv.items[99]=item
    local action=MELensDropAnimal:new(p,v,item,.6,0,0)
    check(action:isValid(),'valid carried animal rejected before the action')
    inv.items[99]=nil
    check(not action:complete() and v.adds==0 and v.partUpdates==0,'stale carried item can duplicate an animal')
    inv.items[99]=item;points={}
    check(not action:complete() and inv.items[99]==item and v.adds==0,'full interior consumes a carried animal')
    points={{0,0},{.6,0},{1.2,0}}
    action.x,action.z,action.f=1e20,0,0/0
    check(action:complete() and v.adds==1 and v.partUpdates==1,'valid atomic drop does not complete')
    local placed=A.record(v,carried)
    check(placed.x==.6 and placed.z==0 and placed.f==0,'remote/nonfinite coordinates corrupt animal placement')
    check(not action:complete() and v.adds==1,'repeated completion duplicates a committed animal')
    local pickup=MELensPickUpAnimal:new(p,v,2)
    v.passenger='Driver';profile.vanillaSeats={'Driver'}
    check(not pickup:isValid() and not pickup:complete(),'cab driver can take an interior animal')
    v.passenger='MELensCabin';AnimalDefinitions.animals.hen.canBePicked=false
    check(not pickup:isValid(),'server accepts an uncarryable animal')
    AnimalDefinitions.animals.hen.canBePicked=true;placed.x=3
    check(not pickup:complete(),'stale distant pickup mutates the vehicle animal list')
    check(#v.animals==1 and inv.items[99]==nil,'rejected pickup changed committed animal ownership')
    placed.x=0
    CompanionDogs={isDog=function() return true end,isCompanion=function() return true end,isOwnedBy=function() return false end}
    check(not pickup:isValid() and not pickup:complete() and #v.animals==1,
        'another player can carry a Companion Dogs companion out of the interior')
    CompanionDogs.isOwnedBy=function(_,player) return player==p end
    check(pickup:isValid(),'companion owner cannot pick up their own interior dog')
    function carried:canBePicked() return false end
    check(not pickup:isValid(),'interior pickup bypasses the games normal animal carry restriction')
    carried.canBePicked=nil
    CompanionDogs=nil

    -- The last following dog leaving must clear its saved occupancy immediately:
    -- the normal minute pass no longer visits a vehicle with an empty list.
    local fresh=animal(3)
    function fresh:addToWorld() self.added=true end
    function v:removeAnimalFromTrailer() self.animals=list();return fresh end
    local owner={getVehicle=function() return nil end}
    CompanionDogs={isDog=function() return true end,isCompanion=function() return true end,
        STATE_FOLLOW='follow',getState=function() return 'follow' end,getOwnerPlayer=function() return owner end}
    getNumActivePlayers=function() return 1 end;getSpecificPlayer=function() return owner end
    getCell=function() return {getVehicles=function() return {iterator=function()
        local pending=true;return {hasNext=function() return pending end,next=function() pending=false;return v end}
    end} end} end
    local transmits=v.transmits
    A.onMinute()
    check(fresh.added and #v.animals==0,'following dog was not returned to the world')
    check(A.record(v,carried)==nil and v.transmits>transmits,'last dog leaves a ghost occupancy record on peers')

    -- Delegate loaded care to Companion Dogs, and preserve its rule that the
    -- first pass after streaming must not charge the time spent unloaded.
    local dog=animal(4);dog.vehicle=v;v.animals=list({dog});A.place(v,dog,0,0,0)
    local loaded=true
    getCell=function() return {getVehicles=function() return {
        contains=function(_,candidate) return loaded and candidate==v end,
        iterator=function() local pending=loaded;return {hasNext=function() return pending end,next=function() pending=false;return v end} end
    } end} end
    CompanionDogs={isDog=function() return true end,isCompanion=function() return true end,
        STATE_FOLLOW='follow',getState=function() return 'stay' end,getOwnerPlayer=function() return owner end,
        data=function(a) return a.data end,worldMinutes=function() return hour*60 end,
        wasInPlay=function() return false end,upkeepEnabled=function() return true end}
    CompanionDogs.updateUpkeep=function(a,_,d)
        local minutes=hour*60;local elapsed=minutes-(d.lastUpkeepMin or minutes)
        d.lastUpkeepMin=minutes
        if CompanionDogs.wasInPlay(a) then a.values.hunger=a.values.hunger+elapsed*.01 end
    end
    A.onMinute();check(dog.values.hunger==0,'initial trailer care charges an unknown prior interval')
    hour=hour+1/60;A.onMinute()
    check(math.abs(dog.values.hunger-.01)<.00001,'loaded trailer dog never receives Companion Dogs upkeep')
    loaded=false;A.onMinute();hour=hour+12;loaded=true;A.onMinute()
    check(math.abs(dog.values.hunger-.01)<.00001,'trailer care charges unloaded hours on return')
    CompanionDogs.troughFeedTrigger=function(p) return p==owner and .4 or .9 end
    check(A.trigger(dog)==.4,'interior dog ignores its owners Companion Dogs feeding threshold')
    local resting=A.record(v,dog)
    resting.nextMove=hour-1;entries={}
    local restX,restZ=resting.x,resting.z
    for _=1,3 do hour=hour+1;A.updateVehicle(v,profile) end
    check(resting.x==restX and resting.z==restZ,'Stay permits voluntary pacing after the quiet timer expires')
    CompanionDogs.getState=function() return 'follow' end
    A.updateVehicle(v,profile)
    check(resting.x~=restX or resting.z~=restZ,'Stay guard also prevents a following dog from moving')
    CompanionDogs.getState=function() return 'stay' end
    local bowl={data={},refreshes=0}
    function bowl:getFullType() return 'Base.CompanionDogsBowl' end
    function bowl:getModData() return self.data end
    function bowl:getContainer() return nil end
    CompanionDogs.absorbRealWater=function(b)
        if b.data.cdWater then return false end
        b.data.cdWater=80;return true
    end
    CompanionDogs.refreshDishModel=function(b) b.refreshes=b.refreshes+1 end
    items[12]=bowl;entries={{id=12,x=.3,z=0,s=0}}
    isClient=function() return true end
    check(#A.sources(v,profile,dog,'water',0,0)==0 and bowl.data.cdWater==nil,
        'client source preview mutates real-water bowl stock')
    isClient=function() return false end
    check(#A.sources(v,profile,dog,'water',0,0)==1 and bowl.data.cdWater==80 and bowl.refreshes==1,
        'authority does not convert real filled water through Companion Dogs')
    A.sources(v,profile,dog,'water',0,0)
    check(bowl.refreshes==1,'repeated source scans credit the same filled bowl again')
    -- Armed dogs can have zero native hunger while CD's saved value is hungry.
    -- Stay must permit a required meal and retain the real bowl's remaining stock.
    CompanionDogs.getHunger=function(a) return a.data.gunHungerSave or a.values.hunger end
    CompanionDogs.setNeed=function(a,kind,value)
        a.values[kind]=value
        if kind=='hunger' then a.data.gunHungerSave=value end
    end
    dog.values.hunger,dog.values.thirst,dog.data.gunHungerSave=0,0,.6
    resting.x,resting.z,resting.p,resting.u=0,0,'idle',nil
    bowl.data.cdFoodMeals=100
    A.updateVehicle(v,profile)
    check(math.abs(dog.data.gunHungerSave-.1)<.00001 and resting.p=='eat',
        'Stay or cleared native hunger prevents an armed companion from eating')
    check(math.abs(bowl.data.cdFoodMeals-50)<.00001,'armed-dog feeding does not conserve bowl stock')
    v.animals=list();A.onMinute()
    local ghost=false;for _ in pairs(A.records(v,false)) do ghost=true end
    check(not ghost,'external Bring/extraction leaves a ghost occupancy record')

    M.Profiles['Base.AnimalsRegression']=nil
    L.floorPoints,L.floorContainer,L.list,L.prune,P.characterAt,L.fitsSurface=oldPoints,oldFloor,oldList,oldPrune,oldCharacter,oldFits
    for _,k in ipairs({'isClient','isServer','getGameTime','ZombRand','ZombRandFloat',
            'AnimalDefinitions','CharacterStat','Fluid','CompanionDogs','instanceof',
            'getCell','getNumActivePlayers','getSpecificPlayer'}) do _G[k]=saved[k] end
end

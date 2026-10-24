-- Production initialization contracts with isolated engine doubles, not native save/MP proof.
local M, P, U = MELens, MELens.Parts, MELens.Utilities
local old = { isClient = isClient, instanceItem = instanceItem, SandboxVars = SandboxVars,
    applyPiece = P.applyPiece, fillFurniture = P.fillFurniture, canReach = P.canReach }
local client, made, fills = false, 0, 0
local function empty(values)
    for _ in pairs(values) do return false end
    return true
end
isClient = function() return client end
SandboxVars = { MELens = { StartFurnished = true, FurnitureLoot = true } }
instanceItem = function(full)
    made = made + 1
    return { getFullType = function() return full end }
end
P.applyPiece = function() end -- Model visibility/capacity is outside these initialization contracts.
P.fillFurniture = function() fills = fills + 1 end

local vehicle = { getScript = function() return { getFullName = function() return "Base.Trailer54FlyingCloud22" end } end }
local function part(item, data, contents, condition)
    local c = { items = contents or {}, explored = false }
    function c:isEmpty() return #self.items == 0 end
    function c:isExplored() return self.explored end
    local p = { item = item, data = data or {}, container = c, condition = condition or -1, conditionSets = 0 }
    function p:getId() return "MELensSpot1" end
    function p:getInventoryItem() return self.item end
    function p:setInventoryItem(value) self.item = value end
    function p:getItemContainer() return self.container end
    function p:getModData() return self.data end
    function p:getCondition() return self.condition end
    function p:setCondition(value) self.condition = value; self.conditionSets = self.conditionSets + 1 end
    return p
end

local fresh = part()
P.createSpot(vehicle, fresh)
check(fresh.item and fresh.item:getFullType() == "Base.MELensRV_Bed", "new existing-vehicle spot lacks its default")
check(fresh.data[P.INITIALIZED_KEY] == true and made == 1 and fills == 1, "new spot initialization/loot missing")
local installed = fresh.item
P.createSpot(vehicle, fresh)
check(fresh.item == installed and made == 1 and fills == 1, "repeated create replaces furniture or refills loot")

local savedItem = { getFullType = function() return "Base.MELensRV_Cabinet" end }
local savedCargo = { token = "keep-original-reference" }
local saved = part(savedItem, {}, { savedCargo })
P.createSpot(vehicle, saved)
check(saved.item == savedItem and saved.container.items[1] == savedCargo, "saved furniture/storage replaced")
check(made == 1 and fills == 1, "saved furniture rerolls defaults or loot")

local deliberatelyEmpty = part()
P.initSpot(vehicle, deliberatelyEmpty)
P.createSpot(vehicle, deliberatelyEmpty)
check(not deliberatelyEmpty.item and deliberatelyEmpty.data[P.INITIALIZED_KEY], "old cleared spot refurnished")
check(made == 1 and fills == 1, "old cleared spot generates items")
local reloadedEmpty = part(nil, { [P.INITIALIZED_KEY] = deliberatelyEmpty.data[P.INITIALIZED_KEY] })
P.createSpot(vehicle, reloadedEmpty)
check(not reloadedEmpty.item and made == 1, "saved initialization marker does not preserve cleared layout")

local orphaned = part(nil, {}, { savedCargo })
P.createSpot(vehicle, orphaned)
check(not orphaned.item and orphaned.container.items[1] == savedCargo and made == 1 and fills == 1,
    "saved orphan storage gains defaults or loses contents")
P.canReach = function() return true end
check(P.containerTest(vehicle, orphaned, {}), "saved contents become inaccessible without furniture")
P.canReach = function() return false end
check(not P.containerTest(vehicle, orphaned, {}), "orphan storage bypasses reach")

SandboxVars.MELens.StartFurnished = false
local unfurnished = part()
P.createSpot(vehicle, unfurnished)
check(not unfurnished.item and unfurnished.data[P.INITIALIZED_KEY], "unfurnished option not retained")
SandboxVars.MELens.StartFurnished = true
P.createSpot(vehicle, unfurnished)
check(not unfurnished.item and made == 1, "changed start option refurnishes initialized vehicle")

client = true
local replica = part()
P.createSpot(vehicle, replica)
P.initSpot(vehicle, replica)
check(not replica.item and not replica.data[P.INITIALIZED_KEY] and made == 1 and fills == 1,
    "client creates furniture/loot or initialization authority")
client = false

local inside = { getVehicle = function() return vehicle end }
local outside = { getVehicle = function() return nil end }
local oldCargo = part(nil, {}, { savedCargo }) -- explored=false deliberately
check(P.ki5StorageTest(vehicle, oldCargo, inside), "unexplored nonempty original cargo hidden after install")
check(not P.ki5StorageTest(vehicle, oldCargo, outside), "original cargo exposed outside the interior")
oldCargo.container.items = {}
check(not P.ki5StorageTest(vehicle, oldCargo, inside), "empty original cargo remains visible")

local generator = part()
U.createGenerator(vehicle, generator)
check(generator.data.fuel == 0 and generator.data.on == false and generator.condition == 100,
    "new generator defaults missing")
U.createGenerator(vehicle, generator)
check(generator.conditionSets == 1, "repeated generator create repairs condition")
local running = part(nil, { fuel = 6.25, on = true, wear = 0.4 }, {}, 17)
U.createGenerator(vehicle, running)
check(running.data.fuel == 6.25 and running.data.on == true and running.data.wear == 0.4
    and running.condition == 17 and running.conditionSets == 0, "saved generator fuel/state/condition reset")
local broken = part(nil, {}, {}, 0)
U.createGenerator(vehicle, broken)
check(broken.condition == 0 and broken.conditionSets == 0, "broken generator repaired on initialization")
local partialGenerator = part(nil, { on = true }, {}, 21)
U.createGenerator(vehicle, partialGenerator)
check(partialGenerator.data.fuel == 0 and partialGenerator.data.on == true
    and partialGenerator.condition == 21, "partial generator initialization overwrites saved fields")

local water = part()
U.createWaterTank(vehicle, water)
check(water.data.water == 0 and water.data.tainted == false, "new water tank defaults missing")
local usedWater = part(nil, { water = 28.5, tainted = true })
U.createWaterTank(vehicle, usedWater)
U.createWaterTank(vehicle, usedWater)
check(usedWater.data.water == 28.5 and usedWater.data.tainted == true, "saved tank emptied/untainted")
local emptyWater = part(nil, { water = 0, tainted = false })
U.createWaterTank(vehicle, emptyWater)
check(emptyWater.data.water == 0 and emptyWater.data.tainted == false, "saved false/zero fields overwritten")
client = true
local clientGenerator, clientWater = part(), part()
U.createGenerator(vehicle, clientGenerator)
U.createWaterTank(vehicle, clientWater)
check(empty(clientGenerator.data) and clientGenerator.conditionSets == 0 and empty(clientWater.data),
    "client initializes authoritative utilities")

-- Appended cargo layouts furnish a fresh vehicle once; a saved cleared conversion
-- gains no new items, even when repair supplies the serialization placeholder.
client=false
local stockProfile={factoryLayout="fixture-cargo",legacySpotCount=1,spots={
    {empty=true,length=1.5,depth=.55,wall="left"},
    {factory=true,default="parcels",pieces={"parcels"},length=.6,depth=.5,wall="left"}}}
M.Profiles["Base.FactoryLifecycleFixture"]=stockProfile
local function conversion()
    local v={data={}}
    function v:getScript() return {getFullName=function() return "Base.FactoryLifecycleFixture" end} end
    function v:getModData() return self.data end
    return v
end
local freshVan=conversion()
P.createSpot(freshVan,part())
check(freshVan.data.MELensFactoryLayout==stockProfile.factoryLayout,"fresh cargo vehicle not identified")
local factoryIndex=stockProfile.legacySpotCount+1
local full=part({getFullType=function() return P.EMPTY_ITEM end})
function full:getId() return P.SPOT..factoryIndex end
local beforeMade,beforeFills=made,fills
P.createSpot(freshVan,full)
check(full.item and P.pieceOfItem(full.item)==stockProfile.spots[factoryIndex].default,"fresh factory freight missing")
check(made==beforeMade+1 and fills==beforeFills+1,"factory freight did not fill once")
P.createSpot(freshVan,full)
check(made==beforeMade+1 and fills==beforeFills+1,"factory freight create refills cargo")
full.item=nil
P.createSpot(freshVan,full)
check(not full.item,"looted cargo refurnished on repair")
local savedVan=conversion()
P.createSpot(savedVan,part(nil,{[P.INITIALIZED_KEY]=true}))
local added=part();function added:getId() return P.SPOT..factoryIndex end
P.createSpot(savedVan,added)
check(not added.item and added.data[P.INITIALIZED_KEY],"appended layout overwrote a saved/cleared conversion")

-- Floor freight uses the same one-time authority as fittings. Keeping exact item
-- references here catches duplication/refill without pretending to test native saves.
local oldLoose=M.Loose
local placed={}
M.Loose={fitsSurface=function(_,_,_,x) return x<1 end,
    set=function(_,item,x,y,z,r,s) placed[#placed+1]={item=item,x=x,y=y,z=z,r=r,s=s} end}
stockProfile.floorY=-.4
stockProfile.factoryFloor={{t="Base.PropaneTank",x=.4,z=-.5,hx=.17,hz=.17},
    {t="Base.PropaneTank",x=-.4,z=-.5,hx=.17,hz=.17},
    {t="Base.PropaneTank",x=2,z=-.5,hx=.17,hz=.17}}
local function floorPart(contents,capacity)
    local p=part(nil,{},contents)
    local c=p.container
    function c:AddItem(t) local i={type=t};self.items[#self.items+1]=i;return i end
    function c:Remove(item) for i,v in ipairs(self.items) do if v==item then table.remove(self.items,i);return end end end
    function c:getCapacityWeight() return #self.items*10 end
    function c:getCapacity() return capacity or 100 end
    function c:setExplored(value) self.explored=value end
    return p
end
local floor=floorPart()
P.createFloor(freshVan,floor)
check(#floor.container.items==2 and #placed==2,"floor cargo failed to populate valid positions only")
check(placed[1].item==floor.container.items[1] and placed[2].item==floor.container.items[2]
    and placed[1].y==stockProfile.floorY and placed[1].s==0,"floor cargo is a copied prop or wrong surface")
local firstTank=floor.container.items[1]
P.createFloor(freshVan,floor)
check(#floor.container.items==2 and floor.container.items[1]==firstTank and #placed==2,"floor cargo duplicated on create")
floor.container.items={}
P.createFloor(freshVan,floor)
check(#floor.container.items==0,"looted floor cargo refilled")
local priorFloor=floorPart({savedCargo})
P.createFloor(freshVan,priorFloor)
check(#priorFloor.container.items==1 and priorFloor.container.items[1]==savedCargo,"existing floor items replaced")
local loadedFloor=floorPart()
P.initFloor(freshVan,loadedFloor);P.createFloor(freshVan,loadedFloor)
check(#loadedFloor.container.items==0,"saved empty floor refilled")
local oldVehicleFloor=floorPart()
P.createFloor(savedVan,oldVehicleFloor)
check(#oldVehicleFloor.container.items==0,"appended floor cargo added to old vehicle")
local capped=floorPart(nil,10)
P.createFloor(freshVan,capped)
check(#capped.container.items==1,"floor cargo exceeds container capacity")
for _,option in ipairs({"StartFurnished","FurnitureLoot"}) do
    SandboxVars.MELens[option]=false
    local disabled=floorPart();P.createFloor(freshVan,disabled)
    check(#disabled.container.items==0,"floor cargo ignores sandbox option "..option)
    SandboxVars.MELens[option]=true;P.createFloor(freshVan,disabled)
    check(#disabled.container.items==0,"sandbox toggle refills floor "..option)
end
client=true
local replicatedFloor=floorPart()
P.createFloor(freshVan,replicatedFloor);P.initFloor(freshVan,replicatedFloor)
check(#replicatedFloor.container.items==0 and not replicatedFloor.data[P.INITIALIZED_KEY],"client creates authoritative floor cargo")
client=false
M.Loose=oldLoose
M.Profiles["Base.FactoryLifecycleFixture"]=nil
isClient, instanceItem, SandboxVars = old.isClient, old.instanceItem, old.SandboxVars
P.applyPiece, P.fillFurniture, P.canReach = old.applyPiece, old.fillFurniture, old.canReach

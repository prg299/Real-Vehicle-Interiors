# Save the accepted utility state and inventory in this disposable profile only.
$code = @'
local F=MELensFeatureTest; assert(F and F.vehicle and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0)
local v,p,U,P=F.vehicle,getPlayer(),MELens.Utilities,MELens.Parts
U.setSwitch(v,"generator",false); U.setSwitch(v,"stove",false); U.setSwitch(v,"heater",false)
v:getModData().MELensLightsOff=true; U.observeLamps(v,true)
local g,w=U.generatorState(v),U.waterState(v)
local state={version=MELens.VERSION, fuel=g.fuel,condition=g.condition,wear=g.part:getModData().wear or 0,
    water=w.water,tainted=w.tainted,propane=U.propaneLevel(v),inventory={},furniture={}}
state.name=MELens.Home.givenName(v) or ""
local red,green,blue=MELens.Home.paint(v); state.paint=red and {r=red,g=green,b=blue} or false
local inv=p:getInventory():getItems()
for i=0,inv:size()-1 do local item=inv:get(i); local fc=item:getFluidContainer()
    state.inventory[#state.inventory+1]={id=item:getID(),fullType=item:getFullType(),amount=fc and fc:getAmount() or 0}
end
local profile=MELens.profileFor(v)
for i=1,#profile.spots do local part=P.spotPart(v,i); local item=part:getInventoryItem()
    state.furniture[#state.furniture+1]={id=part:getId(),piece=item and item:getFullType() or "empty",
        itemId=item and item:getID(),condition=item and item:getCondition()}
end
local floor=MELens.Loose.floorContainer(v); local pencil=floor:getFirstEval(function(i) return i:getModData().MELensFinalFeatureFloor==true end)
if not pencil then pencil=floor:AddItem("Base.Pencil"); pencil:getModData().MELensFinalFeatureFloor=true end
state.floorItem=pencil:getID()
state.floorItems={}; local items=floor:getItems()
for i=0,items:size()-1 do local item=items:get(i); state.floorItems[#state.floorItems+1]={id=item:getID(),fullType=item:getFullType()} end
state.loose={}
for id,entry in pairs(MELens.Loose.positions(v,false) or {}) do
    state.loose[id]={x=entry.x,y=entry.y,z=entry.z,r=entry.r,s=entry.s,t=entry.t}
end
v:getModData().MELensFinalFeatureSave=state
GameWindow.save(true)
return {world=getWorld():getWorld(),state=state}
'@
$state = Lua $code
$state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $runPath 'feature-save-prepared.json') -Encoding utf8
Shot 'features-saved'
Write-Host 'NATIVE_FEATURE_STATE_SAVED'
[IO.File]::WriteAllText((Join-Path $runPath 'request.json'),'{"action":"stop"}')

# Disposable scene only; called inside workshop-capture.ps1's guarded inactive desktop.
$spawn = (Get-Content -LiteralPath (Join-Path $Lens.Root 'dev\lua\spawn_one.lua') -Raw).Replace('NAME', 'Base.87fordF700box').Replace('tonumber("7")', 'tonumber("-4")')
Write-Host (Lua $spawn)
[void](Wait-Lua 'local v=MELensTest and MELensTest.vehicle; return v and v:getPartCount()>0 and "spawned" or "waiting"' '^spawned$' 30)
[void](Wait-Lua 'local v=MELensTest and MELensTest.vehicle; return v and MELens.canWalkIn(getPlayer(),v) and "settled" or "waiting"' '^settled$' 45)
$layout = Lua @'
local v,P=MELensTest.vehicle,MELens.Parts
local profile=MELens.profileFor(v)
local rows,boxes,bare,furniture={},0,0,0
for i,spot in ipairs(profile.spots) do
    local part=P.spotPart(v,i)
    local item=part:getInventoryItem()
    assert((item==nil)==(spot.empty==true),"repair changed intended occupancy at spot "..i)
    if not spot.cargo then furniture=furniture+1
    elseif item then boxes=boxes+1 else bare=bare+1 end
    rows[#rows+1]={index=i,level=spot.level,empty=spot.empty==true,cargo=spot.cargo==true,id=item and item:getID()}
end
-- 2.0.8: 18 bare furniture places along the walls (cleared boxes make room for furniture) after the 63 box places
assert(boxes==46 and bare==17 and furniture==18,"unexpected initial box layout")
return {version=MELens.VERSION,boxes=boxes,bare=bare,furniture=furniture,rows=rows,stockRepairResultUnmodified=true}
'@
$layout | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $runPath 'repair-layout.json') -Encoding utf8
[void](Lua @'
local p,v=getPlayer(),MELensTest.vehicle
ISTimedActionQueue.add(ISPathFindAction:pathToVehicleSeat(p,v,MELens.cabinSeat(v)))
getCore():setAutoZoom(0,false)
for i=1,3 do getCore():doZoomScroll(0,1) end
MEMCNativeLab.releaseKeys()
getGameTime():setTimeOfDay(12)
ISUIHandler.setVisibleAllUI(false)
return true
'@)
[void](Wait-Lua 'local p=getPlayer(); return #ISTimedActionQueue.getTimedActionQueue(p).queue==0 and MELens.nearWayIn(p,MELensTest.vehicle,MELens.profileFor(MELensTest.vehicle)) and "at-door" or "waiting"' '^at-door$' 40)
[void](Lua 'local p,v=getPlayer(),MELensTest.vehicle; local outside=v:getPassengerPosition(MELens.cabinSeat(v),"outside"); local point=Vector3f.new(); v:getPassengerPositionWorldPos(outside,point); p:faceLocation(point:x(),point:y()); return true')
[void](Wait-Lua 'local p,v=getPlayer(),MELensTest.vehicle; local part=v:getUseablePart(p); return part and part:getId()==MELens.profileFor(v).standing.door and "facing-door" or "waiting"' '^facing-door$' 10)
Start-Sleep -Seconds 2
Shot 'f700-outside'
[void](Lua 'MEMCNativeLab.holdKey(getCore():getKey("Interact"),200); return true')
[void](Wait-Lua 'local p=getPlayer(); return MELens.isStanding(p) and #ISTimedActionQueue.getTimedActionQueue(p).queue==0 and "inside" or "waiting"' '^inside$' 45)
[void](Lua 'MELens.walkTo(getPlayer(),0,-1.5); return true')
[void](Wait-Lua 'return not MELens.pathing(getPlayer()) and "centered" or "waiting"' '^centered$' 30)
Start-Sleep -Seconds 2
[void](Lua 'getGameTime():setTimeOfDay(12); ISUIHandler.setVisibleAllUI(false); return true')
Shot 'f700-inside-fixed'
[void](Lua 'assert(not MELensRV.shaderError(),MELensRV.shaderError()); MELensRV.clearCutFront(); getGameTime():setTimeOfDay(12); return true')
Start-Sleep -Seconds 1
Shot 'f700-inside-without-hood-exemption'
[void](Lua @'
local profile=MELens.profileFor(MELensTest.vehicle)
assert(profile.cutFront and profile.cutFrontTop,"missing hood exemption in loaded package")
MELensRV.setCutFront(profile.cutFront/profile.mesh.scale)
MELensRV.setCutFrontTop(profile.mesh.lift-profile.cutFrontTop/profile.mesh.scale)
getGameTime():setTimeOfDay(12)
return true
'@)
Start-Sleep -Seconds 1
Shot 'f700-inside-hood-exemption-control'
Write-Host 'F700_VISUAL_READY'

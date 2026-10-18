-- Disposable lifecycle profile only. PHASE is replaced by the phase harness.
-- Setup and read-only receipts; this file never silently deletes possessions.
local phase="PHASE"
local KEY="RVI_LifecycleNative206"
local p=getPlayer()
local hasRVI=MELens~=nil and MELens.VERSION~=nil and MELens.Profiles~=nil
assert(p and p:getCurrentSquare(),"native world/player not ready")
assert(not p:getVehicle(),"all lifecycle checkpoints require the character outside")

local function itemRows(container)
    local rows={}
    if container then
        for i=0,container:getItems():size()-1 do local item=container:getItems():get(i)
            rows[#rows+1]={id=item:getID(),fullType=item:getFullType()}
        end
    end
    table.sort(rows,function(a,b) return a.id<b.id end)
    return rows
end
local function vehicleRows(v,custom)
    local rows={}
    for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i); local id=part:getId()
        local isCustom=id:find("^MELens")~=nil or id:find("^SeatMELens")~=nil
        if isCustom==custom then
            local item=part:getInventoryItem()
            rows[#rows+1]={id=id,itemId=item and item:getID() or -1,itemType=item and item:getFullType() or "",
                partCondition=part:getCondition(),itemCondition=item and item:getCondition() or -1,
                contents=itemRows(part:getItemContainer())}
        end
    end
    table.sort(rows,function(a,b) return a.id<b.id end)
    return rows
end
local v
local vehicles=getCell():getVehicles():iterator()
while vehicles:hasNext() do local candidate=vehicles:next()
    if candidate:getModData()[KEY] then assert(not v,"duplicate lifecycle vehicle"); v=candidate end
end

if phase=="Baseline" then
    assert(not hasRVI and MELensRV==nil,"baseline unexpectedly loaded RVI")
    if not v then
        local square=getCell():getGridSquare(math.floor(p:getX())-8,math.floor(p:getY()),0)
        assert(square,"baseline spawn square not loaded")
        v=assert(addVehicleDebug("Base.87fordF700box",IsoDirections.E,0,square),"baseline KI5 F700 spawn failed")
        v:repair()
        v:getModData()[KEY]={preparing=true}
        MELensLifecycleTest={vehicle=v}
        return {preparing=true,world=getWorld():getWorld(),vehicleId=v:getId()}
    end
    assert(v:getModData()[KEY].preparing,"baseline already captured; use a fresh owned run")
    for i=0,v:getPartCount()-1 do local door=v:getPartByIndex(i):getDoor(); if door then door:setLocked(false) end end
    p:getInventory():AddItem(v:createVehicleKey())
    local cargo=assert(v:getPartById("F700TrunkBX"):getItemContainer(),"KI5 native cargo container missing")
    local hammer=assert(cargo:AddItem("Base.Hammer")); local pencil=assert(cargo:AddItem("Base.Pencil"))
    cargo:setExplored(true) -- committed meaningful cargo; do not invite the stock unexplored loot roll.
    local unexplored
    for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i); local c=part:getItemContainer()
        if part:getId()~="F700TrunkBX" and c and c:getItems():size()==0 then
            unexplored=part:getId(); c:setExplored(false); break
        end
    end
    assert(unexplored,"fixture needs a separate empty native container")
    v:getModData()[KEY]={nativeParts=vehicleRows(v,false),nativeInventory=itemRows(p:getInventory()),
        markerIds={hammer:getID(),pencil:getID()},unexploredPartId=unexplored,
        script=v:getScript():getFullName(),world=getWorld():getWorld()}
else
    assert(v,"persisted native KI5 vehicle missing")
end

local saved=v:getModData()[KEY]
local installedChanges={}
local documentedCargo=saved.documentedCargo or {}
assert(v:getScript():getFullName()==saved.script,"native vehicle script changed")
assert(getWorld():getWorld()==saved.world,"wrong lifecycle save loaded")
local function findItem(id)
    local item=p:getInventory():getItemWithIDRecursiv(id)
    if item then return item,"inventory" end
    for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i); local container=part:getItemContainer()
        if container then local found=container:getItemWithIDRecursiv(id); if found then return found,part:getId() end end
    end
end
local function assertNative()
    for _,part in ipairs(saved.nativeParts) do local current=assert(v:getPartById(part.id),"native KI5 part disappeared: "..part.id)
        local item=current:getInventoryItem()
        local currentId=item and item:getID() or -1
        if currentId~=part.itemId then
            assert(phase=="Control","installed native KI5 item ID changed: "..part.id)
            installedChanges[#installedChanges+1]={partId=part.id,baselineItemId=part.itemId,currentItemId=currentId,
                baselineType=part.itemType,currentType=item and item:getFullType() or "",
                partCondition=current:getCondition(),itemCondition=item and item:getCondition() or -1}
        end
        for _,row in ipairs(part.contents) do local found=assert(findItem(row.id),"native cargo item ID lost: "..tostring(row.id))
            assert(found:getFullType()==row.fullType,"native cargo type changed")
        end
    end
    for _,row in ipairs(saved.nativeInventory) do local found=assert(p:getInventory():getItemWithIDRecursiv(row.id),"baseline inventory ID lost")
        assert(found:getFullType()==row.fullType,"baseline inventory type changed")
    end
    if #documentedCargo>0 then
        local cargo=assert(v:getPartById("F700TrunkBX"):getItemContainer(),"documented cargo container missing")
        for _,row in ipairs(documentedCargo) do
            local found=assert(cargo:getItemWithIDRecursiv(row.id),"clean cargo ID lost: "..tostring(row.id))
            assert(found:getFullType()==row.fullType,"clean cargo type changed: "..tostring(row.id))
        end
    end
end
assertNative()

local custom=vehicleRows(v,true)
local unexplored=saved.unexploredPartId and v:getPartById(saved.unexploredPartId):getItemContainer()
local r={phase=phase,world=saved.world,vehicleId=v:getId(),script=saved.script,
    rviLuaLoaded=hasRVI,rviJavaLoaded=MELensRV~=nil,version=MELens and MELens.VERSION or false,
    nativePartsPreserved=true,nativeItemIdsPreserved=true,originalCargoExplored=v:getPartById("F700TrunkBX"):getItemContainer():isExplored(),
    nativeInstalledItemIdsPreserved=#installedChanges==0,nativeInstalledItemChanges=installedChanges,
    separateUnexploredPartId=saved.unexploredPartId or false,separateContainerExplored=unexplored and unexplored:isExplored() or false,
    markerIds=saved.markerIds,nativeParts=vehicleRows(v,false),customParts=custom,playerInventory=itemRows(p:getInventory()),
    documentedCargo=saved.documentedCargo or {},documentedCargoItemIdsPreserved=#documentedCargo>0}

if phase=="Control" then
    assert(not hasRVI and MELensRV==nil and #custom==0,"reload control must exclude RVI")
    r.modFreeReloadControl=true
elseif phase=="Enabled" then
    assert(hasRVI and MELensRV and #custom>0,"RVI not active after fresh-process enable")
    for _,id in ipairs(saved.markerIds) do local item,where=findItem(id)
        assert(item and where=="F700TrunkBX","original cargo was moved/replaced during enable")
    end
    r.installPreservedOriginalCargoContainer=true
    -- Compare this measured flag with the no-RVI reload control: the stock
    -- engine may explore an empty native container while loading the vehicle.
elseif phase=="Clean" then
    assert(hasRVI and MELensRV,"clean checkpoint must run before disabling RVI")
    local queue=ISTimedActionQueue.queues[p]
    assert(not queue or #queue.queue==0,"wait for all ordinary transfers to finish")
    -- The parent must empty every custom storage. The explicit documented-removal
    -- fixture mode permits only empty installed MELens boxes to disappear on disable.
    local documentedRemoval=saved.documentedRemovalMode==true
    local allowedEmptyFurniture={}
    for _,part in ipairs(custom) do
        assert(#part.contents==0,"empty custom storage normally first: "..part.id)
        if part.id:find("^MELensSpot") and part.itemId~=-1 then
            assert(documentedRemoval,"remove installed RV furniture first: "..part.id)
            assert(part.itemType=="Base.MELensRV_Box","only empty documented RV boxes may disappear: "..part.id)
            allowedEmptyFurniture[#allowedEmptyFurniture+1]={partId=part.id,itemId=part.itemId,itemType=part.itemType}
        end
    end
    assert(not p:getInventory():getFirstEvalRecurse(function(item) return item:getFullType():find("MELensRV_")~=nil end),
        "remove carried custom RV furniture before disable")
    saved.cleanedCustom=custom
    saved.cleaned=true
    r.cleanPreconditions=true
    r.documentedRemovalMode=documentedRemoval
    r.emptyInstalledFurnitureDisappearanceAllowed=documentedRemoval
    r.allowedEmptyFurniture=allowedEmptyFurniture
elseif phase=="Disabled" then
    assert(saved.cleaned,"a passed clean checkpoint is required before disabling")
    assert(not hasRVI and MELensRV==nil and #custom==0,"RVI still active in disabled phase")
    r.nativeKI5PartsAvailable=v:getPartById("Engine")~=nil and v:getPartById("F700TrunkBX")~=nil
    assert(r.nativeKI5PartsAvailable,"stock KI5 vehicle parts missing after disable")
elseif phase=="Reenabled" then
    assert(saved.cleaned,"missing clean checkpoint")
    assert(hasRVI and MELensRV and #custom>0,"RVI missing after fresh-process re-enable")
    local empty=true
    for _,part in ipairs(custom) do
        if #part.contents>0 or (part.id:find("^MELensSpot") and part.itemId~=-1) then empty=false end
    end
    -- This is measured, not assumed: the engine omits unsupported part IDs
    -- when saving without RVI. A false result is a documented removal boundary.
    r.emptyLayoutPreservedAcrossDisable=empty
    r.customPartDefaultsRestored=not empty
end
MELensLifecycleTest={vehicle=v,saved=saved,last=r}
return r

-- Completion-time authority with real production eligibility/geometry and explicit
-- inventory/vehicle doubles. No native input, renderer or network is simulated.
do
    local M,P,L=MELens,MELens.Parts,MELens.Loose
    local saved={}; for k,v in pairs(L) do saved[k]=v end
    local oldClient,oldRemove,oldAdd=isClient,sendRemoveItemFromContainer,sendAddItemToContainer
    isClient=function() return false end
    sendRemoveItemFromContainer=function() end; sendAddItemToContainer=function() end
    L.floorContainer=function(v) return v.floor end
    L.floorPart=function(v) return v.floorPart end
    L.checked=function(v,x,y,z,r,s) if y>=0 then return x,y,z,r,s end end
    L.entry=function(v,id) return v.positions[id] end
    L.adopt=L.entry
    L.set=function(v,item,x,y,z,r,s) v.positions[item.id]={x=x,y=y,z=z,r=r,s=s}; return v.floorPart end
    L.remove=function(v,id) v.positions[id]=nil; return v.floorPart end
    L.displace=function() end
    local nextId=50000
    local function container()
        local c={items={}}
        function c:AddItem(item) self.items[item.id]=item; item.owner=self; return item end
        function c:Remove(item) self.items[item.id]=nil; item.owner=nil end
        function c:contains(item) return self.items[item.id]==item end
        function c:hasRoomFor() return not self.full end
        function c:getItemById(id) return self.items[id] end
        return c
    end
    local function fixture(full)
        nextId=nextId+1
        local v={parts={},positions={},floor=container(),x=0,z=0,packets=0}
        local script={}
        function script:getFullName() return "Base.87fordF700box" end
        function script:getModel() return {getOffset=function() return Vector3f.new() end} end
        function v:getScript() return script end
        function v:getPartById(id) return self.parts[id] end
        function v:getSeat() return 2 end
        function v:getPassengerLocalPos(_,vec) return vec:set(self.x,0,self.z) end
        function v:transmitPartItem() self.packets=self.packets+1 end
        local p={vehicle=v,inventory=container()}
        function p:getVehicle() return self.vehicle end
        function p:getInventory() return self.inventory end
        function p:isTimedActionInstant() return true end
        function p:removeFromHands() end
        local item={id=nextId,full=full or "Base.Hammer"}
        function item:getID() return self.id end
        function item:getFullType() return self.full end
        function item:getType() return string.match(self.full,"%.(.+)$") end
        function item:getContainer() return self.owner end
        p.inventory:AddItem(item)
        local profile=M.profileFor(v); local part,index
        for i,spot in ipairs(profile.spots) do
            local pt={id=P.SPOT..i}
            function pt:getId() return self.id end
            function pt:getInventoryItem() return self.item end
            function pt:setInventoryItem(it) self.item=it end
            function pt:getModData() self.data=self.data or {}; return self.data end
            function pt:getItemContainer() return self.container end
            v.parts[pt.id]=pt
            if not index and spot.level==1 then part,index=pt,i end
        end
        return {v=v,p=p,item=item,part=part,index=index}
    end
    local f=fixture("Base.MELensRV_Box")
    local a=MELensPlaceFurniture:new(f.p,f.v,f.part,f.item)
    check(a:isValid(),"carried box cannot initially be placed")
    f.p.inventory:Remove(f.item)
    check(not a:complete() and not f.part.item and f.v.packets==0,"stolen furniture resurrected at completion")
    f=fixture("Base.Hammer"); a=MELensPlaceFurniture:new(f.p,f.v,f.part,f.item)
    check(not a:complete() and f.p.inventory:contains(f.item) and not f.part.item,"non-furniture installed in cargo spot")
    f=fixture("Base.MELensRV_Box"); a=MELensPlaceFurniture:new(f.p,f.v,f.part,f.item)
    check(a:complete() and f.part.item==f.item and not f.p.inventory:contains(f.item),"valid furniture placement no longer transfers")

    -- A deliberately empty level-two cargo spot has no script itemType (so repair
    -- cannot auto-fill it), but remains a normal player-buildable spot. Exercise the
    -- production timed action with the exact carried item and then its save callbacks.
    local oldApply=P.applyPiece
    P.applyPiece=function() end
    f=fixture("Base.MELensRV_Box")
    local profile=M.profileFor(f.v)
    local upperIndex,unsupportedIndex
    for i,spot in ipairs(profile.spots) do
        if spot.empty and spot.level==2 and not upperIndex then upperIndex=i end
        if spot.empty and spot.level==3 and not unsupportedIndex then unsupportedIndex=i end
    end
    check(upperIndex~=nil and unsupportedIndex~=nil,"F700 empty upper cargo fixtures missing")
    local upperPart=f.v.parts[P.SPOT..upperIndex]
    local lowerIndex=profile.spots[upperIndex]._under
    f.v.parts[P.SPOT..lowerIndex].item={getFullType=function() return "Base.MELensRV_Box" end}
    a=MELensPlaceFurniture:new(f.p,f.v,upperPart,f.item)
    local originalId=f.item:getID()
    check(a:isValid(),"empty supported upper box spot rejected by placement action")
    check(a:complete() and upperPart.item==f.item and upperPart.item:getID()==originalId
        and not f.p.inventory:contains(f.item),"upper box placement did not transfer the original item")
    P.initSpot(f.v,upperPart)
    P.createSpot(f.v,upperPart)
    check(upperPart.item==f.item and upperPart.item:getID()==originalId,
        "initialization replaced a player-placed upper box")

    f=fixture("Base.MELensRV_Box")
    local unsupported=f.v.parts[P.SPOT..unsupportedIndex]
    a=MELensPlaceFurniture:new(f.p,f.v,unsupported,f.item)
    check(not a:isValid() and not a:complete() and not unsupported.item and f.p.inventory:contains(f.item),
        "unsupported empty upper slot accepted a floating box or consumed the carried item")

    f=fixture("Base.MELensRV_Box")
    local occupied=f.v.parts[P.SPOT..upperIndex]
    f.v.parts[P.SPOT..profile.spots[upperIndex]._under].item={getFullType=function() return "Base.MELensRV_Box" end}
    a=MELensPlaceFurniture:new(f.p,f.v,occupied,f.item)
    local occupant={getFullType=function() return "Base.MELensRV_Box" end}
    occupied.item=occupant
    check(not a:complete() and occupied.item==occupant and f.p.inventory:contains(f.item),
        "stale occupied upper slot replaced cargo or consumed the carried item")
    P.applyPiece=oldApply
    f=fixture(); a=MELensPlaceLoose:new(f.p,f.v,f.item,0,0,0,0,0)
    check(a:isValid(),"carried loose item cannot initially be placed")
    f.p.inventory:Remove(f.item)
    check(not a:complete() and not f.v.floor:getItemById(f.item.id),"removed loose item resurrected at completion")
    f=fixture(); a=MELensPlaceLoose:new(f.p,f.v,f.item,0,0,0,0,0); f.v.x=5
    check(not a:complete() and f.p.inventory:contains(f.item),"out-of-reach loose placement committed")
    f=fixture(); a=MELensPlaceLoose:new(f.p,f.v,f.item,0,0,0,0,0)
    check(a:complete() and not f.p.inventory:contains(f.item) and f.v.floor:getItemById(f.item.id)==f.item,
        "valid loose placement no longer transfers")
    a=MELensGrabLoose:new(f.p,f.v,f.item.id,1); f.p.vehicle=nil
    check(not a:complete() and f.v.floor:getItemById(f.item.id)==f.item,"exited player grabbed camper item")
    f.p.vehicle=f.v
    check(a:complete() and f.p.inventory:contains(f.item) and not f.v.positions[f.item.id],"valid loose grab no longer transfers")
    f=fixture(); f.p.inventory:Remove(f.item); f.v.floor:AddItem(f.item); f.v.positions[f.item.id]={x=0,z=0,r=10}
    a=MELensTurnLoose:new(f.p,f.v,f.item.id,90); f.p.vehicle=nil
    check(not a:complete() and f.v.positions[f.item.id].r==10,"exited player rotated camper item")
    f.p.vehicle=f.v
    check(a:complete() and f.v.positions[f.item.id].r==100,"valid loose rotation no longer commits")
    for k in pairs(L) do L[k]=nil end; for k,v in pairs(saved) do L[k]=v end
    isClient,sendRemoveItemFromContainer,sendAddItemToContainer=oldClient,oldRemove,oldAdd
end

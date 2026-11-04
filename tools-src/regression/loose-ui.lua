-- Shared loose-item reach and the real UI approach chooser, with explicit geometry doubles.
-- Native input and blocked-walk causality have their own disposable-game receipt.
do
    local M,P,I,UI=MELens,MELens.Parts,MELens.Interact,MELens.LooseUI
    local oldAt,oldStanding,oldNearest,oldWalkable,oldSpecific=P.characterAt,M.isStanding,M.nearestWalkableAt,M.walkableAt,getSpecificPlayer
    local v,other={},{}
    local player={vehicle=v,x=0,z=0,standing=true}
    local nearestCalls,walkableCalls=0,0
    P.characterAt=function(vehicle,actor)
        if actor and actor.vehicle==vehicle then return actor.x,actor.z end
    end
    M.isStanding=function(actor) return actor.standing end
    M.nearestWalkableAt=function(_,x,z) nearestCalls=nearestCalls+1;return x+3,z+3 end
    M.walkableAt=function() walkableCalls=walkableCalls+1;return true end
    getSpecificPlayer=function() return player end
    local profile={spots={}}
    local r=P.LOOSE_REACH
    check(P.reachesLoose(player,v,0.6,0),"shared loose reach rejects nearby point")
    check(P.reachesLoose(player,v,r,0),"shared loose reach rejects exact boundary")
    check(not P.reachesLoose(player,v,r+0.001,0),"shared loose reach accepts point beyond boundary")
    check(not P.reachesLoose(player,other,0,0),"shared loose reach accepts another vehicle")
    check(not P.reachesLoose(nil,v,0,0),"shared loose reach accepts absent character")
    local x,z=UI.standFor(v,profile,0.6,0,0,player)
    check(x==0 and z==0,"nearby floor item unnecessarily moves standing player")
    check(nearestCalls==0 and walkableCalls==0,"nearby item computes unnecessary approach route")
    x,z=UI.standFor(v,profile,0.6,0,2,player)
    check(x==0 and z==0,"nearby raised surface unnecessarily moves standing player")
    x,z=UI.standFor(v,profile,r,0,0,player)
    check(x==0 and z==0,"approach chooser disagrees with shared reach boundary")
    x,z=UI.standFor(v,profile,r+0.001,0,0,player)
    check(x~=0 or z~=0,"out-of-reach floor item skips required approach")
    check(nearestCalls==1 and walkableCalls==12,"out-of-reach floor approach no longer searches open ring")
    player.standing=false
    x,z=UI.standFor(v,profile,0.6,0,0,player)
    check(x~=0 or z~=0,"seated character incorrectly keeps furniture seat as standing approach")
    check(nearestCalls==2,"seated character bypasses standing-position chooser")
    player.standing=true
    x,z=UI.standFor(v,profile,0.6,0,0,nil)
    check(x==0 and z==0,"default local standing character does not reuse current reach")
    player.vehicle=other
    x,z=UI.standFor(v,profile,0.6,0,0,player)
    check(x==3.6 and z==3,"another vehicle incorrectly reuses player's current point")
    getSpecificPlayer=function() return nil end
    x,z=UI.standFor(v,profile,0.6,0,0,nil)
    check(x==3.6 and z==3,"absent local character fails fallback approach")
    function player:getVehicle() return self.vehicle end
    player.vehicle=v;player.x=.2;player.z=0;player.standing=true
    M.walkableAt=function() error("reachable furniture should not choose another approach") end
    x,z=I.openStandPoint(v,{wall="left",x=.8,z=0,length=.6,depth=.32},"equipmentrack",0,player)
    check(x==.2 and z==0,"furniture replacement leaves an already reachable standing position")
    P.characterAt,M.isStanding,M.nearestWalkableAt,M.walkableAt,getSpecificPlayer=oldAt,oldStanding,oldNearest,oldWalkable,oldSpecific
    ISUIElement=MELensLooseUISaved.ISUIElement
    for _,name in ipairs({"OnFillInventoryObjectContextMenu","OnGameStart","OnMainMenuEnter","OnPostUIDraw"}) do
        Events[name]=MELensLooseUISaved.events[name]
    end
end

-- Exercise the production menu callback and queue boundary. Native unequip of
-- a force-drop item would place it on the exterior world square.
do
    local M,L,V,UI=MELens,MELens.Loose,MELens.LooseView,MELens.LooseUI
    local oldStanding,oldWalk,oldStand=M.standingThen,M.walkTo,UI.standFor
    local oldFloor,oldList,oldProto,oldRefresh=L.floorContainer,L.list,V.proto,V.refresh
    local names={"ISContextMenu","ISTimedActionQueue","ISUnequipAction","HaloTextHelper","isForceDropHeavyItem","ItemTag"}
    local saved={};for _,name in ipairs(names) do saved[name]=_G[name] end
    ItemTag=ItemTag or {GENERATOR="fixture-generator-tag"}
    local item={}
    function item:getType() return "Generator" end
    function item:getActualWeight() return 40 end
    function item:getDisplayName() return "Generator" end
    function item:getTex() return nil end
    local vehicle,profile={},{}
    local player={}
    function player:getPrimaryHandItem() return self.primary end
    function player:getSecondaryHandItem() return self.secondary end
    function player:isTimedActionInstant() return true end
    local entries={{id=101,t="Base.Generator",x=0,z=0,y=0,s=0},{id=102,t="Base.Generator",x=0,z=0,y=0,s=0}}
    L.floorContainer=function() return {getItemById=function() return item end} end
    L.list=function() return entries end
    V.proto=function() return item end;V.refresh=function() end
    M.standingThen=function(_,callback) callback() end
    UI.standFor=function() return 0,0 end
    local pending,queued,options,messages
    M.walkTo=function(_,_,_,callback) pending=callback end
    ISTimedActionQueue={add=function(action) queued[#queued+1]=action end}
    ISUnequipAction={new=function(_,_,held) return {kind="unequip",item=held} end}
    HaloTextHelper={addBadText=function(_,text) messages[#messages+1]=text end}
    isForceDropHeavyItem=function(held) return held.forceDrop==true end
    ISContextMenu={getNew=function() return {addOption=function(_,label,_,callback)
        options[label]=callback;return {}
    end} end}
    local context={addOptionOnTop=function() return {} end,addSubMenu=function() end}
    local function choose(primary,secondary,all)
        player.primary,player.secondary=primary,secondary
        queued,options,messages={},{},{}
        UI.menu(player,vehicle,profile,{entry=entries[1]},context)
        options[all and "ContextMenu_MELens_GrabAllHere" or "ContextMenu_Grab"]()
    end
    choose(nil,nil);pending()
    check(#queued==1 and queued[1].itemId==101,"empty hands failed to queue generator pickup")
    local ordinary,other={},{forceDrop=false}
    choose(ordinary,ordinary);pending()
    check(#queued==2 and queued[1].item==ordinary and queued[2].itemId==101,
        "two-handed ordinary item queued duplicate unequip")
    choose(ordinary,other);pending()
    check(#queued==3 and queued[1].item==ordinary and queued[2].item==other and queued[3].itemId==101,
        "distinct ordinary hand items did not unequip before pickup")
    local carried={forceDrop=true}
    choose(carried,carried);pending()
    check(#queued==0 and player.primary==carried and player.secondary==carried and #messages==1,
        "generator pickup queued exterior drop of carried heavy item")
    choose(ordinary,carried);pending()
    check(#queued==0 and player.primary==ordinary and player.secondary==carried,
        "secondary heavy item was checked after ordinary unequip was queued")
    choose(nil,nil);player.primary=carried;pending()
    check(#queued==0 and player.primary==carried,"changed heavy hand state during approach queued exterior drop")
    choose(carried,carried)
    check(#queued==0 and player.primary==carried and player.secondary==carried,
        "cancelled approach changed carried heavy item")
    choose(nil,nil,true);pending()
    check(#queued==1 and queued[1].itemId==101,"Grab All queued a second generator after heavy pickup")
    M.standingThen,M.walkTo,UI.standFor=oldStanding,oldWalk,oldStand
    L.floorContainer,L.list,V.proto,V.refresh=oldFloor,oldList,oldProto,oldRefresh
    for _,name in ipairs(names) do _G[name]=saved[name] end
    MELens.LooseView=MELensLooseUISaved.LooseView
    MELensLooseUISaved=nil
end

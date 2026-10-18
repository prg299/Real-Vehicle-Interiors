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
    P.characterAt,M.isStanding,M.nearestWalkableAt,M.walkableAt,getSpecificPlayer=oldAt,oldStanding,oldNearest,oldWalkable,oldSpecific
    ISUIElement=MELensLooseUISaved.ISUIElement
    for _,name in ipairs({"OnFillInventoryObjectContextMenu","OnGameStart","OnMainMenuEnter","OnPostUIDraw"}) do
        Events[name]=MELensLooseUISaved.events[name]
    end
    MELensLooseUISaved=nil
end

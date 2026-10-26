-- Real packing and display contracts, with explicit native size/container doubles.
do
    local M,P,V=MELens,MELens.Parts,MELens.LooseView
    local slot={length=.60,depth=.32,pieces={"equipmentrack"}}
    check(P.fits(slot,"equipmentrack"),"declared factory model cannot return to its slot")
    check(not P.fits(slot,"medlocker"),"factory slot accepts furniture without a declared model")
    local oldPart,oldSize,oldRV=P.spotPart,M.LooseUI.size,MELensRV
    MELensRV=completeJava({canShow=function() return true end})
    M.LooseUI.size=function(item) return item.w,item.h,item.d end
    local rows={}
    local function item(id,w,h,d)
        return {w=w,h=h,d=d,getID=function() return id end,getFullType=function() return "Base.Bandage" end,
                getClothingItem=function() end}
    end
    local items={size=function() return #rows end,get=function(_,i) return rows[i+1] end}
    local installed={getFullType=function() return "Base.MELensRV_Equipmentrack" end}
    local container={getItems=function() return items end}
    local part={getInventoryItem=function() return installed end,
                getItemContainer=function() return container end}
    P.spotPart=function() return part end
    local profile={floorY=.3,spots={{wall="left",x=.8,z=0}}}
    local shown,pending=V.shelfItems({},profile,64)
    check(#shown==0 and not pending,"empty shelf invents props")
    rows={item(12,.13,.10,.10),item(7,.15,.10,.10),item(9,.11,.10,.12)}
    shown,pending=V.shelfItems({},profile,64)
    check(#shown==3 and not pending,"real shelf items not represented")
    check(shown[1].e.id==7 and shown[3].e.id==12,"shelf packing unstable by item ID")
    for _,s in ipairs(shown) do
        check(s.item~=nil and s.e.t==s.item:getFullType(),"display substitutes a different item")
        check(s.e.y>=profile.floorY+.052 and s.e.s==1,"item not resting on shelf board")
    end
    rows={rows[1],rows[3]};shown=V.shelfItems({},profile,64)
    check(#shown==2 and shown[1].e.id==9,"removed shelf item still drawn")
    rows={item(1,2,2,2)};shown=V.shelfItems({},profile,64)
    check(#shown==0,"oversize stored object clips through shelf")
    rows={item(1,.1,.1,.1),item(2,.1,.1,.1)};profile.spots[2]={wall="right",x=-.8,z=0}
    shown=V.shelfItems({},profile,2)
    check(#shown==2 and shown[1].e.s==1 and shown[2].e.s==2,"draw budget starves later shelves")
    -- Keep identity stable, as real VehicleParts/ItemContainers do. Count native
    -- size queries to prove that unchanged contents avoid the placement search.
    profile.spots[2]=nil
    local vehicle,queries={},0
    local measured=M.LooseUI.size
    M.LooseUI.size=function(value) queries=queries+1;return measured(value) end
    rows={}
    for id=1,1000 do rows[id]=item(id,.1,.1,.1) end
    shown=V.shelfItems(vehicle,profile,2)
    check(#shown==2 and queries==2,"packing ignores the display budget")
    local first=shown[1].item
    queries=0;shown=V.shelfItems(vehicle,profile,2)
    check(queries==0 and shown[1].item==first,"unchanged shelf repeats packing")
    shown=V.shelfItems(vehicle,profile,0)
    check(#shown==0 and queries==0,"zero display budget still packs items")
    rows[1]=item(2001,.1,.1,.1)
    shown=V.shelfItems(vehicle,profile,2)
    check(queries>0 and shown[1].e.id==2,"same-count native transfer leaves stale display")
    queries=0;shown=V.shelfItems(vehicle,profile,1)
    check(queries==0 and #shown==1,"lowering budget rebuilds a sufficient cache")
    shown=V.shelfItems(vehicle,profile,16)
    check(queries>0 and #shown==16,"raising budget does not refill display")
    local before=shown[1].e.x
    profile.spots[1].x=profile.spots[1].x+.2
    shown=V.shelfItems(vehicle,profile,16)
    check(math.abs(shown[1].e.x-before-.2)<.00001,"moved furniture uses old coordinates")
    queries=0;V.refresh();shown=V.shelfItems(vehicle,profile,16)
    check(queries>0,"explicit refresh does not invalidate shelf layout")
    -- Unready native models must be reconsidered, while a full shelf must not
    -- search the same impossible placement for every identical inventory item.
    rows={item(1,2,2,2),item(2,2,2,2),item(3,.1,.1,.1)}
    local loading=true
    M.LooseUI.size=function(value) if loading and value:getID()==3 then return nil end;return measured(value) end
    shown,pending=V.shelfItems(vehicle,profile,16)
    check(#shown==0 and pending,"loading item is cached as permanently invisible")
    local waitingQueries=0
    local waitingSize=M.LooseUI.size
    M.LooseUI.size=function(value) waitingQueries=waitingQueries+1;return waitingSize(value) end
    V.shelfItems(vehicle,profile,16) -- new size adapter invalidates once
    waitingQueries=0;V.shelfItems(vehicle,profile,16)
    check(waitingQueries==1,"unready model repeats packing for ready inventory items")
    loading=false;shown,pending=V.shelfItems(vehicle,profile,16)
    check(#shown==1 and not pending and shown[1].e.id==3,"native model retry does not recover")
    local oldLook=M.Loose.lookOf
    local tint=.2
    M.Loose.lookOf=function() return {tx="same-item",tr=tint,tg=.3,tb=.4} end
    shown=V.shelfItems(vehicle,profile,16)
    check(shown[1].e.tr==.2,"shelf loses item appearance")
    tint=.8;shown=V.shelfItems(vehicle,profile,16)
    check(shown[1].e.tr==.8,"cached shelf freezes item tint")
    M.Loose.lookOf=oldLook
    local speedCalls,tumbles,speed=0,0,100
    local travel={getCurrentAbsoluteSpeedKmHour=function() speedCalls=speedCalls+1;return speed end}
    local oldTumble=M.Loose.tumble
    M.Loose.tumble=function() tumbles=tumbles+1;return true end
    check(not M.Loose.look(864512300,travel,1000,2,1),"initial speed sample throws loose items")
    speed=0
    for t=1010,1100,10 do M.Loose.look(864512300,travel,t,2,1) end
    check(speedCalls==1 and tumbles==0,"travel watch queries speed before its sample deadline")
    check(M.Loose.look(864512300,travel,1300,2,1) and tumbles==1,"sample deadline suppresses real braking")
    check(not M.Loose.look(864512300,travel,10,2,1),"clock reset produces false braking")
    M.Loose.tumble=oldTumble
    P.spotPart,M.LooseUI.size,MELensRV=oldPart,oldSize,oldRV
end

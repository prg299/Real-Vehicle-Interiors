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
    local part={getInventoryItem=function() return {getFullType=function() return "Base.MELensRV_Equipmentrack" end} end,
                getItemContainer=function() return {getItems=function() return items end} end}
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
    P.spotPart,M.LooseUI.size,MELensRV=oldPart,oldSize,oldRV
end

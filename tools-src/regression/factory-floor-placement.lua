-- Shared production Floor listing: no Java/native model, inventory mutation or renderer.
do
    local M, L, P = MELens, MELens.Loose, MELens.Parts
    local oldRings, oldPoints, oldPart, oldPiece = M.RoomRings, L.floorPoints, P.spotPart, P.pieceAt
    local oldRV = MELensRV
    MELensRV = nil
    M.RoomRings = { cargoTest = {{-1,-2},{1,-2},{1,2},{-1,2}} }
    local profile = { floorY=-.5, walkGrid="cargoTest", spots={}, wheelWells={}, blocked={},
        factoryFloor={{t="Base.PropaneTank",x=-.6,z=-1,r=0,hx=.17,hz=.17},
                      {t="Base.PropaneTank",x=.6,z=-1,r=0,hx=.17,hz=.17}} }
    local rows, data, pointCalls = {}, {}, 0
    local function item(id, typ)
        return {getID=function() return id end, getFullType=function() return typ or "Base.PropaneTank" end,
                getClothingItem=function() end}
    end
    local items={size=function() return #rows end,get=function(_,i) return rows[i+1] end}
    local part={getModData=function() return data end,getItemContainer=function() return {getItems=function() return items end} end}
    local vehicle={getPartById=function(_,id) if id==P.FLOOR then return part end end,getId=function() return 98989 end}
    local points={{0,0},{0,.4},{0,.8},{0,1.2}}
    L.floorPoints=function() pointCalls=pointCalls+1;return points end
    rows={item(30),item(10)}
    local shown=L.list(vehicle,profile)
    check(#shown==2 and shown[1].id==10 and shown[2].id==30,"cargo ID ordering")
    check(shown[1].x==-.6 and shown[2].x==.6 and shown[1].z==-1,"returned cargo misses measured bays")
    check(shown[1].y==profile.floorY and shown[1].s==0 and shown[1].orphan,"cargo floor presentation")
    check(data.loose==nil and #rows==2 and rows[1]:getID()==30,"listing mutates items or saved placements")
    rows={rows[2],rows[1]}
    local again=L.list(vehicle,profile)
    check(again[1].x==shown[1].x and again[2].x==shown[2].x,"inventory order changes bays")
    data.loose={["30"]={t="Base.PropaneTank",x=-.6,y=-.5,z=-1,r=90,s=0}}
    shown=L.list(vehicle,profile)
    check(shown[1].x==.6 and shown[2].x==-.6 and shown[2].r==90,"occupied known bay or explicit placement overwritten")
    check(data.loose["30"].r==90,"explicit saved rotation changed")
    data.loose={};rows={item(10)}
    profile.blocked={{x1=-.45,x2=-.3,z1=-1.2,z2=-.8}}
    shown=L.list(vehicle,profile)
    check(shown[1].x==.6,"declared envelope gets furniture slack")
    profile.blocked={};profile.wheelWells={{x={-.8,-.45},z={-1.3,-.7},y={-.5,0}}}
    shown=L.list(vehicle,profile)
    check(shown[1].x==.6,"cargo overlaps a wheel housing")
    profile.wheelWells={};profile.factoryFloor[1].x=-.9
    shown=L.list(vehicle,profile)
    check(shown[1].x==.6,"cargo footprint crosses room wall")
    profile.factoryFloor[1].x=-.6
    profile.spots={{wall="front",x=-.6,z=-.7,length=.5,depth=.5}}
    P.spotPart=function() return {} end;P.pieceAt=function() return "metalcase" end
    shown=L.list(vehicle,profile)
    check(shown[1].x==.6,"cargo ignores newly installed furniture")
    profile.spots={};P.spotPart,P.pieceAt=oldPart,oldPiece
    -- Unknown floor footprints conservatively disable preferred bays. They keep
    -- legacy generic packing; this test does not claim generic collision safety.
    data.loose={["20"]={t="Base.UnknownLargeItem",x=-.95,y=-.5,z=1.8,r=0,s=0}}
    shown=L.list(vehicle,profile)
    check(shown[1].x==0 and shown[2].x==-.95,"unknown footprint did not block preferred bays or was moved")
    data.loose={};rows={item(10),item(40,"Base.UnknownLargeItem")}
    shown=L.list(vehicle,profile)
    check(shown[1].x==0 and shown[2].x==0,"unknown later orphan ignored before preferred packing")
    rows={item(10),item(30),item(50)}
    shown=L.list(vehicle,profile)
    check(#shown==3 and shown[3].x==0,"full bays do not use checked fallback")
    for i=1,#shown do for j=i+1,#shown do
        check(math.abs(shown[i].x-shown[j].x)>=.34 or math.abs(shown[i].z-shown[j].z)>=.34,"known cargo envelopes overlap")
    end end
    -- Ordinary profiles preserve the old ID-modulo grid result exactly.
    profile.factoryFloor=nil;rows={item(3,"Base.Book"),item(1,"Base.Book")}
    data.loose={["9"]={t="Base.Book",x=.3,y=.6,z=.4,r=17,s=2}}
    shown=L.list(vehicle,profile)
    check(#shown==3 and shown[1].id==1 and shown[1].z==.4 and shown[2].id==3 and shown[2].z==1.2,
          "ordinary profile fallback changed")
    check(shown[3].x==.3 and shown[3].y==.6 and shown[3].r==17 and shown[3].s==2,"ordinary explicit placement changed")
    rows={};data.loose={}
    check(#L.list(vehicle,profile)==0,"listing spawns/refills cargo")
    M.RoomRings,L.floorPoints,P.spotPart,P.pieceAt,MELensRV=oldRings,oldPoints,oldPart,oldPiece,oldRV
end

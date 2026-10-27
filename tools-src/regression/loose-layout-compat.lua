-- Released Floor coordinates remain in their original furniture anchor frame.
-- Exercise production Loose functions with inventory/vehicle doubles only.
-- These checks do not prove native save bytes, rendering, input or multiplayer.
do
    local M,L,P=MELens,MELens.Loose,MELens.Parts
    local old={client=isClient,server=isServer,watch=L.watch,drop=L.dropSpot,covered=P.covered,look=L.lookOf}
    local client,server,watchCalls=false,false,0
    isClient=function() return client end
    isServer=function() return server end
    L.watch=function() watchCalls=watchCalls+1 end
    local function close(a,b) return math.abs(a-b)<.00000001 end
    local function copy(value)
        local out={}
        for k,v in pairs(value) do out[k]=v end
        return out
    end
    local function same(a,b,label)
        for k,v in pairs(a) do check(b[k]==v,label.." changed field "..tostring(k)) end
        for k,v in pairs(b) do check(a[k]==v,label.." added field "..tostring(k)) end
    end
    local profile=M.Profiles["Base.90fordF350ambulance"]
    check(profile and profile.looseSpotOffsets,"generated F350 compatibility metadata missing")
    local offsetCount=0
    for key,offset in pairs(profile.looseSpotOffsets) do
        offsetCount=offsetCount+1
        check((key=="7" or key=="8") and close(offset.x or 0,0) and close(offset.z,-.06),
            "F350 projection includes another slot or wrong displacement")
    end
    check(offsetCount==2,"F350 projection must cover exactly slots7/8")
    check(close(profile.spots[7].z,-.46) and close(profile.spots[8].z,-.46),
        "projection metadata no longer matches the moved cabinet geometry")
    check(not M.Profiles["Base.90fordF350SWAT"].looseSpotOffsets,"ambulance compatibility leaked to SWAT")
    local function item(id)
        return {getID=function() return id end,getFullType=function() return "Base.Bandage" end,
                getClothingItem=function() end}
    end
    local function fixture(script,records)
        local data={loose=records}
        local items={}
        for key in pairs(records) do items[#items+1]=item(tonumber(key)) end
        local list={size=function() return #items end,get=function(_,i) return items[i+1] end}
        local container={getItems=function() return list end,
            getItemById=function(_,id) for _,it in ipairs(items) do if it:getID()==id then return it end end end}
        local floor={getModData=function() return data end,getItemContainer=function() return container end}
        local cabinets={}
        for _,n in ipairs({7,8}) do
            cabinets[P.SPOT..n]={getInventoryItem=function()
                return {getFullType=function() return "Base.MELensRV_Medlocker" end}
            end}
        end
        local v={data={},floor=floor,transmits=0}
        function v:getScript() return {getFullName=function() return script end} end
        function v:getPartById(id) if id==P.FLOOR then return floor end;return cabinets[id] end
        function v:getId() return 827017 end
        function v:transmitPartModData(part) check(part==floor,"wrong part transmitted");self.transmits=self.transmits+1 end
        function v:getModData() return self.data end
        return v,data
    end
    local raw={t="Base.Bandage",x=-.27,y=.295,z=-.46,r=37,s=7,
        tx="retained-texture",tr=.2,tg=.3,tb=.4,legacyTag="keep-unknown-field"}
    local raw8={t="Base.Bandage",x=.27,y=.585,z=-.45,r=87,s=8}
    local floorRecord={t="Base.Bandage",x=2,y=profile.floorY,z=-1,r=9,s=0}
    local otherRecord={t="Base.Bandage",x=.8,y=.3,z=-1.3,r=19,s=6}
    local records={["27001"]=copy(raw),["27002"]=copy(raw8),["27003"]=copy(floorRecord),["27004"]=copy(otherRecord)}
    local v,data=fixture("Base.90fordF350ambulance",records)
    local rawReference=records["27001"]
    -- Multiple client-style reads project once and never replace or modify the saved table.
    client=true
    for pass=1,4 do
        local entry=L.entry(v,27001)
        check(entry~=rawReference and close(entry.z,-.52) and entry.x==raw.x and entry.s==7,
            "old shelf record is not projected exactly once")
        check(entry.legacyTag==raw.legacyTag and entry.tx==raw.tx and entry.r==raw.r,
            "projected entry drops retained record fields")
        entry.z=99 -- mutation of the presentation copy must not mutate authority
        same(records["27001"],raw,"entry read")
        local shown=L.list(v,profile)
        check(#shown==4 and shown[1].id==27001 and close(shown[1].z,-.52)
            and close(shown[2].z,-.51),"repeated listing doubles/skips cabinet projection")
        check(shown[1].tx==raw.tx and shown[1].tr==raw.tr and shown[1].tg==raw.tg
            and shown[1].tb==raw.tb and shown[1].r==raw.r,"listing changes saved appearance/turn")
        check(shown[3].x==floorRecord.x and shown[3].z==floorRecord.z and shown[3].s==0,
            "floor placement receives furniture offset")
        check(shown[4].x==otherRecord.x and shown[4].z==otherRecord.z and shown[4].s==6,
            "unrelated raised placement receives furniture offset")
        check(records["27001"]==rawReference,"read replaces committed record")
        same(records["27001"],raw,"repeated read")
        same(records["27002"],raw8,"slot8 read")
    end
    client=false
    -- Current authority accepts the projected old near-edge coordinate. Raw legacy
    -- coordinates are not UI coordinates, and can lie beyond the moved shelf.
    local x,y,z,r,s=L.checked(v,raw8.x,raw8.y,-.51,raw8.r,8)
    check(x==raw8.x and close(y,raw8.y) and close(z,-.51) and r==87 and s==8,
        "projected old near-edge shelf placement fails production authority")
    check(L.checked(v,raw8.x,raw8.y,raw8.z,raw8.r,8)==nil,
        "authority silently treats raw legacy coordinates as current shelf coordinates")
    -- Explicit placement writes in the released frame; new records downgrade
    -- against old cabinet anchors and reload through the same projection.
    L.lookOf=function() return {tx="fresh-texture",tr=.4,tg=.5,tb=.6} end
    local placed=item(27005)
    check(L.set(v,placed,-.27,.295,-.52,137,7)==v.floor,"placement returns wrong authoritative part")
    check(close(records["27005"].z,-.46) and records["27005"].s==7 and records["27005"].r==137,
        "placement persists current rather than released coordinates")
    local firstWrite=copy(records["27005"])
    for pass=1,3 do
        local current=L.entry(v,27005)
        check(close(current.z,-.52),"new placement projection drifts")
        L.set(v,placed,current.x,current.y,current.z,current.r,current.s)
        same(records["27005"],firstWrite,"inverse roundtrip")
    end
    check(watchCalls==4,"raised placement no longer starts its existing travel watch")
    check(records["27005"].tx=="fresh-texture" and records["27005"].tb==.6,
        "inverse placement loses native item appearance")
    L.set(v,item(27006),.2,profile.floorY,-.52,5,0)
    check(records["27006"].z==-.52 and records["27006"].s==0,"floor write is inverse projected")
    L.set(v,item(27007),.2,.3,-.52,5,6)
    check(records["27007"].z==-.52 and records["27007"].s==6,"unrelated slot write is inverse projected")
    local ordinary,ordinaryData=fixture("Base.Van",{["27001"]=copy(raw)})
    check(L.entry(ordinary,27001)==ordinaryData.loose["27001"],"ordinary profile changes entry identity")
    check(L.list(ordinary,M.profileFor(ordinary))[1].z==raw.z,"ordinary profile is projected")
    L.set(ordinary,item(27008),raw.x,raw.y,-.52,7,7)
    check(ordinaryData.loose["27008"].z==-.52,"ordinary profile write receives inverse offset")
    -- Snapshot/reload into another vehicle instance preserves raw records and
    -- presents the same current geometry without a migration/version stamp.
    local reloaded,reloadedData=fixture("Base.90fordF350ambulance",{["27001"]=copy(raw)})
    check(close(L.entry(reloaded,27001).z,-.52),"reloaded raw record receives a second/missing shift")
    same(reloadedData.loose["27001"],raw,"reload read")
    -- Production displacement and tumble must seed current-space drop search,
    -- then store floor-space coordinates without retaining/inverting the old offset.
    local seeds={}
    L.dropSpot=function(_,_,px,pz,id)
        seeds[id]={x=px,z=pz}
        return px+.01,pz-.02
    end
    P.covered=function(_,_,index) return index==7 or index==8 end
    local displaced,displacedData=fixture("Base.90fordF350ambulance",
        {["27001"]=copy(raw),["27002"]=copy(raw8),["27003"]=copy(floorRecord),["27004"]=copy(otherRecord)})
    check(L.displace(displaced,7)==displaced.floor,"displacement misses covered saved placements")
    check(close(seeds[27001].z,-.52) and close(seeds[27002].z,-.51),"displacement seeds legacy coordinates")
    check(close(displacedData.loose["27001"].z,-.54) and displacedData.loose["27001"].s==0,
        "displaced item retains/doubles its shelf offset")
    same(displacedData.loose["27003"],floorRecord,"unburied floor displacement control")
    same(displacedData.loose["27004"],otherRecord,"uncovered raised displacement control")
    seeds={}
    local tumbled,tumbledData=fixture("Base.90fordF350ambulance",
        {["27001"]=copy(raw),["27002"]=copy(raw8),["27003"]=copy(floorRecord),["27004"]=copy(otherRecord)})
    server=true
    check(L.tumble(tumbled),"tumble misses saved raised placements")
    check(close(seeds[27001].z,-.52) and close(seeds[27002].z,-.51)
        and seeds[27004].z==otherRecord.z,"tumble seeds unprojected/double-projected coordinates")
    check(tumbledData.loose["27001"].s==0 and close(tumbledData.loose["27001"].z,-.54)
        and tumbledData.loose["27002"].s==0 and close(tumbledData.loose["27002"].z,-.53),
        "tumble writes the wrong floor-space result")
    check(close(L.entry(tumbled,27001).z,-.54),"floor read keeps applying former shelf shift")
    same(tumbledData.loose["27003"],floorRecord,"tumble floor control")
    check(tumbledData.tumbles==1 and tumbled.transmits==1,"tumble accounting/transmission changed")
    for _,id in ipairs({27001,27002,27004}) do
        local e=tumbledData.loose[tostring(id)]
        check(e.t=="Base.Bandage" and e.r==({[27001]=37,[27002]=87,[27004]=19})[id],
            "tumble loses item identity/turn")
    end
    isClient,isServer,L.watch,L.dropSpot,P.covered,L.lookOf=old.client,old.server,old.watch,old.drop,old.covered,old.look
end

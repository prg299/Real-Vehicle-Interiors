"""Native two-client checks for the reported F700 pickup/loot/passenger bugs.

Import is inert. The parent owns the server and both inactive clients.
Entry, pickup menus, driving and exit use native input. Loot transfers explicitly
use the game's real inventory-transfer action, not mouse drag/drop acceptance.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]


def import_driver(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


JSON_ENCODER = r'''
local function enc(v)
    local t=type(v)
    if t=="nil" then return "null" end
    if t=="boolean" or t=="number" then return tostring(v) end
    if t=="string" then return '"'..v:gsub('\\','\\\\'):gsub('"','\\"'):gsub('\n','\\n'):gsub('\r','\\r')..'"' end
    local out={}
    if #v>0 then for i=1,#v do out[#out+1]=enc(v[i]) end; return '['..table.concat(out,',')..']' end
    local keys={}; for k in pairs(v) do keys[#keys+1]=k end; table.sort(keys)
    for _,k in ipairs(keys) do out[#out+1]=enc(tostring(k))..':'..enc(v[k]) end
    return '{'..table.concat(out,',')..'}'
end
'''

READ_STATE = r'''
local v=getVehicleById(VID)
local r={ready=v~=nil}
if v then
    r.vehicle={id=v:getId(),x=v:getX(),y=v:getY(),z=v:getZ(),speed=v:getCurrentSpeedKmHour(),engine=v:isEngineRunning()}
    if not isServer() then
        local ok,k=pcall(function() return v:isKeyboardControlled() end); if ok then r.vehicle.keyboardControlled=k end
        local pad,j=pcall(function() return v:getJoypad() end); if pad then r.vehicle.joypad=j end
    end
    r.partIds={}; r.boxes={}; r.players={}; r.loot={}; r.floor={};r.furniture={};r.storage={}
    for i=0,v:getPartCount()-1 do r.partIds[#r.partIds+1]=v:getPartByIndex(i):getId() end
    for i,s in ipairs(MELens.profileFor(v).spots) do
        if s.cargo then local p=MELens.Parts.spotPart(v,i); local it=p and p:getInventoryItem()
            r.boxes[tostring(i)]=it and it:getID() or -1
        end
    end
    local function ids(c)
        local a={}; if c then for i=0,c:getItems():size()-1 do a[#a+1]=c:getItems():get(i):getID() end end
        table.sort(a); return a
    end
    for i,s in ipairs(MELens.profileFor(v).spots) do
        local part=MELens.Parts.spotPart(v,i);local item=part and part:getInventoryItem()
        r.furniture[i]=item and item:getID() or -1
        r.storage[i]=ids(part and part:getItemContainer())
    end
    local chosen=v:getPartById('MELensSpot'..BOX)
    r.loot=ids(chosen and chosen:getItemContainer())
    local floor=v:getPartById('MELensFloor'); r.floor=ids(floor and floor:getItemContainer())
    local function playerState(p)
        if p:getUsername()=='MELensAdmin' or p:getUsername()=='MELensGuest' then
            local pv=p:getVehicle(); local seat=v:getSeat(p)
            local a={id=p:getOnlineID(),x=p:getX(),y=p:getY(),z=p:getZ(),vehicleId=pv and pv:getId() or -1,seat=seat}
            if seat>=0 then local w=v:getPassengerWorldPos(seat,Vector3f.new())
                a.expectedX=w:x(); a.expectedY=w:y(); a.expectedZ=w:z()
                local q=v:getPassengerLocalPos(seat,Vector3f.new()); a.localX=q:x(); a.localY=q:y(); a.localZ=q:z()
            end
            a.standing=false
            if seat>=0 then
                local passenger=v:getScript():getPassenger(seat)
                local id=passenger and passenger:getId()
                for _,standingId in ipairs(MELens.standingIds(MELens.profileFor(v))) do
                    if id==standingId then a.standing=true end
                end
            end
            if isServer() or p==getPlayer() then a.inventory=ids(p:getInventory()) end
            -- Client timed queues are not server authority and querying a queue
            -- may create one. Observe the existing local queue only.
            if not isServer() and p==getPlayer() then
                local q=ISTimedActionQueue.queues[p]
                a.queue=q and #q.queue or 0
                a.pathing=MELens.pathing(p)
            end
            r.players[p:getUsername()]=a
        end
    end
    local list=getOnlinePlayers()
    for i=0,list:size()-1 do playerState(list:get(i)) end
    if not isServer() and getPlayer() then playerState(getPlayer()) end
end
'''

PICK_POINT = r'''
local p=getPlayer(); local v=p:getVehicle(); local q=MELens.profileFor(v); local P,I=MELens.Parts,MELens.Interact
local o=v:getScript():getModel():getOffset(); local base=v:getWorldPos(0,0,0,Vector3f.new()):z()
local zoom=getCore():getZoom(p:getPlayerNum())
local candidates={}
for i,s in ipairs(q.spots) do
    if s.cargo and (s.level or 1)>=2 and P.pieceAt(P.spotPart(v,i))=='box' and not P.covered(v,q,i) then
        candidates[#candidates+1]={index=i,spot=s,d=(s.x-q.door.x)^2+(s.z-q.door.z)^2}
    end
end
table.sort(candidates,function(a,b) return a.d<b.d end)
for _,c in ipairs(candidates) do local s=c.spot; local _,depth,height=P.footprint(s,'box'); local top=q.floorY+(s.rise or 0)+height
    for _,a in ipairs({0,-.15,.15,-.24,.24}) do for _,d in ipairs({depth/2,depth-.08,.08}) do
        local x,z=P.spotPoint(s,a,d)
        for _,h in ipairs({.01,.1,.2,.3}) do
            local w=v:getWorldPos(o:x()+x,o:y()+top-h,o:z()+z,Vector3f.new())
            local sx,sy=ISCoordConversion.ToScreen(w:x(),w:y(),base+(o:y()+top-h)/2.44949)
            local hit=I.pick(v,q,sx,sy)
            local px,py=math.floor(sx/zoom+0.5),math.floor(sy/zoom+0.5)
            if px>10 and px<1270 and py>10 and py<710 and hit and hit.index==c.index then
                return {index=c.index,level=s.level or 1,x=px,y=py}
            end
        end
    end end
end
return false
'''

ENTRY_DIAGNOSTIC = r'''
local p=getPlayer(); local v=getVehicleById(VID)
local r={ready=p~=nil and v~=nil,pendingUse=tostring(MELens.pendingUse),
    vehicleUtils=type(VehicleUtils and VehicleUtils.OnUseVehicle),
    doorUse=type(Vehicles and Vehicles.Use and Vehicles.Use.Door),
    trunkUse=type(Vehicles and Vehicles.Use and Vehicles.Use.TrunkDoor)}
local function probe(name,fn)
    local ok,a,b=pcall(fn); local row={ok=ok}
    if ok then row.isNil=a==nil; row.value=a; row.second=b else row.error=tostring(a) end
    r[name]=row
end
if not r.ready then return r end
local q=MELens.profileFor(v); local part=v:getPartById(q.standing.door)
r.player={x=p:getX(),y=p:getY(),z=p:getZ(),vehicleId=p:getVehicle() and p:getVehicle():getId() or -1}
r.vehicle={id=v:getId(),x=v:getX(),y=v:getY(),z=v:getZ(),speed=v:getCurrentSpeedKmHour(),
    script=v:getScript():getFullName(),door=q.standing.door,area=part and part:getArea()}
probe('java',function() return MELens.debugState() end)
probe('keybind',function() return getCore():getKey(KeybindId.INTERACT) end)
probe('canWalkIn',function() return MELens.canWalkIn(p,v) end)
probe('nearWayIn',function() return MELens.nearWayIn(p,v,q) end)
probe('freeStandingSeat',function() return MELens.freeStandingSeat(v,q) end)
probe('usablePart',function() local a=v:getUseablePart(p); return a and a:getId() end)
probe('usablePartIgnoringFacing',function() local a=v:getUseablePart(p,false); return a and a:getId() end)
probe('inDoorArea',function() return part and v:isInArea(part:getArea(),p) end)
probe('forward',function() local a=p:getForwardDirection(); return {x=a:getX(),y=a:getY(),turning=p:shouldBeTurning()} end)
probe('outside',function()
    local a=v:getPassengerPosition(MELens.cabinSeat(v,q),'outside'); local w=v:getPassengerPositionWorldPos(a,Vector3f.new())
    return {x=w:x(),y=w:y(),z=w:z(),distance=math.sqrt(p:DistToSquared(w:x(),w:y()))}
end)
probe('doorArea',function()
    local a=v:getAreaCenter(part:getArea()); local s=v:getScript():getAreaById(part:getArea())
    return {x=a:getX(),y=a:getY(),localX=s:getX(),localY=s:getY(),width=s:getW(),height=s:getH()}
end)
probe('door',function() local d=part:getDoor(); local it=part:getInventoryItem()
    return {use=part:getLuaFunction('use'),installed=it~=nil,itemId=it and it:getID(),locked=d and d:isLocked(),open=d and d:isOpen()}
end)
probe('useableVehicle',function() local a=p:getUseableVehicle(); return a and a:getId() end)
probe('nearVehicle',function() local a=p:getNearVehicle(); return a and a:getId() end)
probe('queue',function() local a=ISTimedActionQueue.queues[p]; local list={}
    for _,action in ipairs(a and a.queue or {}) do list[#list+1]=tostring(action.Type) end
    return {count=#list,actions=list,pathing=MELens.pathing(p)}
end)
probe('nearbyVehicles',function() local list={}; local it=getCell():getVehicles():iterator()
    while it:hasNext() do local a=it:next(); local d=(a:getX()-v:getX())^2+(a:getY()-v:getY())^2
        if a~=v and d<225 then list[#list+1]={id=a:getId(),script=a:getScript():getFullName(),x=a:getX(),y=a:getY(),distance=math.sqrt(d)} end
    end; return list
end)
probe('polygonLine',function()
    local map
    if type(getPolygonalMap2)=='function' then map=getPolygonalMap2()
    elseif PolygonalMap2 then map=PolygonalMap2.instance end
    if not map then return {available=false,reason='PolygonalMap2 is not exposed to this Lua state'} end
    local s=v:getScript(); local a=s:getAreaById(part:getArea()); local o=v:areaPositionLocal(a,Vector2.new())
    local c,e=s:getCenterOfMassOffset(),s:getExtents(); local x,z=0,0
    if o:getY()>=c:z()+e:z()/2 or o:getY()<=c:z()-e:z()/2 then x=o:getX() else z=o:getY() end
    local t=v:getWorldPos(x,0,z,Vector3f.new()); local f=p:getForwardDirection()
    local dx,dy=t:x()-p:getX(),t:y()-p:getY(); local n=math.sqrt(dx*dx+dy*dy)
    return {available=true,targetX=t:x(),targetY=t:y(),facingDot=n>0 and (dx*f:getX()+dy*f:getY())/n or 0,
        collides=map:lineClearCollide(p:getX(),p:getY(),t:x(),t:y(),math.floor(p:getZ()),v,false,true)}
end)
return r
'''


SPAWN_CANDIDATES = ((10804, 10164), (10780, 10140), (10804, 10188),
                    (10780, 10164), (10828, 10164), (10828, 10140),
                    (10756, 10140), (10804, 10116))


def clear_spawn_candidates(vehicles, candidates=SPAWN_CANDIDATES):
    """Keep 14 tiles before spawn so a native one-tile spawn offset still leaves 12."""
    return [(x, y) for x, y in candidates
            if all(math.hypot(x-v["x"], y-v["y"]) >= 14 for v in vehicles)]


class InteriorLab:
    def __init__(self, session, output):
        self.mp = import_driver("final-mp-features")
        metadata = json.loads((session / "session.json").read_text(encoding="utf-8-sig"))
        clients = {record["name"]: record for record in metadata["clients"]}
        self.h = self.mp.load_helpers()
        self.h.configure(output, f'http://127.0.0.1:{clients["client-a"].get("port",18470)}/lua?depth=8&sandbox=false')
        self.b = self.mp.load_helpers()
        self.b.ENDPOINT = f'http://127.0.0.1:{clients["client-b"].get("port",18472)}/lua?depth=8&sandbox=false'
        self.h.SCREENS = Path(clients["client-a"]["cache"]) / "Screenshots"
        self.b.SCREENS = Path(clients["client-b"]["cache"]) / "Screenshots"
        self.server = self.mp.ServerEval(self.h)
        self.vid, self.box, self.input_until = -1, 1, 0.0
        self.h.REPORT.update(scope=__doc__.strip(), serverNoJava=metadata.get("serverNoJava",True),
                             lootNativeMouseInput=False, lootUsesProductionTransferAction=True,
                             inputCoverage=["E entry/exit", "upper box context-menu pickup", "W driving", "Space braking"])

    def state(self, side):
        code = READ_STATE.replace("VID", str(self.vid)).replace("BOX", str(self.box))
        if side == "server":
            state = json.loads(self.server(JSON_ENCODER + code + "\nreturn enc(r)"))
        else:
            state = (self.h if side == "A" else self.b).lua(code + "\nreturn r")
        if state.get("ready"):
            for key in ("partIds", "loot", "floor"):
                state[key] = self.h._sequence(state.get(key))
            for player in state.get("players", {}).values():
                if "inventory" in player:
                    player["inventory"] = self.h._sequence(player["inventory"])
        return state

    def wait(self, read, predicate, label, timeout=60):
        self.h.REPORT["activeWait"] = label
        deadline = time.monotonic() + timeout
        latest = None
        while time.monotonic() < deadline:
            latest = read()
            if time.monotonic() >= self.input_until and predicate(latest):
                return latest
            time.sleep(.15)
        raise AssertionError(f"Timeout: {label}; last={json.dumps(latest, default=str)}")

    def input(self, side, *, key=None, milliseconds=180, x=None, y=None, right=False):
        api = self.h if side == "A" else self.b
        if key is not None:
            api.lua(f"MEMCNativeLab.holdKey({int(key)},{int(milliseconds)}); return true")
            self.input_until = time.monotonic() + milliseconds / 1000 + .1
            event = dict(client=side, api="holdKey", key=key, milliseconds=milliseconds)
        else:
            self.h.check(0 <= x < 1280 and 0 <= y < 720, f"offscreen native input: {x},{y}")
            api.lua(f"MEMCNativeLab.clickButtonAt({int(x)},{int(y)},{1 if right else 0}); return true")
            self.input_until = time.monotonic() + (.32 if right else .55)
            event = dict(client=side, api="clickButtonAt", x=x, y=y, right=right)
        self.h.REPORT["inputs"].append(event)
        self.h.REPORT["nativeInput"] = True

    def capture(self, side, name):
        old_endpoint, old_screens = self.h.ENDPOINT, self.h.SCREENS
        try:
            if side == "B": self.h.ENDPOINT, self.h.SCREENS = self.b.ENDPOINT, self.b.SCREENS
            return self.h.capture(name)
        finally:
            self.h.ENDPOINT, self.h.SCREENS = old_endpoint, old_screens

    def all_states(self):
        return {side: self.state(side) for side in ("A", "B", "server")}

    def wait_same_boxes(self, expected=None):
        def same(states):
            if not all(s.get("ready") for s in states.values()): return False
            values = [s["boxes"] for s in states.values()]
            return values[0] == values[1] == values[2] and (expected is None or values[0] == expected)
        return self.wait(self.all_states, same, "identical exact box inventory-item IDs on A/B/server")

    def position_players_at_field(self):
        """Setup fixture: native admin teleports with explicit destinations.

        Client teleport receipt precedes server position replication. Do not
        derive the guest destination from an admin position that may be stale.
        Read actual coordinates/squares on both clients and the server before
        allowing vehicle/input checks to begin.
        """
        local = 'local p=getPlayer();return {x=p:getX(),y=p:getY(),z=p:getZ(),square=p:getCurrentSquare()~=nil,outside=p:getVehicle()==nil}'
        remote = JSON_ENCODER + '''local r={};local ps=getOnlinePlayers()
for i=0,ps:size()-1 do local p=ps:get(i);local n=p:getUsername()
if n=="MELensAdmin" or n=="MELensGuest" then
r[n]={x=p:getX(),y=p:getY(),z=p:getZ(),square=p:getCurrentSquare()~=nil,outside=p:getVehicle()==nil} end end
return enc(r)'''
        fixture = {"commands": ['/teleportto 10813,10140,0', '/teleportto "MELensGuest" 10813,10140,0']}
        self.h.REPORT.setdefault('positionFixtures', []).append(fixture)

        def positions():
            value = {'A': self.h.lua(local), 'B': self.b.lua(local), 'server': json.loads(self.server(remote))}
            fixture['last'] = value
            return value

        fixture['before'] = positions()
        self.h.check(fixture['before']['A']['outside'] and fixture['before']['B']['outside'],
                     'field setup must not eject either player')
        self.h.lua("SendCommandToServer('/teleportto 10813,10140,0');return true")
        self.h.lua('SendCommandToServer(\'/teleportto "MELensGuest" 10813,10140,0\');return true')

        def ready(states):
            rows = [states['A'], states['B'], states['server'].get('MELensAdmin', {}),
                    states['server'].get('MELensGuest', {})]
            return all(row.get('square') and row.get('outside') and abs(row.get('x', 0)-10813)<4
                       and abs(row.get('y', 0)-10140)<4 and abs(row.get('z', 9))<.1 for row in rows)

        fixture['after'] = self.wait(positions, ready, 'both clients and server at explicit field coordinates', timeout=30)
        return fixture['after']

    def enter_e(self, side):
        api = self.h if side == "A" else self.b
        diagnostic = {"client": side, "vehicleId": self.vid}
        self.h.REPORT.setdefault("entryDiagnostics", []).append(diagnostic)
        def observe(stage):
            result = api.lua(ENTRY_DIAGNOSTIC.replace("VID", str(self.vid)))
            diagnostic[stage] = result
            return result
        observe("beforeApproach")
        api.lua(f'local p=getPlayer(); local v=getVehicleById({self.vid}); '
                'MELensTest=MELensTest or {}; MELensTest.vehicle=v; '
                'ISTimedActionQueue.add(ISPathFindAction:pathToVehicleSeat(p,v,MELens.cabinSeat(v))); return true')
        self.wait(lambda: api.lua('local p=getPlayer(); return {idle=#ISTimedActionQueue.getTimedActionQueue(p).queue==0,'
                                 'near=MELens.nearWayIn(p,MELensTest.vehicle,MELens.profileFor(MELensTest.vehicle))}'),
                  lambda s: s["idle"] and s["near"], f"{side} at F700 rear entrance")
        # Path arrival alone does not face the door. Vanilla E requires a facing
        # dot above 0.5; orientation is fixture setup, entry remains native input.
        observe("beforeFacing")
        api.lua('local p=getPlayer(); local v=MELensTest.vehicle; local q=MELens.profileFor(v); '
                'local outside=v:getPassengerPosition(MELens.cabinSeat(v,q),"outside"); local point=Vector3f.new(); '
                'v:getPassengerPositionWorldPos(outside,point); p:faceLocation(point:x(),point:y()); return true')
        def usable(state):
            row = state.get("usablePart", {})
            return row.get("ok") and row.get("value") == state.get("vehicle", {}).get("door")
        self.wait(lambda: observe("beforeE"), usable, f"{side} faces usable entrance before native E")
        self.input(side, key=int(diagnostic["beforeE"]["keybind"]["value"]))
        return self.wait(lambda: self.state(side),
                         lambda s: s.get("ready") and s["players"]["MELensAdmin" if side == "A" else "MELensGuest"]["vehicleId"] == self.vid,
                         f"{side} native E entry")

    def pickup_menu(self, point):
        self.input("A", x=point["x"], y=point["y"], right=True)
        menu_code = r'''
local c=getPlayerContextMenu(0); if not c or not c:isVisible() then return false end
for i,o in ipairs(c.options) do local sub=o.subOption and c:getSubMenu(o.subOption)
    for j,k in ipairs(sub and sub.options or {}) do
        if k.name==getText('ContextMenu_MELens_PickUp') then
            return {parentX=math.floor(c:getX()+70),parentY=math.floor(c:getItemY(i)+c.itemHgt/2),
                x=math.floor(sub:getX()+70),y=math.floor(sub:getItemY(j)+sub.itemHgt/2),
                visible=sub:isVisible(),disabled=k.notAvailable==true}
        end
    end
end
return false
'''
        menu = self.wait(lambda: self.h.lua(menu_code), lambda s: bool(s), "native box context menu")
        self.h.check(not menu["disabled"], "upper empty box Pick up is disabled")
        self.capture("A", "mp-upper-box-menu")
        self.input("A", x=menu["parentX"], y=menu["parentY"])
        menu = self.wait(lambda: self.h.lua(menu_code), lambda s: bool(s) and s["visible"], "box submenu visible")
        self.input("A", x=menu["x"], y=menu["y"])

    def prepare(self, allow_server_java=False, vehicle_script="Base.87fordF700box"):
        # The phobia checks reuse this fixture on a server that runs the Java part (its trait hook needs it there).
        expected = ("true/true", "true/false") if allow_server_java else ("true/true",)
        self.h.check(self.server('return tostring(isServer()).."/"..tostring(MELensRV==nil)') in expected, "server must have no MELensRV Java")
        for api in (self.h, self.b):
            api.lua('if MELens.Dashboard.instance then MELens.Dashboard.instance:close() end; '
                    'ISUIHandler.setVisibleAllUI(false); MEMCNativeLab.releaseKeys(); '
                    'local p=getPlayer(); if p:getVehicle() then MELens.leave(p) end; return true')
        for api in (self.h, self.b):
            self.wait(lambda api=api: api.lua('return getPlayer():getVehicle()==nil'), bool, "players outside old camper")
        self.h.lua("SendCommandToServer('/teleportto 10813,10140,0'); return true")
        self.wait(lambda: self.h.lua('local p=getPlayer(); return p:getCurrentSquare()~=nil and math.abs(p:getX()-10813)<2 and math.abs(p:getY()-10140)<2'), bool, "admin at owned open test field")
        self.h.lua('SendCommandToServer(\'/teleportplayer "MELensGuest" "MELensAdmin"\'); return true')
        self.wait(lambda: self.b.lua('local p=getPlayer(); return p:getCurrentSquare()~=nil and math.abs(p:getX()-10813)<4 and math.abs(p:getY()-10140)<4'), bool, "guest teleported by admin to test field")
        find = 'local p=getPlayer(); local a={}; local it=getCell():getVehicles():iterator(); while it:hasNext() do local v=it:next(); if v:getScript():getFullName()==' + json.dumps(vehicle_script) + ' and p:DistToSquared(v:getX(),v:getY())<6400 then a[#a+1]=v:getId() end end; return a'
        old = set(self.h._sequence(self.h.lua(find)))
        loaded = json.loads(self.server(JSON_ENCODER + 'local a={}; local it=getCell():getVehicles():iterator(); '
                                        'while it:hasNext() do local v=it:next(); a[#a+1]={id=v:getId(),x=v:getX(),y=v:getY()} end; return enc(a)'))
        loaded = self.h._sequence(loaded)
        candidates = clear_spawn_candidates(loaded)
        self.h.REPORT["spawn"] = {"loadedVehicles": loaded, "minimumCenterDistanceTiles": 12,
                                   "preSpawnClearanceTiles": 14, "candidates": candidates,
                                   "oldVehicleIds": sorted(old), "attempts": [], "oldVehiclesPreserved": True}
        self.h.check(candidates, "no candidate has 14 tiles of clearance from all loaded vehicles")
        for x, y in candidates:
            # An earlier admin spawn may arrive late. Adopt that one instead of
            # placing another vehicle on top of it during a retry.
            new = set(self.h._sequence(self.h.lua(find))) - old
            if new:
                self.h.check(len(new) == 1, f"ambiguous late F700 spawn: {new}")
                self.vid = int(next(iter(new)))
                break
            self.h.lua(f"SendCommandToServer('/addvehicle {vehicle_script} {x},{y},0'); return true")
            self.h.REPORT["spawn"]["attempts"].append({"x": x, "y": y})
            try:
                new = self.wait(lambda: set(self.h._sequence(self.h.lua(find))) - old, bool, "fresh F700 replication", timeout=18)
                self.h.check(len(new) == 1, f"ambiguous fresh F700 spawn: {new}")
                self.vid = int(next(iter(new)))
                break
            except AssertionError:
                continue
        self.h.check(self.vid >= 0, "no F700 spawned on clear test field")
        clearance = json.loads(self.server(JSON_ENCODER + f'local v=getVehicleById({self.vid}); assert(v); local r={{minimum=1000000}}; '
                                           'local it=getCell():getVehicles():iterator(); while it:hasNext() do local a=it:next(); '
                                           'if a~=v then local d=math.sqrt((a:getX()-v:getX())^2+(a:getY()-v:getY())^2); '
                                           'if d<r.minimum then r.minimum=d; r.nearestVehicleId=a:getId() end end end; return enc(r)'))
        self.h.REPORT["spawn"].update(vehicleId=self.vid, actualClearance=clearance,script=vehicle_script)
        self.h.check(clearance["minimum"] >= 12, "native spawn shifted within 12 tiles of another vehicle")
        # The native /addvehicle command already repairs the fresh vehicle.
        # A second immediate repair races initial container replication.
        self.server(f'local v=getVehicleById({self.vid}); assert(v); '
                    'for i,s in ipairs(MELens.profileFor(v).spots) do if s.empty then '
                    'local p=MELens.Parts.spotPart(v,i); assert(not p:getItemContainer() or p:getItemContainer():isEmpty(),"fresh bare spot unexpectedly holds cargo"); '
                    'p:setInventoryItem(nil); MELens.Parts.applyPiece(v,p); v:transmitPartItem(p) end end; '
                    'for i=0,v:getPartCount()-1 do local p=v:getPartByIndex(i); local d=p:getDoor(); '
                    'if d then d:setLocked(false); v:transmitPartDoor(p) end end; '
                    'local gas=v:getPartById("GasTank"); if gas then gas:setContainerContentAmount(gas:getContainerCapacity()); '
                    'pcall(function() v:transmitPartUsedDelta(gas) end) end; '
                    'local ps=getOnlinePlayers(); for i=0,ps:size()-1 do local p=ps:get(i); if p:getUsername()=="MELensAdmin" then '
                    'local key=v:createVehicleKey(); p:getInventory():AddItem(key); sendAddItemToContainer(p:getInventory(),key) end end; return "prepared"')
        self.wait(lambda: self.b.lua(f"return getVehicleById({self.vid})~=nil"), bool, "guest sees F700")
        self.enter_e("A"); self.enter_e("B")
        states = self.wait_same_boxes()
        self.h.check(states["A"]["partIds"] == states["B"]["partIds"] == states["server"]["partIds"], "network part order differs")
        for side, s in states.items():
            self.h.check(s["players"]["MELensAdmin"]["vehicleId"] == self.vid and s["players"]["MELensGuest"]["vehicleId"] == self.vid
                         and s["players"]["MELensAdmin"]["standing"] and s["players"]["MELensGuest"]["standing"],
                         f"{side} lacks both standing passengers")
        self.h.record("both-enter-f700-with-native-e-and-identical-parts", {}, states)

    def loot_and_pickup(self):
        point = self.h.lua(PICK_POINT)
        self.h.check(point and point["level"] >= 2, "no visible upper box can be ray-picked")
        self.box = int(point["index"])
        marker = int(self.server(f'local v=getVehicleById({self.vid}); local c=v:getPartById("MELensSpot{self.box}"):getItemContainer(); '
                                 'local old={}; for i=0,c:getItems():size()-1 do old[#old+1]=c:getItems():get(i) end; '
                                 'for _,it in ipairs(old) do c:Remove(it); sendRemoveItemFromContainer(c,it) end; '
                                 'local it=c:AddItem("Base.Hammer"); sendAddItemToContainer(c,it); return it:getID()'))
        before = self.wait(self.all_states, lambda states: all(marker in self.h._sequence(s.get("loot")) for s in states.values()), "same fixture loot item ID on both clients/server")
        self.h.lua(f'local p=getPlayer(); local c=getVehicleById({self.vid}):getPartById("MELensSpot{self.box}"):getItemContainer(); '
                   f'local it=c:getItemWithID({marker}); assert(it); '
                   'ISTimedActionQueue.add(ISInventoryTransferAction:new(p,it,c,p:getInventory())); return true')
        after = self.wait(self.all_states, lambda states: all(not self.h._sequence(s.get("loot")) for s in states.values())
                          and marker in self.h._sequence(states["A"]["players"]["MELensAdmin"]["inventory"])
                          and marker in self.h._sequence(states["server"]["players"]["MELensAdmin"]["inventory"]), "native interior loot transfer reaches authority and observer")
        self.h.record("interior-box-loot-exact-item-id", before, after, nativeTransferAction=True, mouseDragDropVerified=False)
        before = after
        self.h.lua(f'local p=getPlayer(); local dst=getVehicleById({self.vid}):getPartById("MELensFloor"):getItemContainer(); '
                   f'local it=p:getInventory():getItemWithID({marker}); assert(it); '
                   'ISTimedActionQueue.add(ISInventoryTransferAction:new(p,it,p:getInventory(),dst)); return true')
        after = self.wait(self.all_states, lambda states: all(marker in s["floor"] for s in states.values())
                          and all(marker not in states[side]["players"]["MELensAdmin"]["inventory"] for side in ("A", "server")),
                          "same exact item deposited into Floor on A/B/server")
        self.h.record("interior-floor-deposit-exact-item-id", before, after, nativeTransferAction=True, mouseDragDropVerified=False)
        before = after
        self.b.lua(f'local p=getPlayer(); local src=getVehicleById({self.vid}):getPartById("MELensFloor"):getItemContainer(); '
                   f'local it=src:getItemWithID({marker}); assert(it); '
                   'ISTimedActionQueue.add(ISInventoryTransferAction:new(p,it,src,p:getInventory())); return true')
        after = self.wait(self.all_states, lambda states: all(marker not in s["floor"] for s in states.values())
                          and all(marker in states[side]["players"]["MELensGuest"]["inventory"] for side in ("B", "server")),
                          "guest loots identical Floor item and server accepts transfer")
        self.h.record("guest-interior-floor-loot-exact-item-id", before, after, nativeTransferAction=True, mouseDragDropVerified=False)
        before = self.wait_same_boxes()
        expected = dict(before["A"]["boxes"]); picked_id = expected[str(self.box)]; expected[str(self.box)] = -1
        # Recompute ray after any camera following while the loot action ran.
        point = self.h.lua(PICK_POINT)
        self.h.check(point and int(point["index"]) == self.box, "visible target changed before pickup")
        self.pickup_menu(point)
        after = self.wait_same_boxes(expected)
        for side in ("A", "server"):
            self.h.check(picked_id in self.h._sequence(after[side]["players"]["MELensAdmin"]["inventory"]), f"{side} lost original picked box ID")
        self.h.record("upper-box-native-context-pickup-only-target-removed", before, after, index=self.box, level=point["level"], originalBoxId=picked_id)
        self.capture("A", "mp-upper-box-picked")
        self.capture("B", "mp-upper-box-observer")

    @staticmethod
    def aligned(state, tolerance=.7):
        if not state.get("ready"): return False
        b = state["players"].get("MELensGuest", {})
        return b.get("vehicleId") == state["vehicle"]["id"] and b.get("seat", -1) >= 0 and math.hypot(
            b["x"] - b["expectedX"], b["y"] - b["expectedY"]) < tolerance

    def drive_and_reenter(self):
        self.h.lua('MELens.leave(getPlayer()); return true')
        self.wait(lambda: self.h.lua('return getPlayer():getVehicle()==nil'), bool, "actor exits cargo for driver's cab")
        self.h.lua(f'ISVehicleMenu.onEnter(getPlayer(),getVehicleById({self.vid}),0); return true')
        approached = self.wait(lambda: self.state("A"),
                               lambda s: s.get("ready") and (s["players"]["MELensAdmin"]["seat"] == 0
                                   or (s["players"]["MELensAdmin"].get("queue") == 0
                                       and not s["players"]["MELensAdmin"].get("pathing"))),
                               "stock driver approach settles")
        if approached["players"]["MELensAdmin"]["seat"] != 0:
            # Stock ISEnterVehicle.start can reject the first queued entry at
            # its two-tile outside-position gate. Retry once at the reached door.
            self.h.REPORT["driverEntryRetriedAtDoor"] = True
            self.h.lua(f'ISVehicleMenu.onEnter(getPlayer(),getVehicleById({self.vid}),0); return true')
        self.wait(lambda: self.state("A"), lambda s: s.get("ready") and s["players"]["MELensAdmin"]["seat"] == 0, "normal queued driver-seat entry")
        self.h.lua('ISTimedActionQueue.add(ISStartVehicleEngine:new(getPlayer())); return true')
        self.wait(lambda: self.state("A"), lambda s: s["vehicle"]["engine"], "engine starts using real authoritative vehicle key", timeout=30)
        self.b.lua('MEMCNativeLab.releaseKeys(); return true')
        before = self.wait(self.all_states, lambda ss: all(self.aligned(s) for s in ss.values()), "stationary passenger aligned before driving")
        self.capture("A", "mp-driver-before-driving")
        self.capture("B", "mp-stationary-passenger-before-driving")
        self.input("A", key=17, milliseconds=3000)
        samples = []
        captured_moving = False
        deadline = time.monotonic() + 3.5
        while time.monotonic() < deadline:
            sample = self.all_states()
            samples.append(sample)
            if not captured_moving and abs(sample["A"]["vehicle"]["speed"]) > 2:
                self.capture("A", "mp-observer-during-driving")
                captured_moving = True
            time.sleep(.15)
        self.input("A", key=57, milliseconds=1500)
        after = self.wait(self.all_states, lambda ss: all(self.aligned(s) for s in ss.values()) and abs(ss["A"]["vehicle"]["speed"]) < .5,
                          "braked vehicle and stationary passenger align on both clients/server")
        moved = math.hypot(after["A"]["vehicle"]["x"]-before["A"]["vehicle"]["x"], after["A"]["vehicle"]["y"]-before["A"]["vehicle"]["y"])
        self.h.check(moved > 1.5, f"truck did not drive away enough: {moved:.3f} tiles")
        significant = [s for s in samples if math.hypot(s["A"]["vehicle"]["x"]-before["A"]["vehicle"]["x"], s["A"]["vehicle"]["y"]-before["A"]["vehicle"]["y"]) > 1.0]
        self.h.check(len(significant) >= 2 and all(self.aligned(s["A"], 1.0) for s in significant), "observer left remote passenger behind during actual W driving")
        original = before["B"]["players"]["MELensGuest"]
        for sample in samples:
            guest = sample["B"]["players"]["MELensGuest"]
            self.h.check(math.hypot(guest["localX"]-original["localX"],guest["localZ"]-original["localZ"]) < .04, "passenger moved inside; stationary-input control invalid")
        self.capture("A", "mp-driver-observer-after-driving")
        self.capture("B", "mp-passenger-inside-after-driving")
        self.h.record("stationary-passenger-follows-real-w-driven-f700", before, after, displacementTiles=moved, samples=samples,
                      renderEvidence="native framebuffer and actual remote character world position; no mesh-transform assertion")
        self.b.lua('local p=getPlayer(); local v=p:getVehicle(); local q=MELens.profileFor(v); MELens.walkTo(p,q.exitMarker.x,q.exitMarker.z); return true')
        self.wait(lambda: self.b.lua('return #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0 and not MELens.pathing(getPlayer())'), bool, "guest at exit marker")
        self.input("B", key=18)
        exited = self.wait(self.all_states, lambda ss: all(s["players"]["MELensGuest"]["vehicleId"] != self.vid for s in ss.values()), "native E exit replicated everywhere")
        self.enter_e("B")
        reentered = self.wait(self.all_states, lambda ss: all(self.aligned(s) for s in ss.values()), "native E reentry recovers correct standing membership")
        self.h.record("passenger-exit-and-reenter-after-driving", exited, reentered)
        self.capture("A", "mp-final-observer")
        self.capture("B", "mp-final-passenger")
        return reentered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=ROOT / "build/rv/final-mp-206")
    parser.add_argument("--output", type=Path, default=ROOT / "build/rv/final-mp-interiors")
    args = parser.parse_args()
    lab = None
    try:
        lab = InteriorLab(args.session.resolve(), args.output.resolve())
        lab.prepare(); lab.loot_and_pickup()
        lab.h.REPORT["final"] = lab.drive_and_reenter()
        print(f"NATIVE_MP_INTERIORS_PASSED {lab.h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        if lab is not None:
            try: lab.h.REPORT["lastSnapshot"] = lab.all_states()
            except Exception: pass
            path = lab.h.write_report("failed", error)
        else:
            args.output.mkdir(parents=True, exist_ok=True)
            path = args.output / "native-feature-tests.json"
            path.write_text(json.dumps({"status": "failed", "nativeInput": False, "preconditionFailure": True,
                                        "error": error}, indent=2) + "\n", encoding="utf-8")
        print(error, flush=True)
        print(f"NATIVE_MP_INTERIORS_FAILED {path}; parent-owned game/server left running", flush=True)
        return 1
    finally:
        if lab is not None:
            for api in (lab.h, lab.b):
                try: api.lua('MEMCNativeLab.releaseKeys(); return true')
                except Exception: pass
            try:
                lab.h.lua('local p=getPlayer(); local v=p:getVehicle(); if v and v:isDriver(p) then MEMCNativeLab.holdKey(57,1500) end; return true')
            except Exception: pass


if __name__ == "__main__":
    raise SystemExit(main())

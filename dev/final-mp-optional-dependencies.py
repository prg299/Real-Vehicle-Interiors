"""Native two-client bench/observer checks with ZombieBuddy as the only dependency.

The parent owns the game lifetime. Server spawn/repair and approach positioning
are setup fixtures. Entry, Rest menus, movement/get-up and exit use native input.
No furniture, inventory or animation handler is invoked as a tested action.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import traceback

import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'dev' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


READ = r'''
local v=getVehicleById(VID)
local r={ready=v~=nil,players={}}
if not v then return r end
local profile=MELens.profileFor(v)
local function add(p)
    local name=p:getUsername()
    if name~="MELensAdmin" and name~="MELensGuest" then return end
    local pv=p:getVehicle()
    local seat=v:getSeat(p)
    -- Cabin helpers are client-only. Read the shared passenger IDs on the
    -- dedicated server instead of calling a client animation/session helper.
    local a={id=p:getOnlineID(),seat=seat,vehicleId=pv and pv:getId() or -1,standing=false}
    if seat>=0 then
        local passenger=v:getScript():getPassenger(seat)
        for _,id in ipairs(MELens.standingIds(profile)) do
            if passenger and passenger:getId()==id then a.standing=true end
        end
    end
    if not isServer() then
        a.pose=p:getVariableString("damnPosition")
        a.cabin=p:getVariableString("MELensCabin")
        a.clip=MELensRV.animationProgress(p,"Bob_SatChair")
        a.anim=MELensRV.animInfo(p)
        a.alpha=p:getAlpha(0)
        if seat>=0 then
            local localPos=v:getPassengerLocalPos(seat,Vector3f.new())
            -- BaseVehicle.getPassengerLocalPos adds the script model offset.
            -- Furniture placement uses model-relative coordinates, as in the
            -- native bed-contact checks. Preserve raw data and compare one basis.
            local offset=v:getScript():getModel():getOffset()
            a.rawPassengerPosition={x=localPos:x(),y=localPos:y(),z=localPos:z()}
            a.modelOffset={x=offset:x(),y=offset:y(),z=offset:z()}
            a.position={x=localPos:x()-offset:x(),y=localPos:y()-offset:y(),z=localPos:z()-offset:z()}
            local passenger=v:getScript():getPassenger(seat)
            local expected=passenger and MELens.Parts.seatPose(v,profile,passenger:getId())
            if expected then a.expected={x=expected.x,y=expected.y,z=expected.z,pose=expected.pose,turn=expected.turn} end
        end
    end
    r.players[name]=a
end
local players=getOnlinePlayers()
for i=0,players:size()-1 do add(players:get(i)) end
if not isServer() and getPlayer() then add(getPlayer()) end
return r
'''

MODS = r'''
local mods=getActivatedMods();local a={}
for i=0,mods:size()-1 do a[#a+1]=mods:get(i) end
return {mods=a,damn=MELens.Parts.hasDamnSeats(),
    camper=getScriptManager():getVehicle("Base.Trailer54FlyingCloud22")~=nil,
    b700=getScriptManager():getVehicle("Base.87fordB700school")~=nil}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    d, interior = load('final-mp-interior-tests'), load('final-interior-tests')
    lab = d.InteriorLab(args.session, args.output)
    h = lab.h
    apis = {'A': h, 'B': lab.b}
    names = {'A': 'MELensAdmin', 'B': 'MELensGuest'}
    h.REPORT.update(scope=__doc__, inputCoverage=[], lootUsesProductionTransferAction=False, fixtures=[
        'fresh owned world and server spawn/repair/unlocked doors',
        'normal approach path and facing fixtures',
        'read-only furniture projection/production-picker fixture',
        'exit approach fixture uses normal cabin pathing'],
        unverified=['Steam transport', 'cold utility restart is a separate phase', 'human acceptance'])

    def server(code):
        return json.loads(lab.server(d.JSON_ENCODER + 'local r=(function() ' + code + ' end)();return enc(r)'))

    def peers():
        code = READ.replace('VID', str(lab.vid))
        return {'A': h.lua(code), 'B': lab.b.lua(code), 'server': server(code)}

    def row(states, side, person):
        return states.get(side, {}).get('players', {}).get(names[person], {})

    def standing(states, person):
        return all(row(states, side, person).get('vehicleId') == lab.vid and
                   row(states, side, person).get('standing') for side in ('A', 'B', 'server'))

    def fixture(side):
        apis[side].lua('''local p=getPlayer();local v=p:getVehicle()
MELensFeatureTest={vehicle=v,player=p,snapshot=function()
local q=ISTimedActionQueue.queues[p]
return {queueCount=q and #q.queue or 0,controls={}} end};return true''')
        apis[side].lua(interior.FIXTURE)

    def menus(side, point, labels, label):
        api = apis[side]
        lab.wait(lambda: interior.read_state(api), interior.idle, 'idle before ' + label)
        lab.input(side, x=point['x'], y=point['y'], right=True)
        for text in labels:
            state = lab.wait(lambda: interior.read_state(api),
                             lambda s: any(o['name'] == text for m in s['menus'] for o in m['options']),
                             'menu ' + text, timeout=8)
            options = [o for m in state['menus'] for o in m['options'] if o['name'] == text]
            h.check(len(options) == 1 and options[0]['enabled'], 'missing/disabled/ambiguous ' + text)
            lab.input(side, x=options[0]['x'], y=options[0]['y'])

    def bench(side, index):
        api = apis[side]
        before = lab.wait(peers, lambda s: standing(s, 'A') and standing(s, 'B'), 'both standing before Rest')
        point = api.lua(f'return MELensInteriorTest.point({index})')
        h.check(point['piece'] == 'medbench', 'expected normal passenger bench')
        menus(side, point, [point['header'], api.lua('return getText("ContextMenu_Rest")')], side + '-rest')

        def seated(states):
            rows = [row(states, role, side) for role in ('A', 'B', 'server')]
            if not all(r.get('vehicleId') == lab.vid and not r.get('standing', True) and r.get('seat', -1) >= 0 for r in rows):
                return False
            if len({r['seat'] for r in rows}) != 1:
                return False
            for role in ('A', 'B'):
                r = row(states, role, side)
                if r.get('pose') != 'MELensSeat' or r.get('clip', 0) <= 0 or 'standing=false' not in r.get('anim', ''):
                    return False
                if r.get('expected', {}).get('pose') != 'MELensSeat':
                    return False
                if any(abs(r['position'][axis] - r['expected'][axis]) > .035 for axis in ('x', 'y', 'z')):
                    return False
            return True

        first = lab.wait(peers, seated, side + ' same seated animation and contact on both clients', timeout=35)
        time.sleep(1.2)  # native500ms get-up guard plus animation/seat-switch blend
        settled = lab.wait(peers, seated, side + ' settled seating')
        for role in ('A', 'B'):
            h.check(abs(row(settled, role, side)['clip'] - row(first, role, side)['clip']) > .001,
                    side + ' seated clip did not advance on ' + role)
            lab.capture(role, side.lower() + '-seated-seen-by-' + role.lower())
        lab.input(side, key=int(api.lua('return getCore():getKey("Forward")')), milliseconds=200)
        after = lab.wait(peers, lambda s: standing(s, side) and all(
            row(s, role, side).get('pose') != 'MELensSeat' and 'standing=true' in row(s, role, side).get('anim', '')
            for role in ('A', 'B')), side + ' get-up and observer cleanup', timeout=35)
        for role in ('A', 'B'):
            lab.capture(role, side.lower() + '-standing-seen-by-' + role.lower())
        h.record('native-' + side.lower() + '-rest-get-up-observer', before, after,
                 seatedFirst=first, seatedSettled=settled, worldMenuNativeInput=True)
        h.REPORT['inputCoverage'].append(side + ' native Rest, movement get-up and peer pose cleanup')

    try:
        h.REPORT['activeMods'] = {'A': h.lua(MODS), 'B': lab.b.lua(MODS), 'server': server(MODS)}
        for role, value in h.REPORT['activeMods'].items():
            h.check(set(h._sequence(value['mods'])) == {'ZombieBuddy', 'RealVehicleInteriors', 'RealVehicleInteriors_Dev'}, role + ' not core-only')
            h.check(not value['damn'] and not value['camper'] and not value['b700'], role + ' optional packs unexpectedly available')
        lab.position_players_at_field()
        # Teleport updates the position before the destination chunks load.
        # AddVehicleCommand rejects an absent server square as Invalid location.
        # Choose a nearby clear tile only after all three worlds expose it.
        candidates = [(10819, 10140), (10807, 10140), (10813, 10146), (10813, 10134),
                      (10821, 10148), (10805, 10132)]
        points = '{' + ','.join('{x=' + str(x) + ',y=' + str(y) + '}' for x, y in candidates) + '}'
        square_code = 'local r={};for _,p in ipairs(' + points + ') do r[#r+1]=getCell():getGridSquare(p.x,p.y,0)~=nil end;return r'
        ready = lab.wait(lambda: {'server': h._sequence(server(square_code)),
                                 'A': h._sequence(h.lua(square_code)), 'B': h._sequence(lab.b.lua(square_code))},
                         lambda states: any(all(states[role][i] for role in ('A', 'B', 'server'))
                                            for i in range(len(candidates))),
                         'spawn tile loaded on both clients and server', timeout=20)
        loaded = h._sequence(server('local r={};local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next();r[#r+1]={x=v:getX(),y=v:getY()} end;return r'))
        candidates = d.clear_spawn_candidates(loaded, [point for i, point in enumerate(candidates)
                                                     if all(ready[role][i] for role in ('A', 'B', 'server'))])
        h.check(candidates, 'no clear native vehicle spawn')
        x, y = candidates[0]
        h.REPORT['spawn'] = {'x': x, 'y': y, 'tileReadyBeforeCommand': ready,
                             'loadedVehicles': loaded, 'clearanceTiles': 14}
        h.lua(f"SendCommandToServer('/addvehicle Base.VanSeats {x},{y},0');return true")
        find = ('local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next();'
                'if v:getScript():getFullName()=="Base.VanSeats" and (v:getX()-' + str(x) + ')^2+(v:getY()-' + str(y) + ')^2<25 '
                'then return tostring(v:getId()) end end;return "-1"')
        lab.vid = lab.wait(lambda: int(lab.server(find)), lambda n: n >= 0, 'fresh vanilla passenger van')
        server(f'local v=getVehicleById({lab.vid});v:repair();for i=0,v:getPartCount()-1 do local p=v:getPartByIndex(i);if p:getDoor() then p:getDoor():setLocked(false);v:transmitPartDoor(p) end end;return true')
        for side, api in apis.items():
            lab.wait(lambda api=api: api.lua(f'return getVehicleById({lab.vid})~=nil'), bool, side + ' vehicle replication')
            lab.enter_e(side)
            lab.wait(lambda api=api: api.lua('local p=getPlayer();return MELens.isStanding(p) and not MELens.pathing(p) and #ISTimedActionQueue.getTimedActionQueue(p).queue==0'), bool, side + ' normal entry complete')
            api.lua('ISUIHandler.setVisibleAllUI(true);return true')
            fixture(side)
        before_ids = lab.all_states()
        bench('A', 4)
        bench('B', 5)
        after_ids = lab.all_states()
        for role in ('A', 'B', 'server'):
            h.check(before_ids[role]['partIds'] == after_ids[role]['partIds'], role + ' seating changed part identities')
        for side in ('B', 'A'):
            api = apis[side]
            api.lua('MELensInteriorTest.positionAtExit();return true')
            lab.wait(lambda api=api: api.lua('return not MELens.pathing(getPlayer())'), bool, side + ' exit approach fixture')
            lab.input(side, key=int(api.lua('return getCore():getKey("Interact")')), milliseconds=200)
            after = lab.wait(peers, lambda states: all(row(states, role, side).get('vehicleId') == -1 for role in ('A', 'B', 'server')),
                             side + ' native exit on both peers and authority')
            h.REPORT['inputCoverage'].append(side + ' native Interact exit')
        h.record('native-core-peer-entry-and-exit', before_ids, after_ids, finalOutside=after)
        h.write_report('passed')
        print('CORE_ONLY_NATIVE_MP_PASSED', flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            h.REPORT['lastPeerState'] = peers()
        except Exception:
            pass
        for side in ('A', 'B'):
            try:
                lab.capture(side, 'failure-' + side.lower())
            except Exception:
                pass
        h.write_report('failed', error)
        print(error, flush=True)
        return 1
    finally:
        for api in apis.values():
            try:
                api.lua('MEMCNativeLab.releaseKeys();return true')
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(main())

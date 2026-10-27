"""Reacquire saved native fixtures and compare their complete prior snapshots.

Import performs no I/O. Relocation is an explicit streaming fixture; no vehicle,
item or inventory is created, repaired or replaced. Missing or changed state
fails. Both the fleet audit and closed-world verification use this contract.
"""
import json
import math
import time


def verify(h, expected, position, snapshot_code, timeout=40):
    sql, script = expected['sqlId'], expected['script']
    assert isinstance(sql, int) and sql > 0 and isinstance(script, str)
    lookup = '''local found;local it=getCell():getVehicles():iterator()
while it:hasNext() do local v=it:next();if v:getSqlId()=='''+str(sql)+''' then
assert(v:getScriptName()=='''+json.dumps(script)+''','preserved SQL identity has another script');found=v;break end end
MELensPreservationFixture={vehicle=found};return found~=nil'''
    reloaded = not h.lua(lookup)
    origin = None
    try:
        if reloaded:
            assert position and all(math.isfinite(position[key]) for key in ('x', 'y', 'z')), 'Missing preserved location'
            origin = h.lua('''local p=getPlayer();assert(not p:getVehicle(),'start preservation check outside')
MELensMedia.cameraOff();return {x=p:getX(),y=p:getY(),z=p:getZ()}''')
            h.lua(f'''local p=getPlayer();p:setX({position['x']+4});p:setY({position['y']});p:setZ({math.floor(position['z'])})
p:setLastX(p:getX());p:setLastY(p:getY());return true''')
            deadline = time.monotonic()+timeout
            while not h.lua(lookup):
                h.check(time.monotonic() < deadline, 'Saved fixture did not reload: '+str(sql))
                time.sleep(.15)
        actual = h.lua(snapshot_code.replace('local v=MELensLifecycle.vehicle',
                                            'local v=MELensPreservationFixture.vehicle'))
        identical = actual == expected
        h.REPORT.setdefault('fixturePreservation', []).append(dict(
            sql=sql, script=script, relocatedToSavedLocation=reloaded,
            snapshot=actual, inventoryUtilitiesAndInstalledIdsIdentical=identical,
            scope='Saved SQL/script lookup and full snapshot comparison; relocation is a streaming fixture'))
        h.check(identical, 'Preserved fixture contents/state changed: '+str(sql))
        return actual
    finally:
        if origin is not None:
            h.lua(f'''local p=getPlayer();p:setX({origin['x']});p:setY({origin['y']});p:setZ({origin['z']})
p:setLastX(p:getX());p:setLastY(p:getY());return true''')
        h.lua('MELensPreservationFixture=nil;return true')

"""Native locomotion, observer and furniture checks in a furnished KI5 camper."""
import argparse
import importlib.util
import json
from pathlib import Path
import traceback

def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--transitions-only',action='store_true')
    parser.add_argument('--restore-only',action='store_true')
    parser.add_argument('--baseline',type=Path)
    args=parser.parse_args()
    lab=load('final-mp-interior-tests').InteriorLab(args.session,args.output/'setup')
    motion=None
    try:
        if args.restore_only:
            baseline=json.loads(args.baseline.read_text(encoding='utf-8-sig'))
            expected={'native-walk-same-open-cabin-route','native-run-same-open-cabin-route',
                      'a-native-rest-seats-standing-player','b-native-rest-seats-standing-player',
                      'both-clients-normal-outside-animation-after-rest-and-exit'}
            passed={case['name'] for case in baseline['cases'] if case.get('passed')}
            lab.h.check(expected<=passed and baseline.get('final'),'motion/transition acceptance cases are incomplete')
            before=baseline['final']
            lab.vid=int(before['A']['vehicle']['id'])
            lab.h.REPORT['baselineReport']=str(args.baseline)
            lab.h.REPORT['setupFixture']='Move the waiting guest two tiles away from the same exit point before sequential native re-entries.'
            lab.b.lua('local p=getPlayer();p:setX(p:getX()-2);p:setLastX(p:getX());return true')
            for side in ('A','B'):lab.enter_e(side)
            after=lab.all_states()
            for side in ('A','B','server'):
                for key in ('partIds','furniture','storage','floor'):
                    lab.h.check(before[side][key]==after[side][key],'re-entry changed '+side+'/'+key+' identities')
            for side,name in (('A','MELensAdmin'),('B','MELensGuest'),('server','MELensAdmin'),('server','MELensGuest')):
                lab.h.check(before[side]['players'][name]['inventory']==after[side]['players'][name]['inventory'],
                            're-entry changed '+side+'/'+name+' inventory IDs')
            lab.capture('A','mp-reentry-actor');lab.capture('B','mp-reentry-observer')
            lab.h.record('both-native-reentries-retain-furniture-storage-and-player-item-identities',before,after)
            lab.h.write_report('passed')
            print('NATIVE_MP_REENTRY_IDENTITIES_PASSED',flush=True)
            return 0
        # Reuse the owned-field spawn, authority/part checks and real E entry.
        # The camper aisle can show a sustained native run; short vanilla vans
        # reach their wall before a complete running comparison is possible.
        if args.transitions_only:
            lab.vid=int(lab.h.lua('local v=getPlayer():getVehicle();return v and v:getId() or -1'))
            lab.h.check(lab.vid>=0,'continuation needs both standing players in the owned camper')
        else:
            lab.prepare(allow_server_java=True,vehicle_script='Base.Trailer54FlyingCloud22')
            parked=f'local v=getVehicleById({lab.vid});v:setPhysicsActive(false);v:setSpeedKmHour(0);v:setAngles(0,0,0);return true'
            lab.server(parked)
            for api in (lab.h,lab.b):api.lua(parked)
            lab.h.REPORT['parkedFixture']='Fresh camper parked and aligned to keyboard axes on all peers; vehicle physics is outside this motion test.'
            lab.h.lua('MELens.walkTo(getPlayer(),.02,1.8);return true')
            lab.wait(lambda: lab.h.lua('local d=MELens.debugState();return not d.pathing and math.abs(d.x-.02)<.04 and math.abs(d.z-1.8)<.04'),
                     bool,'actor reaches the front of the ordinary camper aisle',timeout=45)
        before=lab.all_states()
        lab.h.write_report('passed')
        motion=load('final-mp-motion-tests').MotionLab(args.session,args.output/'motion')
        if args.transitions_only:motion.transitions()
        else:motion.run()
        after=motion.lab.all_states()
        for side in ('A','B','server'):
            lab.h.check(before[side]['partIds']==after[side]['partIds'],'movement changed '+side+' part identities')
            for key in ('furniture','storage','floor'):
                lab.h.check(before[side][key]==after[side][key],'movement changed '+side+'/'+key+' item IDs')
        for side,name in (('A','MELensAdmin'),('B','MELensGuest'),('server','MELensAdmin'),('server','MELensGuest')):
            lab.h.check(before[side]['players'][name]['inventory']==after[side]['players'][name]['inventory'],
                        'movement/furniture actions changed '+side+'/'+name+' inventory IDs')
        motion.h.record('movement-retains-furniture-storage-and-player-item-identities',before,after)
        motion.h.write_report('passed')
        print('NATIVE_MP_MOVEMENT_RELEASE_PASSED',flush=True)
        return 0
    except Exception:
        error=traceback.format_exc()
        (motion.h if motion else lab.h).write_report('failed',error)
        print(error,flush=True)
        return 1
    finally:
        for api in (lab.h,lab.b):
            try:api.lua('MEMCNativeLab.releaseKeys();if RVI_MPFrameMotion then Events.OnPostRender.Remove(RVI_MPFrameMotion.tick) end;return true')
            except Exception:pass

if __name__=='__main__':raise SystemExit(main())

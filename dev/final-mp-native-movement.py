"""Native locomotion, observer and furniture checks in a furnished KI5 camper."""
import argparse
import importlib.util
from pathlib import Path
import traceback

def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    lab=load('final-mp-interior-tests').InteriorLab(args.session,args.output/'setup')
    motion=None
    try:
        # Reuse the owned-field spawn, authority/part checks and real E entry.
        # The camper aisle can show a sustained native run; short vanilla vans
        # reach their wall before a complete running comparison is possible.
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
        motion.run()
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

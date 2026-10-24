"""Final native fleet audit after the independent visual/role reviews.

Each child records its own input/fixture boundary. The parent owns the disposable
game process; all captures come from that installed package and actual renderer.
"""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-source',help='Prior service-save run to cold-load before the audit')
    parser.add_argument('--phase',choices=('shells','features','gates','fleet','polish','stock','reload','original-controls','edges','edge-presets','all'),default='all')
    parser.add_argument('--polish-plan',type=Path,help='Owned JSON plan of changed profiles and shell families to retake')
    parser.add_argument('--resume-fleet',action='store_true',help='Continue a completed partial factory review before gallery and persistence checks')
    args=parser.parse_args()
    phases={
      'shells':[('rear-door-tests.py',['--all-bodies','--white-passenger',
                                   '--height-headings','N','W','--missing-headings','E','W'])],
      'features':[
        ('utility-furniture-tests.py',['--cargo','--only','workbench']),
        ('utility-furniture-tests.py',['--cargo','--only','medbench','--vehicle','Base.85chevyStepVanSWAT']),
        ('open-storage-visual-tests.py',[]),
      ],
      'stock':[('propane-cargo-tests.py',[]),('service-save-tests.py',[])],
      'original-controls':[
        ('cab-wall-tests.py',['--only','Base.87fordB700school','--empty','--all-headings',
                             '--front-positions','1.97','1.98','--front-tops','.70',
                             '--native-exterior-control','--output-name','bus-front-back-controls']),
        ('shell-isolation-tests.py',[]),
      ],
      'fleet':[
        ('vehicle-role-tests.py',['--all','--output-name','factory-layouts']),
        ('fleet-gallery.py',['--output-name','gallery-immersive']),
        ('propane-cargo-tests.py',[]),
        ('service-save-tests.py',[]),
      ],
    }
    if args.phase=='polish':
        if not args.polish_plan:parser.error('--phase polish requires --polish-plan')
        import json
        plan=json.loads(args.polish_plan.read_text())
        selected_vehicles=[value for name in plan['retakeVehicles'] for value in ('--only',name)]
        bodies=[value for name in plan['bodyRepresentatives'] for value in ('--only',name)]
        changes=[value for name in plan['changedProfiles'] for value in ('--changed',name)]
        phases['polish']=[
            ('profile-snapshot.py',['--compare-run',plan['baseline'],*changes]),
            ('cab-wall-tests.py',[*bodies,'--empty','--all-headings','--native-exterior-control','--output-name','original-shells']),
            ('vehicle-role-tests.py',['--all','--native-selected',*selected_vehicles,'--output-name','factory-final-retakes']),
            ('fleet-gallery.py',['--output-name','gallery-immersive']),
            ('propane-cargo-tests.py',[]),
            ('service-save-tests.py',[]),
        ]
    if args.phase=='reload':
        if not args.verify_source:parser.error('--phase reload requires --verify-source')
        phases['reload']=[('propane-cargo-tests.py',['--verify-source',args.verify_source])]
        if args.polish_plan:
            import json
            plan=json.loads(args.polish_plan.read_text())
            vehicles=[value for name in plan['retakeVehicles'] for value in ('--only',name)]
            bodies=[value for name in plan['bodyRepresentatives'] for value in ('--only',name)]
            changes=[value for name in plan['changedProfiles'] for value in ('--changed',name)]
            phases['reload'] += [
                ('profile-snapshot.py',['--compare-run',plan['baseline'],*changes]),
                ('cab-wall-tests.py',[*bodies,'--empty','--all-headings','--native-exterior-control','--output-name','original-shells']),
                ('vehicle-role-tests.py',['--all','--native-selected',*vehicles,'--output-name','factory-final-retakes']),
            ]
    edge_cases=(
        ('van-high','Base.Van','N',3),
        ('passenger','Base.VanSeats','N',2),
        ('ambulance-side','Base.VanAmbulance','S',2),
        ('ambulance-high','Base.VanAmbulance','N',3),
        ('e150','Base.86fordE150','W',2),
        ('chevy','Base.85chevyStepVan','E',2),
    )
    for phase,option,values,prefix in (
        ('edges','--cut-inset-sweep','0,.02,.04,.06,.10,.16','native-edge-'),
        ('edge-presets','--cut-inset-presets','0:0:0,.06:0:.16,.10:0:.16,.10:.02:.16','native-edge-preset-'),
    ):
        phases[phase]=[('rear-door-tests.py',[
            '--all-bodies','--only',vehicle,'--headings',heading,'--height-choice',str(height),
            option,values,'--white-passenger','--output-name',prefix+label,
        ]) for label,vehicle,heading,height in edge_cases]
    if args.resume_fleet:
        if args.phase=='polish':
            phases['polish']=phases['polish'][2:]
            phases['polish'][0][1].append('--resume')
        else:phases['fleet'][0][1].append('--resume')
    selected=(('shells','features','fleet') if args.phase=='all' else
              ('shells','features') if args.phase=='gates' else (args.phase,))
    checks=[check for phase in selected for check in phases[phase]]
    if args.verify_source:checks.insert(0,('service-save-tests.py',['--verify-source',args.verify_source]))
    for driver,args in checks:
        print('IMMERSIVE_AUDIT_START '+driver+' '+' '.join(args),flush=True)
        result=subprocess.run([sys.executable,str(ROOT/'dev'/driver),*args],cwd=ROOT)
        if result.returncode:return result.returncode
        print('IMMERSIVE_AUDIT_PASS '+driver,flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())

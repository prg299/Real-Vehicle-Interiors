"""Focused ambulance factory/renderer review in the parent's owned game."""
from pathlib import Path
import json
import os
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
command=[sys.executable,str(root/'dev/vehicle-role-tests.py'),'--all','--native-selected',
         '--output-name','ambulance-layouts']
for name in ('Base.VanAmbulance','Base.86fordE150med','Base.90fordF350ambulance','Base.90fordF350SWAT'):
    command += ['--only',name]
result=subprocess.run(command,cwd=root).returncode
if result:raise SystemExit(result)
for name,args in (('ambulance-door-tests',[]),('ambulance-slot-tests',[]),
                  ('utility-furniture-tests',['--cargo','--only','medbench','--vehicle','Base.90fordF350ambulance']),
                  ('bed-tests',['--vehicle','Base.90fordF350ambulance','--heading','E',
                                '--bed-index','5','--label','stretcher-right-e'])):
    result=subprocess.run([sys.executable,str(root/'dev'/(name+'.py')),*args],cwd=root).returncode
    if result:raise SystemExit(result)
(root/'build/rv'/os.environ['RVI_CAPTURE_RUN']/'request.json').write_text(json.dumps({'action':'stop'}))

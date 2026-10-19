"""Run the remaining snow cases inside an already guarded, owned native game."""
import importlib.util
import json
import os
from pathlib import Path

spec=importlib.util.spec_from_file_location('snow_checks',Path(__file__).with_name('snow-tests.py'))
snow=importlib.util.module_from_spec(spec)
spec.loader.exec_module(snow)

cases=[
    ('airflyte-e','Base.Trailer61Airflyte','E','snow'),
    ('bambi-s','Base.Trailer61Bambi16','S','snow'),
    ('scamp13-n','Base.Trailer87Scamp13','N','snow'),
    ('scamp16-w','Base.Trailer87Scamp16','W','snow'),
    ('bus-e','Base.87fordB700school','E','snow'),
    ('truck-s','Base.87fordF700box','S','snow'),
    ('cloud-n','Base.Trailer54FlyingCloud22','N','snow'),
    ('cloud-s','Base.Trailer54FlyingCloud22','S','snow'),
    ('cloud-w','Base.Trailer54FlyingCloud22','W','snow'),
    ('cloud-rain','Base.Trailer54FlyingCloud22','E','rain'),
]

if __name__=='__main__':
    run=snow.ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    jar=snow.hashlib.sha256((run/'home/Zomboid/mods/RealVehicleInteriors/42.21/media/java/RealVehicleInteriors.jar').read_bytes()).hexdigest()
    completed=[]
    for label,vehicle,heading,weather in cases:
        report=run/f'{label}-report.json'
        if report.exists() and (result:=json.loads(report.read_text())).get('passed') and result.get('jarSha256')==jar:
            completed.append(label)
            continue
        snow.main(['--label',label,'--vehicle',vehicle,'--heading',heading,'--precipitation',weather])
        completed.append(label)
        (run/'matrix-report.json').write_text(json.dumps({'passed':completed,'total':len(cases)},indent=2))

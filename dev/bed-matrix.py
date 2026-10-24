"""Run camper bed cases inside the parent-owned native session's resource guard."""
import importlib.util
import os
from pathlib import Path
import sys

spec=importlib.util.spec_from_file_location('bed_tests',Path(__file__).with_name('bed-tests.py'))
bed=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bed)
cases=[
    ('cloud-side-e','Base.Trailer54FlyingCloud22','E','male',2),
    ('cloud-n','Base.Trailer54FlyingCloud22','N','male',1),
    ('cloud-s','Base.Trailer54FlyingCloud22','S','female',1),
    ('cloud-w','Base.Trailer54FlyingCloud22','W','male',1),
    ('airflyte-e','Base.Trailer61Airflyte','E','female',1),
    ('bambi-s','Base.Trailer61Bambi16','S','male',1),
    ('scamp13-n','Base.Trailer87Scamp13','N','female',1),
    ('scamp16-w','Base.Trailer87Scamp16','W','male',1),
]
for label,vehicle,heading,sex,index in cases:
    sys.argv=[__file__,'--run',os.environ['RVI_CAPTURE_RUN'],'--label',label,
              '--vehicle',vehicle,'--heading',heading,'--sex',sex,'--bed-index',str(index)]
    result=bed.main()
    if result: raise SystemExit(result)
print('NATIVE_BED_MATRIX_PASSED',flush=True)

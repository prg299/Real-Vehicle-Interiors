"""Owned native body-surface diagnostic controls; does not change a player save."""
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
for label,vehicle,heading,height in (
    ('ambulance-side','Base.VanAmbulance','S',2),
    ('passenger','Base.VanSeats','N',2),
    ('van','Base.Van','N',3),
    ('radio','Base.VanRadio','N',2),
):
    args=['--all-bodies','--only',vehicle,'--headings',heading,'--height-choice',str(height),
          '--body-lining-sweep','--white-passenger','--output-name','body-lining-'+label]
    result=subprocess.run([sys.executable,str(root/'dev/rear-door-tests.py'),*args],cwd=root)
    if result.returncode:raise SystemExit(result.returncode)

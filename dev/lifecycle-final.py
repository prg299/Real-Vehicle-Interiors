"""Cold-load and cross-family native lifecycle checks; parent owns the game/guard."""
from pathlib import Path
import argparse
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--skip-cold',action='store_true')
parser.add_argument('--only',action='append',choices=('Base.87fordF700box','Base.Van','Base.Trailer87Scamp13'))
parser.add_argument('--suffix',default='final');args=parser.parse_args()
checks=[] if args.skip_cold else [['--verify-source','interior-lifecycle-20261024-b','--output-name','cold-reload']]
checks += [['--vehicle',name,'--output-name',label+'-'+args.suffix] for name,label in (
    ('Base.87fordF700box','f700'),('Base.Van','van'),('Base.Trailer87Scamp13','camper')) if not args.only or name in args.only]
for arguments in checks:
    print('LIFECYCLE_START '+' '.join(arguments),flush=True)
    result=subprocess.run([sys.executable,str(root/'dev/interior-lifecycle-tests.py'),*arguments],cwd=root)
    if result.returncode:raise SystemExit(result.returncode)
    print('LIFECYCLE_PASS '+' '.join(arguments),flush=True)

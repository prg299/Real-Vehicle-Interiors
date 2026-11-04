"""Bounded two-client release driver; parent owns server/client lifetimes."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    for driver,folder in [('final-mp-native-movement','movement'),('final-workshop-mp-generator','generator')]:
        result=subprocess.run([sys.executable,str(ROOT/'dev'/(driver+'.py')),
                               '--session',str(args.session),'--output',str(args.output/folder)],check=False)
        if result.returncode:return result.returncode
    print('WORKSHOP_MP_RELEASE_INPUT_PASSED',flush=True);return 0

if __name__=='__main__':raise SystemExit(main())

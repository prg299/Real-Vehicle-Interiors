"""Focused SP release continuation after separately qualified movement checks."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    for name in ('workshop-generator-tests','workshop-appliance-tests'):
        spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        assert module.main()==0,name+' failed'
    print('NATIVE_PICKUP_APPLIANCE_RELEASE_PASSED',flush=True)

if __name__=='__main__':main()

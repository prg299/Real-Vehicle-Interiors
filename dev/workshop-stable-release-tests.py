"""Bounded stable-framework release checks in one parent-owned native session."""
import importlib.util
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    load('movement-release-tests').main()
    h=load('final-feature-tests')
    h.lua('local p=getPlayer();assert(not p:getVehicle());p:setX(10880.5);p:setY(10160.5);p:setLastX(p:getX());p:setLastY(p:getY());return true')
    deadline=time.monotonic()+20
    while not h.lua('local p=getPlayer();return getCell():getGridSquare(math.floor(p:getX()),math.floor(p:getY()),0)~=nil'):
        assert time.monotonic()<deadline,'disposable field did not stream before fixture spawn'
        time.sleep(.2)
    assert load('workshop-generator-tests').main()==0,'native stable generator checks failed'
    assert load('workshop-appliance-tests').main()==0,'native stable appliance checks failed'
    print('STABLE_WORKSHOP_RELEASE_INPUT_PASSED',flush=True)

if __name__=='__main__':main()

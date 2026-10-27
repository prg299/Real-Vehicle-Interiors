"""Fail-closed control checks for the shared fixture snapshot gate, no game I/O."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('protection',Path(__file__).with_name('vehicle-preservation.py'))
protection=importlib.util.module_from_spec(spec);spec.loader.exec_module(protection)
SNAPSHOT='local v=MELensLifecycle.vehicle;return fixtureSnapshot'
EXPECTED={'sqlId':3,'script':'Base.86fordE150','parts':{'cargo':{'items':[123],'capacity':120}}}
POSITION={'x':10778.5,'y':10094.67,'z':0}

class Endpoint:
    def __init__(self,loaded,actual=None):
        self.loaded=iter(loaded);self.actual=copy.deepcopy(EXPECTED if actual is None else actual)
        self.REPORT={};self.calls=[]
    def lua(self,code):
        self.calls.append(code)
        if code.startswith('local found;'):return next(self.loaded,False)
        if 'return {x=p:getX()' in code:return {'x':10,'y':20,'z':0}
        if 'return fixtureSnapshot' in code:return self.actual
        return True
    def check(self,condition,message):
        if not condition:raise AssertionError(message)

class PreservationGate(unittest.TestCase):
    def test_loaded_identity_requires_full_original_state(self):
        h=Endpoint([True]);self.assertEqual(protection.verify(h,EXPECTED,None,SNAPSHOT),EXPECTED)
        self.assertFalse(h.REPORT['fixturePreservation'][0]['relocatedToSavedLocation'])
    def test_changed_inventory_is_rejected(self):
        changed=copy.deepcopy(EXPECTED);changed['parts']['cargo']['items']=[124]
        h=Endpoint([True],changed)
        with self.assertRaisesRegex(AssertionError,'contents/state changed'):protection.verify(h,EXPECTED,None,SNAPSHOT)
        self.assertFalse(h.REPORT['fixturePreservation'][0]['inventoryUtilitiesAndInstalledIdsIdentical'])
    def test_missing_location_cannot_pass(self):
        h=Endpoint([False])
        with self.assertRaisesRegex(AssertionError,'Missing preserved location'):protection.verify(h,EXPECTED,None,SNAPSHOT)
        self.assertEqual(h.calls[-1],'MELensPreservationFixture=nil;return true')
    def test_reacquired_identity_compares_state_and_restores_position(self):
        h=Endpoint([False,True]);self.assertEqual(protection.verify(h,EXPECTED,POSITION,SNAPSHOT),EXPECTED)
        self.assertTrue(h.REPORT['fixturePreservation'][0]['relocatedToSavedLocation'])
        self.assertIn('p:setX(10)',h.calls[-2])
    def test_unavailable_identity_fails_and_restores_position(self):
        h=Endpoint([False,False])
        with self.assertRaisesRegex(AssertionError,'did not reload'):protection.verify(h,EXPECTED,POSITION,SNAPSHOT,timeout=-1)
        self.assertIn('p:setX(10)',h.calls[-2])
        self.assertNotIn('fixturePreservation',h.REPORT)

if __name__=='__main__':unittest.main()

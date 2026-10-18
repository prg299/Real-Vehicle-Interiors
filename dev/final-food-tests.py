"""Real Food cooking component probe; import performs no native calls.

Run against an owned SP game, or --server via the running MP admin channel.
The probe restores utility/clock state and removes only its tagged bacon items.
It proves native cooking, separately from actual input acceptance.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import traceback


ROOT=Path(__file__).resolve().parents[1]


def load_driver(name):
    spec=importlib.util.spec_from_file_location(name.replace("-","_"),Path(__file__).with_name(name+".py"))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"build/rv/final-food-tests")
    parser.add_argument("--endpoint",default=None)
    parser.add_argument("--server",action="store_true")
    parser.add_argument("--vehicle-id",type=int,default=None)
    args=parser.parse_args()
    h=load_driver("final-feature-tests")
    h.configure(args.output,args.endpoint)
    code=(ROOT/"dev/lua/native-food-cooking.lua").read_text(encoding="utf-8")
    if args.vehicle_id is not None:
        code=f"local MELensFoodProbeVehicleID={args.vehicle_id}\n"+code
    try:
        if args.server:
            interior=load_driver("final-mp-interior-tests")
            server=load_driver("final-mp-features").ServerEval(h)
            result=json.loads(server(interior.JSON_ENCODER+"local result=(function()\n"+code+"\nend)();return enc(result)"))
        else:
            result=h.lua(code)
        h.check(isinstance(result,dict) and result.get("passed"),"native Food cooking probe failed")
        h.REPORT.update(scope=__doc__.strip(),nativeInput=False,foodCooking=result)
        print(json.dumps(result,indent=2),flush=True)
        print(f"NATIVE_FOOD_COOKING_PASSED {h.write_report('passed')}",flush=True)
        return 0
    except Exception:
        error=traceback.format_exc()
        print(error,flush=True)
        print(f"NATIVE_FOOD_COOKING_FAILED {h.write_report('failed',error)}; parent-owned game/server left running",flush=True)
        return 1


if __name__=="__main__":
    raise SystemExit(main())

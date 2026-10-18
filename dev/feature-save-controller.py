"""Run the owned PS1 save/verify Lua block and persist its full JSON receipt."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import time

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run",required=True,type=Path)
    parser.add_argument("--mode",choices=("prepare","verify"),required=True)
    args=parser.parse_args()
    output=args.run.resolve()
    output.relative_to((ROOT/"build/rv").resolve())
    spec=importlib.util.spec_from_file_location("feature",ROOT/"dev/final-feature-tests.py")
    h=importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
    h.configure(output)
    script=ROOT/"dev"/("prepare-feature-save.ps1" if args.mode=="prepare" else "verify-feature-save.ps1")
    code=re.search(r"\$code = @'\r?\n(.*?)\r?\n'@",script.read_text(encoding="utf-8"),re.S).group(1)
    result=h.lua(code)
    (output/f"feature-save-{args.mode}.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    h.capture("features-saved" if args.mode=="prepare" else "features-reloaded")
    print(json.dumps({"mode":args.mode,"world":result.get("world"),"passed":True}),flush=True)
    if args.mode=="prepare":
        (output/"request.json").write_text(json.dumps({"action":"stop"}),encoding="utf-8")
    return 0

if __name__=="__main__": raise SystemExit(main())

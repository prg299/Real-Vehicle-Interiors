"""Execute real-engine utility component probes inside the parent-owned game."""
import importlib.util
import json
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]

def main():
    spec = importlib.util.spec_from_file_location("native_features", ROOT / "dev/final-feature-tests.py")
    feature = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(feature)
    feature.configure(ROOT / "build/rv/final-components-206")
    result = {}
    try:
        result = feature.lua((ROOT / "dev/lua/native-utility-components.lua").read_text(encoding="utf-8"))
        feature.check(result.get("passed"), "native component probes failed")
        print(json.dumps(result, indent=2), flush=True)
        status = 0
    except Exception:
        result = {"passed": False, "error": traceback.format_exc()}
        print(result["error"], flush=True)
        status = 1
    (feature.OUTPUT / "native-components.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return status

if __name__ == "__main__":
    raise SystemExit(main())

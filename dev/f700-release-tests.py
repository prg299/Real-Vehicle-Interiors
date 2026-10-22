"""Run the target native placement, generator and furniture/save checks under one owner."""
import importlib.util
from pathlib import Path


def main():
    for name in ('f700-tests', 'f700-fuel-tests', 'f700-seat-tests'):
        spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        status = module.main()
        if status:
            return status
    print('F700_RELEASE_NATIVE_PASSED', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

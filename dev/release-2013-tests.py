"""Run the focused 2.0.13 native suites inside workshop-capture's resource job."""
import importlib.util
from pathlib import Path
import sys


def run(name, arguments=()):
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    sys.argv = [str(path), *arguments]
    return module.main()


if __name__ == '__main__':
    if '--neat' in sys.argv:
        status = run('dashboard-style-tests', ['--neat', '--quick'])
    else:
        status = run('vision-tests')
        if status == 0: status = run('vision-coverage-tests')
        if status == 0: status = run('dashboard-style-tests', ['--resume', '--quick'])
    print('RELEASE_2013_NATIVE_PASSED' if status == 0 else 'RELEASE_2013_NATIVE_FAILED', flush=True)
    raise SystemExit(status)

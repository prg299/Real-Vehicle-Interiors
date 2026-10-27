"""Read-only parser/capture-count preflight; never import a native driver or launch PZ.

Supports exact-script photography and variant modes only. Full opening/isolation
matrices depend on live contracts and deliberately require their own scope review.
"""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'dev/native-body-tests.py'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight(arguments):
    tree = ast.parse(DRIVER.read_text('utf-8-sig'))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    # Reuse actual argparse declarations and pre-I/O semantic assertions. Stop
    # before catalogue(), native imports, session reads or any fixture calls.
    boundary = next(i for i, n in enumerate(main.body) if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'families' for t in n.targets))
    namespace = dict(argparse=argparse, Path=Path, math=math, json=json, __doc__=__doc__)
    previous = sys.argv
    try:
        sys.argv = [str(DRIVER), *arguments]
        # Reject file-reading diagnostics before executing actual assertions.
        parser_end = next(i for i, n in enumerate(main.body) if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'args' for t in n.targets))
        exec(compile(ast.Module(body=main.body[:parser_end+1], type_ignores=[]), str(DRIVER), 'exec'), namespace)
        args = namespace['args']
        unsupported = ('isolate', 'material_controls', 'empty_opening_controls', 'opening_part',
                       'opening_cut_y', 'panel_input', 'alias_controls', 'project_points',
                       'reuse_ledger', 'family', 'ki5_only', 'start', 'limit', 'fallback')
        assert not any(getattr(args, key) for key in unsupported), 'Unsupported count mode: use exact --only photography/variants without diagnostic extras or reuse'
        exec(compile(ast.Module(body=main.body[parser_end+1:boundary], type_ignores=[]), str(DRIVER), 'exec'), namespace)
    finally:
        sys.argv = previous
    assert args.variants, 'Use --photos-only or --variants; full opening matrices need live part contracts'
    assert args.only and len(set(args.only)) == len(args.only), 'Select distinct exact --only script IDs'
    headings = args.headings.split(',')
    assert len(set(headings)) == len(headings), 'Duplicate headings are not independent evidence'
    supported = {'Base.Trailer54FlyingCloud22'}
    for path in (ROOT/'tools-src/vehicles/specs').glob('*.json'):
        spec = json.loads(path.read_text('utf-8-sig'))
        if not spec.get('disabled'):
            supported.update(spec['vehicles'])
    assert set(args.only) <= supported, 'Unknown/disabled script IDs: '+str(set(args.only)-supported)
    detail = next(n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == 'detail_photos')
    heading_loop = next(n for n in ast.walk(main) if isinstance(n, ast.For)
                        and isinstance(n.target, ast.Name) and n.target.id == 'heading'
                        and isinstance(n.iter, ast.Name) and n.iter.id == 'case_headings')

    def relevant(node):
        return any(isinstance(n, ast.Call) and (isinstance(n.func, ast.Name)
                   and n.func.id in ('collect', 'detail_photos') or isinstance(n.func, ast.Attribute)
                   and isinstance(n.func.value, ast.Name) and n.func.value.id == 'h'
                   and n.func.attr == 'capture') for n in ast.walk(node))

    def count(statements):
        ledger = outside = 0
        for node in statements:
            if isinstance(node, ast.Continue):
                return ledger, outside, True
            if not relevant(node):
                continue
            stop = False
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Name) and call.func.id == 'collect':
                    a, b = 1, 0
                elif isinstance(call.func, ast.Name) and call.func.id == 'detail_photos':
                    a, b, _ = count(detail.body)
                elif isinstance(call.func, ast.Attribute) and call.func.attr == 'capture':
                    a, b = 0, 1
                else:
                    raise AssertionError('Capture call shape changed; review counter')
            elif isinstance(node, ast.If):
                # Only literal/arg boolean branches can be counted offline.
                allowed = (ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Name, ast.Load,
                           ast.Attribute, ast.Constant, ast.And, ast.Or, ast.Not)
                assert all(isinstance(n, allowed) for n in ast.walk(node.test)), 'Dynamic capture branch requires review'
                chosen = eval(compile(ast.Expression(node.test), '<capture-branch>', 'eval'),
                              {'__builtins__': {}}, {'args': args, 'alias_groups': []})
                a, b, stop = count(node.body if chosen else node.orelse)
            elif isinstance(node, ast.For):
                repetitions = len(ast.literal_eval(node.iter))
                a, b, stop = count(node.body)
                assert not stop and not node.orelse, 'Capture loop control changed'
                a, b = a*repetitions, b*repetitions
            elif isinstance(node, ast.Try):
                assert not node.handlers and not node.orelse, 'Conditional recovery captures need review'
                a, b, stop = count(node.body)
                c, d, final_stop = count(node.finalbody)
                assert not final_stop
                a, b = a+c, b+d
            elif isinstance(node, ast.With):
                a, b, stop = count(node.body)
            else:
                raise AssertionError('Capture structure changed at line '+str(node.lineno))
            ledger, outside = ledger+a, outside+b
            if stop:
                return ledger, outside, True
        return ledger, outside, False

    ledger, outside, _ = count(heading_loop.body)
    poses = len(args.only)*len(headings)
    return dict(scripts=args.only, headings=headings, poses=poses,
                ledgerFramesPerPose=ledger, otherCapturesPerPose=outside,
                expectedLedgerFrames=poses*ledger,
                expectedTotalCaptures=poses*(ledger+outside))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, help='Existing review JSON with phases; hashes verified when declared')
    parser.add_argument('--expect-total', type=int)
    parser.add_argument('arguments', nargs=argparse.REMAINDER, help='Actual body-driver arguments after --')
    args = parser.parse_args()
    assert not (args.plan and args.arguments), 'Choose plan or driver arguments'
    plan = json.loads(args.plan.read_text('utf-8-sig')) if args.plan else {}
    phases = plan.get('phases') if args.plan else [dict(name='dry-run', arguments=args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments)]
    assert isinstance(phases, list) and 1 <= len(phases) <= 8
    if args.plan and plan.get('driver') == 'dev/native-wall-sequence.py':
        sequence_path = ROOT/'build/rv'/plan['run']/'sequence.json'
        assert sequence_path.is_file(), 'Missing runtime sequence: '+str(sequence_path)
        assert json.loads(sequence_path.read_text('utf-8-sig')) == phases, 'Runtime sequence differs from reviewed plan'
    for name, wanted in plan.get('driverSha256', {}).items():
        assert digest(ROOT/'dev'/name) == wanted, 'Driver changed: '+name
    if 'manifest' in plan:
        manifest_path = args.plan.parent/plan['manifest']
        assert digest(manifest_path) == plan['manifestSha256'], 'Manifest changed'
        package = args.plan.parent/plan['frozenPackage']
        manifest = json.loads(manifest_path.read_text('utf-8-sig'))
        assert {str(p.relative_to(package)): digest(p) for p in package.rglob('*') if p.is_file()} == manifest, 'Frozen payload mismatch'
    results = []
    for phase in phases:
        assert phase.get('driver', 'native-body-tests.py') == 'native-body-tests.py', 'Non-body driver needs separate preflight'
        assert '--output-name' not in phase['arguments'] and '--keep-open' not in phase['arguments'], 'Sequence owns output/lifetime flags'
        results.append(dict(name=phase['name'], **preflight(phase['arguments'])))
    total = sum(row['expectedTotalCaptures'] for row in results)
    expected = args.expect_total if args.expect_total is not None else plan.get('expectedTotalCaptures', plan.get('expectedVehicleOriginals'))
    report = dict(scope='Read-only preflight; no native/visual acceptance', driverSha256=digest(DRIVER), phases=results,
                  expectedTotalCaptures=total, declaredTotal=expected,
                  countMatches=expected is None or total == expected)
    print(json.dumps(report, indent=2))
    return 0 if report['countMatches'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

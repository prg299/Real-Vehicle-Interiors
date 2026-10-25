"""Game-independent repository checks; native gameplay and engine tests run separately."""
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', 'build', '.tools', '.local', '.cache', '__pycache__'}
errors = []



def require(condition, message):
    if not condition:
        errors.append(message)


def files():
    if (ROOT / '.git').exists():
        result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                                cwd=ROOT, check=True, capture_output=True)
        return sorted({ROOT / value.decode('utf-8') for value in result.stdout.split(b'\0') if value})
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and not EXCLUDED.intersection(p.relative_to(ROOT).parts))


paths = files()
required = ['README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
            'scripts/build.ps1', 'scripts/prepare-shaders.py', '.github/workflows/checks.yml']
for path in required:
    require((ROOT / path).is_file(), f'Missing {path}')
require('MIT License' in (ROOT / 'LICENSE').read_text('utf-8'), 'Expected MIT license')
for relative in ('mod/RealVehicleInteriors/mod.info', 'mod/RealVehicleInteriors/42.21/mod.info'):
    info = (ROOT / relative).read_text('utf-8')
    dependencies = re.search(r'^require=(.*)$', info, re.M)
    require(dependencies and dependencies[1].strip() == '\\ZombieBuddy',
            f'{relative}: ZombieBuddy must be the only hard dependency')

seen = set()
for p in paths:
    relative = p.relative_to(ROOT).as_posix()
    require(relative.casefold() not in seen, f'Case-colliding path: {relative}')
    seen.add(relative.casefold())
    require(p.stat().st_size < 25 * 1024 * 1024, f'Oversized source file: {relative}')
    require(p.suffix.lower() not in {'.jar', '.class', '.dll', '.exe', '.der', '.pem', '.key', '.p12', '.db'},
            f'Binary/dependency/private file cannot be published: {relative}')
    try:
        text = p.read_text('utf-8-sig')
    except UnicodeDecodeError:
        continue
    if p.suffix == '.json':
        try:
            json.loads(text)
        except ValueError as error:
            errors.append(f'{relative}: {error}')
    if p.suffix == '.py':
        try:
            ast.parse(text, filename=relative)
        except SyntaxError as error:
            errors.append(str(error))
    for pattern in (r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                    r'gh[pousr]_[A-Za-z0-9]{30,}', r'github_pat_[A-Za-z0-9_]{40,}'):
        require(not re.search(pattern, text), f'Potential credential in {relative}; redact before publication')
    # Root guides and current architecture/setup documents are authoritative.
    if p.suffix == '.md' and (p.parent == ROOT or p.name in {'DEVELOPMENT.md', 'ARCHITECTURE.md', 'COMPATIBILITY.md', 'ANIMALS.md'}):
        for link in re.findall(r'\]\(([^)]+)\)', text):
            target = link.split('#', 1)[0].strip('<>')
            if not target or re.match(r'[a-z]+:', target):
                continue
            require((p.parent / unquote(target)).exists(), f'{relative}: broken local link {target}')

for path in (ROOT / 'tools-src/shaders').glob('*.json'):
    recipe = json.loads(path.read_text('utf-8'))
    require(recipe['schema'] == 1 and recipe['base'] == Path(recipe['base']).name
            and recipe['output'] == Path(recipe['output']).name and len(recipe['outputSha256']) == 64,
            f'Invalid shader recipe: {path.name}')


if errors:
    print('\n'.join(errors), file=sys.stderr)
    sys.exit(1)
print(f'Repository checks passed: {len(paths)} files; JSON, Python syntax, current doc links, credential patterns and shader recipes')
print('Native/gameplay/input/multiplayer/visual acceptance is not established by this check.')

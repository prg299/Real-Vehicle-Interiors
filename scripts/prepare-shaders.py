"""Reconstruct cutaway shaders from authored edits and a local Build 42.21 install."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(game_root, output):
    prepared = []
    for path in sorted((ROOT / 'tools-src/shaders').glob('*.json')):
        recipe = json.loads(path.read_text('utf-8'))
        base_path = game_root / 'media/shaders' / recipe['base']
        base = base_path.read_bytes()
        if hashlib.sha256(base).hexdigest() != recipe['baseSha256']:
            raise ValueError(f'{base_path.name}: game shader changed; review and regenerate its recipe for this game version')
        lines = base.splitlines(keepends=True)
        chunks = []
        for operation in recipe['operations']:
            if 'copy' in operation:
                start, end = operation['copy']
                chunks.append(b''.join(lines[start:end]))
            elif 'insertFile' in operation:
                source = (path.parent / operation['insertFile']).resolve()
                if not source.is_relative_to(path.parent.resolve()):
                    raise ValueError('Shader insertion must stay in the recipe directory')
                chunks.append(source.read_bytes())
            else:
                chunks.append(operation['insert'].encode('utf-8'))
        result = b''.join(chunks)
        if hashlib.sha256(result).hexdigest() != recipe['outputSha256']:
            raise ValueError(f'{path.name}: reconstructed shader hash differs')
        prepared.append((recipe['output'], result))
    output.mkdir(parents=True, exist_ok=True)
    for name, result in prepared:
        (output / name).write_bytes(result)
    print(f'Prepared {len(prepared)} shaders; exact recipe output hashes match')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.game_root, args.output)

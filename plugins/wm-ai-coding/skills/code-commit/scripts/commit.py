"""Preview or execute one scoped local commit; authorization is host asserted."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def git(repo: Path, *args: str, optional: bool = False) -> bytes:
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=60)
    if result.returncode and not optional:
        raise ValueError(result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout


def paths(raw: bytes) -> set[str]:
    return {p for p in raw.decode('utf-8').split('\0') if p}


def snapshot(repo: Path) -> str:
    value = hashlib.sha256()
    for args in [('diff', '--binary', 'HEAD'), ('diff', '--cached', '--binary'),
                 ('status', '--porcelain=v1', '-z')]:
        value.update(git(repo, *args))
    for name in sorted(paths(git(repo, 'ls-files', '--others', '--exclude-standard', '-z'))):
        path = repo / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'unsupported untracked path: {name}')
        value.update(name.encode()); value.update(b'\0'); value.update(path.read_bytes())
    return value.hexdigest()


def perform(args: argparse.Namespace) -> dict:
    repo = args.repo.resolve()
    actual = Path(git(repo, 'rev-parse', '--show-toplevel').decode('utf-8').strip()).resolve()
    if actual != repo:
        raise ValueError('--repo must identify the Git worktree root')
    if args.execute and not (args.authorization_reference or '').strip():
        raise ValueError('execution requires an existing authorization reference')
    if not args.message.strip() or not args.check:
        raise ValueError('a commit message and an exact check argv are required')
    head = git(repo, 'rev-parse', '--verify', 'HEAD').strip()
    selected = set()
    for name in args.files:
        path = (repo / name).resolve()
        if not path.is_relative_to(repo) or path == repo:
            raise ValueError('selected paths must stay inside the repository')
        relative = path.relative_to(repo).as_posix()
        if relative.split('/')[0] == '.git' or path.is_dir() or (repo / name).is_symlink():
            raise ValueError(f'only explicit regular file paths are supported: {name}')
        literal = ':(literal)' + relative
        if not path.is_file() and not git(repo, 'ls-files', '-z', '--', literal):
            raise ValueError(f'selected file is missing and untracked: {name}')
        selected.add(relative)
    staged = paths(git(repo, 'diff', '--cached', '--name-only', '-z', '--no-renames'))
    if staged - selected:
        raise ValueError('unrelated staged paths: ' + ', '.join(sorted(staged - selected)))
    before = snapshot(repo)
    check = subprocess.run(args.check, cwd=repo, capture_output=True, timeout=300)
    if check.returncode:
        raise ValueError(f'required check failed with exit code {check.returncode}')
    if snapshot(repo) != before or git(repo, 'rev-parse', 'HEAD').strip() != head:
        raise ValueError('check changed the repository; review changes and run again')
    result = {'status': 'preview', 'files': sorted(selected), 'message': args.message,
              'checks': 'passed', 'authorization': 'host asserted, not authenticated'}
    if not args.execute:
        return result
    git(repo, 'add', '--', *[':(literal)' + p for p in sorted(selected)])
    staged = paths(git(repo, 'diff', '--cached', '--name-only', '-z', '--no-renames'))
    if not staged or staged - selected:
        raise ValueError('staged scope changed or contains no changes; inspect the index')
    git(repo, 'commit', '-m', args.message)
    commit = git(repo, 'rev-parse', 'HEAD').decode('ascii').strip()
    changed = paths(git(repo, 'diff', '--name-only', '-z', '--no-renames', head.decode('ascii'), commit))
    result.update(status='scope_exceeded' if changed - selected else 'committed',
                  commit=commit, files=sorted(changed))
    if changed - selected:
        result['error'] = 'Git hooks expanded the commit scope; commit retained for review, no reset performed'
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--files', nargs='+', required=True)
    parser.add_argument('--message', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization-reference')
    parser.add_argument('--check', nargs=argparse.REMAINDER, required=True)
    try:
        result = perform(parser.parse_args())
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result['status'] == 'scope_exceeded' else 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

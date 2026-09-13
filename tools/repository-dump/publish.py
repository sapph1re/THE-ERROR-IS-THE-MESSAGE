#!/usr/bin/env python3
"""Publish an existing archive in bounded Git pushes. Run only inside the archive branch."""
import json
from pathlib import Path
import subprocess

BATCH = 256 * 1024**2


def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True, text=True).stdout


def checkpoint(paths, message):
    for start in range(0, len(paths), 100):
        git('add', '--', *paths[start:start + 100])
    if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode:
        git('commit', '-m', message)
        git('push', 'origin', 'HEAD:repository-archive')


def publish():
    if git('branch', '--show-current').strip() != 'repository-archive':
        raise ValueError('Refusing to publish outside repository-archive branch')
    path = Path('archive/manifest.json')
    final_manifest = path.read_bytes()
    metadata = json.loads(final_manifest)
    path.write_text(json.dumps({'complete': False, 'publishing': True,
                                'repository': metadata['repository']}) + '\n')
    checkpoint([str(path)], 'Mark archive publication in progress')
    # Remove deleted paths without staging every new binary in one huge commit.
    removed = git('ls-files', '--deleted', '-z', '--', 'archive').split('\0')
    removed = [p for p in removed if p]
    if removed:
        checkpoint(removed, 'Remove obsolete archive files')
    batch, size = [], 0
    for f in sorted(Path('archive').rglob('*')):
        if not f.is_file() or f == path:
            continue
        if f.is_symlink():
            raise ValueError('Archive must not contain symlinks')
        file_size = f.stat().st_size
        if file_size > 50 * 1024**2:
            raise ValueError('Unexpected oversized archive part')
        if batch and size + file_size > BATCH:
            checkpoint(batch, 'Save archive files')
            batch, size = [], 0
        batch.append(str(f))
        size += file_size
    if batch:
        checkpoint(batch, 'Save archive files')
    path.write_bytes(final_manifest)
    checkpoint([str(path)], 'Finalize archive publication manifest')


if __name__ == '__main__':
    publish()

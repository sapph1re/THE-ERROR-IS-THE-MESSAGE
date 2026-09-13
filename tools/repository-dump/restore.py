#!/usr/bin/env python3
"""Reassemble archived assets and verify every part and full-file checksum."""
import argparse
import hashlib
import json
from pathlib import Path


def restore(archive, output):
    archive, output = Path(archive).resolve(), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for item in json.loads((archive / 'assets-manifest.json').read_text()):
        if item['status'] != 'complete':
            raise ValueError('Archive has failed assets; inspect manifest before restoring')
        key = hashlib.sha256(item['source_url'].encode()).hexdigest()
        name = Path(item.get('name') or key).name
        dest = output / (key[:16] + '-' + name)
        digest, total = hashlib.sha256(), 0
        with dest.open('xb') as target:
            for part in item['parts']:
                source = (archive / part['path']).resolve()
                if not source.is_relative_to(archive):
                    raise ValueError('Part path escapes archive')
                data = source.read_bytes()
                if len(data) != part['bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
                    raise ValueError('Corrupt archive part: ' + part['path'])
                target.write(data)
                digest.update(data)
                total += len(data)
        if total != item['bytes'] or digest.hexdigest() != item['sha256']:
            raise ValueError('Reconstructed asset does not match manifest')
    print('Restored and verified all assets')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive')
    p.add_argument('output')
    a = p.parse_args()
    restore(a.archive, a.output)

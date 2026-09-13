#!/usr/bin/env python3
"""Reassemble archived assets and verify every part and full-file checksum."""
import argparse
import hashlib
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse, unquote


def asset_name(item):
    key = hashlib.sha256(item['source_url'].encode()).hexdigest()
    candidate = item.get('name') or Path(unquote(urlparse(item['source_url']).path)).name
    candidate = re.sub(r'[^A-Za-z0-9._ -]', '_', candidate).strip('. ')[:150]
    if not candidate:
        candidate = key
    if not Path(candidate).suffix:
        kind = (item.get('content_type') or '').split(';')[0].strip()
        candidate += mimetypes.guess_extension(kind) or '.bin'
    return key[:16] + '-' + candidate


def restore(archive, output):
    archive, output = Path(archive).resolve(), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for item in json.loads((archive / 'assets-manifest.json').read_text()):
        if item['status'] != 'complete':
            raise ValueError('Archive has failed assets; inspect manifest before restoring')
        key = hashlib.sha256(item['source_url'].encode()).hexdigest()
        dest = output / asset_name(item)
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

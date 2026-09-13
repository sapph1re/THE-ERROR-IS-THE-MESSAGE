#!/usr/bin/env python3
"""Retry failed asset downloads without rereading successful snapshot metadata."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from dump import Exporter


def retry(archive, max_mib=8192):
    archive = Path(archive)
    manifest = json.loads((archive / 'manifest.json').read_text())
    if any(f.get('stage') == 'metadata' for f in manifest['failures']):
        raise ValueError('Metadata is incomplete; create a new full export')
    assets = json.loads((archive / 'assets-manifest.json').read_text())
    e = Exporter(manifest['repository'], archive,
                 os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN'), max_mib * 1024**2)
    e.bytes = sum(p.stat().st_size for p in (archive / 'assets').glob('*/*') if p.is_file())
    for item in assets:
        if item['status'] != 'complete':
            e.download(item['source_url'], binary='/releases/assets/' in item['source_url'],
                       label=item.get('name'), expected_size=item.get('expected_bytes'))
    replacements = {a['source_url']: a for a in e.assets}
    assets = [replacements.get(a['source_url'], a) for a in assets]
    failures = [{'source_url': a['source_url'], 'error': a.get('error'),
                 'http_status': a.get('http_status')} for a in assets if a['status'] != 'complete']
    manifest.update(complete=not failures, failures=failures,
                    downloaded_bytes=sum(a['bytes'] for a in assets),
                    last_asset_retry_at=datetime.now(timezone.utc).isoformat())
    e.save('assets-manifest.json', assets)
    e.save('manifest.json', manifest)
    index = archive / 'README.md'
    if not failures and index.exists():
        index.write_text(index.read_text().replace('Status: INCOMPLETE: see manifest.json',
                                                  'Status: COMPLETE for the documented API scope'))
    print(json.dumps({'complete': manifest['complete'], 'retried': len(replacements),
                      'remaining_failures': failures, 'downloaded_bytes': manifest['downloaded_bytes']}))
    return 0 if not failures else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive')
    p.add_argument('--max-download-mib', type=int, default=8192)
    a = p.parse_args()
    if a.max_download_mib <= 0:
        p.error('--max-download-mib must be positive')
    raise SystemExit(retry(a.archive, a.max_download_mib))

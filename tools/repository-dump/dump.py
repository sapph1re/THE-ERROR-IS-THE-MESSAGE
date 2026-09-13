#!/usr/bin/env python3
"""Read-only GitHub archive exporter. Standard library only; Python 3.10+."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

API = "https://api.github.com"
GITHUB_S3 = {'github-cloud.s3.amazonaws.com',
             'github-production-user-asset-6210df.s3.amazonaws.com',
             'github-production-repository-file-5c1aeb.s3.amazonaws.com',
             'github-production-release-asset-2e65be.s3.amazonaws.com'}
CHUNK = 40 * 1024 * 1024  # Stay below GitHub's per-file Git limit.
URL_RE = re.compile(r'https://[^\s<>\"\x27]+')


def allowed(url):
    p = urlparse(url)
    return (p.scheme == 'https' and p.port in (None, 443)
            and not p.username and not p.password
            and (p.hostname in {'github.com', 'api.github.com', 'codeload.github.com'} | GITHUB_S3
                 or (p.hostname or '').endswith('.githubusercontent.com')))


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError('Refused non-GitHub download redirect')
        nxt = super().redirect_request(req, fp, code, msg, headers, newurl)
        if urlparse(newurl).hostname != urlparse(req.full_url).hostname:
            nxt.remove_header('Authorization')
        return nxt


def attachment_urls(value):
    found = set()
    if isinstance(value, dict):
        for v in value.values():
            found.update(attachment_urls(v))
    elif isinstance(value, list):
        for v in value:
            found.update(attachment_urls(v))
    elif isinstance(value, str):
        for u in URL_RE.findall(value):
            u = u.rstrip('.,;:!?)]}`')
            p = urlparse(u)
            asset_path = re.fullmatch(r'/user-attachments/assets/[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', p.path)
            file_path = re.match(r'^/user-attachments/files/[0-9]+/', p.path)
            if ((p.hostname == 'github.com' and (asset_path or file_path))
                    or p.hostname == 'user-images.githubusercontent.com'):
                found.add(u)
    return found


class Exporter:
    def __init__(self, repo, out, token=None, max_bytes=2 * 1024**3):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('Expected owner/repository')
        self.repo, self.out, self.token = repo, Path(out), token
        self.max_bytes, self.bytes = max_bytes, 0
        self.byte_lock = threading.Lock()
        self.opener = build_opener(SafeRedirect())
        self.urls, self.assets, self.failures, self.counts = set(), [], [], {}

    def request(self, url, binary=False):
        if not allowed(url):
            raise ValueError('Refused non-GitHub URL')
        headers = {'User-Agent': 'repository-dump/1.0',
                   'Accept': 'application/octet-stream' if binary else 'application/vnd.github+json'}
        if urlparse(url).hostname == 'api.github.com':
            headers['X-GitHub-Api-Version'] = '2022-11-28'
            if self.token:
                headers['Authorization'] = 'Bearer ' + self.token
        for attempt in range(3):
            try:
                return self.opener.open(Request(url, headers=headers), timeout=90)
            except HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
                time.sleep(min(10, 2**attempt))

    def api(self, suffix):
        with self.request(API + '/repos/' + self.repo + suffix) as response:
            return json.load(response)

    def pages(self, suffix):
        result, page = [], 1
        while True:
            sep = '&' if '?' in suffix else '?'
            batch = self.api(f'{suffix}{sep}per_page=100&page={page}')
            if not isinstance(batch, list):
                raise ValueError('Expected paginated array')
            result.extend(batch)
            if len(batch) < 100:
                return result
            page += 1

    def save(self, name, data):
        path = self.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
        self.urls.update(attachment_urls(data))

    def readable_issue(self, number):
        directory = self.out / 'issues' / str(number)
        issue = json.loads((directory / 'issue.json').read_text())
        lines = [f"# #{number}: {issue['title']}", '', issue['html_url'], '',
                 f"State: {issue['state']}; created: {issue['created_at']}", '', issue.get('body') or '', '']
        for filename, heading in [('comments.json', 'Conversation'), ('reviews.json', 'Reviews'),
                                  ('review-comments.json', 'Inline review comments')]:
            path = directory / filename
            if not path.exists():
                continue
            lines += ['## ' + heading, '']
            for comment in json.loads(path.read_text()):
                user = (comment.get('user') or {}).get('login', '[deleted]')
                lines += [f"### {user} ({comment.get('created_at') or comment.get('submitted_at') or ''})", '',
                          comment.get('html_url', ''), '']
                if comment.get('path'):
                    lines += [f"File: {comment['path']}; line: {comment.get('line')}; reply to: {comment.get('in_reply_to_id')}", '']
                lines += [comment.get('body') or '', '']
        (directory / 'README.md').write_text('\n'.join(lines))

    def collect(self):
        self.save('repository.json', self.api(''))
        issues = self.pages('/issues?state=all&sort=created&direction=asc')
        self.save('issues-index.json', issues)
        for issue in issues:
            n = issue['number']
            prefix = f'issues/{n}'
            self.save(prefix + '/issue.json', self.api(f'/issues/{n}'))
            self.save(prefix + '/comments.json', self.pages(f'/issues/{n}/comments'))
            self.save(prefix + '/events.json', self.pages(f'/issues/{n}/events'))
            if 'pull_request' in issue:
                self.save(prefix + '/pull.json', self.api(f'/pulls/{n}'))
                self.save(prefix + '/reviews.json', self.pages(f'/pulls/{n}/reviews'))
                self.save(prefix + '/review-comments.json', self.pages(f'/pulls/{n}/comments'))
                self.save(prefix + '/commits.json', self.pages(f'/pulls/{n}/commits'))
            self.readable_issue(n)
        releases = self.pages('/releases')
        self.save('releases.json', releases)
        for release in releases:
            for format_name in ('tarball_url', 'zipball_url'):
                if release.get(format_name):
                    self.download(release[format_name], label=f"{release['tag_name']}-{format_name}")
            assets = self.pages(f"/releases/{release['id']}/assets")
            self.save(f"releases/{release['id']}/assets.json", assets)
            for a in assets:
                self.download(a['url'], binary=True, expected_size=a['size'], label=a['name'])
        self.save('tags.json', self.pages('/tags'))
        self.counts = {'issues': sum('pull_request' not in i for i in issues),
                       'pull_requests': sum('pull_request' in i for i in issues),
                       'releases': len(releases)}
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(self.download, sorted(self.urls)))
        self.assets.sort(key=lambda a: a['source_url'])

    def download(self, url, binary=False, expected_size=None, label=None):
        key = hashlib.sha256(url.encode()).hexdigest()
        directory = self.out / 'assets' / key
        directory.mkdir(parents=True, exist_ok=True)
        record = {'source_url': url, 'name': label, 'expected_bytes': expected_size, 'parts': [], 'bytes': 0}
        digest = hashlib.sha256()
        try:
            with self.request(url, binary=binary) as response:
                record['content_type'] = response.headers.get('Content-Type')
                declared = response.headers.get('Content-Length')
                if declared and self.bytes + int(declared) > self.max_bytes:
                    raise ValueError('Total download limit exceeded; raise --max-download-mib and rerun')
                while True:
                    block = response.read(min(CHUNK, self.max_bytes - self.bytes + 1))
                    if not block:
                        break
                    with self.byte_lock:
                        if self.bytes + len(block) > self.max_bytes:
                            raise ValueError('Total download limit exceeded')
                        self.bytes += len(block)
                    file = directory / f"part-{len(record['parts']):04d}"
                    file.write_bytes(block)
                    record['bytes'] += len(block)
                    digest.update(block)
                    record['parts'].append({'path': str(file.relative_to(self.out)),
                                            'bytes': len(block),
                                            'sha256': hashlib.sha256(block).hexdigest()})
                if declared and record['bytes'] != int(declared):
                    raise ValueError('Truncated response')
                if expected_size is not None and expected_size != record['bytes']:
                    raise ValueError('Release asset size differs from API metadata')
            record.update(status='complete', sha256=digest.hexdigest())
        except Exception as e:
            # Do not persist exception URLs: redirected URLs can contain signed query strings.
            record.update(status='failed', error=type(e).__name__)
            if isinstance(e, HTTPError):
                record['http_status'] = e.code
            self.failures.append({'source_url': url, 'error': type(e).__name__})
        self.assets.append(record)

    def run(self):
        if self.out.exists() and any(self.out.iterdir()):
            raise ValueError('Output must be empty; preserve previous archive in another directory')
        self.out.mkdir(parents=True, exist_ok=True)
        started = datetime.now(timezone.utc).isoformat()
        try:
            self.collect()
        except Exception as e:
            self.failures.append({'stage': 'metadata', 'error': type(e).__name__})
            if isinstance(e, HTTPError):
                self.failures[-1]['http_status'] = e.code
        self.save('assets-manifest.json', self.assets)
        result = {'repository': self.repo, 'started_at': started,
                  'finished_at': datetime.now(timezone.utc).isoformat(),
                  'complete': not self.failures, 'counts': self.counts,
                  'downloaded_bytes': self.bytes, 'failures': self.failures,
                  'scope': 'Issues, PRs and review comments, releases, tags, GitHub-hosted uploaded attachments. Not a Git mirror or deleted content recovery.'}
        self.save('manifest.json', result)
        lines = [f'# Archive of {self.repo}', '',
                 'Status: ' + ('COMPLETE for the documented API scope' if result['complete'] else 'INCOMPLETE: see manifest.json'),
                 '', '[Run manifest](manifest.json) | [Issues and PRs](issues-index.json) | [Releases](releases.json) | [Tags](tags.json) | [Assets](assets-manifest.json)', '',
                 'Raw JSON retains original Markdown, timestamps, authors and source URLs.',
                 'Attachments are stored as numbered parts. Use restore.py to reconstruct and verify them.',
                 'This is a non-atomic snapshot. Rerun after activity has stopped for a stable archive.', '']
        index = self.out / 'issues-index.json'
        if index.exists():
            for i in json.loads(index.read_text()):
                title = i['title'].replace('\n', ' ').replace('[', '\\[').replace(']', '\\]')
                lines.append(f"- #{i['number']} [{title}](issues/{i['number']}/README.md) ({i['state']})")
        (self.out / 'README.md').write_text('\n'.join(lines) + '\n')
        print(json.dumps(result))
        return 0 if result['complete'] else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('repository')
    p.add_argument('--output', default='archive')
    p.add_argument('--max-download-mib', type=int, default=2048)
    a = p.parse_args()
    if a.max_download_mib <= 0:
        p.error('--max-download-mib must be positive')
    raise SystemExit(Exporter(a.repository, a.output, os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN'), a.max_download_mib * 1024**2).run())

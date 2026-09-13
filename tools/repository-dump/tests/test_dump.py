import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request

import dump
from restore import restore


class Response(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {'Content-Length': str(len(data)), 'Content-Type': 'application/octet-stream'}


class Tests(unittest.TestCase):
    def test_pagination_over_one_hundred(self):
        e = dump.Exporter('a/b', '/unused')
        with patch.object(e, 'api', side_effect=[list(range(100)), [100]]) as api:
            self.assertEqual(len(e.pages('/issues?state=all')), 101)
            self.assertIn('&per_page=100&page=2', api.call_args.args[0])

    def test_uploaded_markdown_and_html(self):
        u = 'https://github.com/user-attachments/assets/abc'
        self.assertEqual(dump.attachment_urls({'body': f'![image]({u}) <img src="{u}">'}), {u})
        self.assertEqual(dump.attachment_urls('https://evil.test/f https://github.com/a/b'), set())

    def test_redirect_strips_auth(self):
        req = Request('https://api.github.com/repos/a/b/releases/assets/1', headers={'Authorization': 'Bearer sentinel'})
        nxt = dump.SafeRedirect().redirect_request(req, None, 302, '', {}, 'https://objects.githubusercontent.com/file')
        self.assertFalse(nxt.has_header('Authorization'))
        self.assertTrue(dump.allowed('https://github-production-user-asset-6210df.s3.amazonaws.com/file'))
        self.assertFalse(dump.allowed('https://attacker.s3.amazonaws.com/file'))
        with self.assertRaises(ValueError):
            dump.SafeRedirect().redirect_request(req, None, 302, '', {}, 'http://127.0.0.1/private')

    def test_chunks_restore_and_corruption(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / 'archive'
            e = dump.Exporter('a/b', out)
            data = b'1234567890'
            with patch.object(e, 'request', return_value=Response(data)), patch.object(dump, 'CHUNK', 4):
                e.download('https://github.com/user-attachments/assets/abc')
            self.assertEqual([p['bytes'] for p in e.assets[0]['parts']], [4, 4, 2])
            e.save('assets-manifest.json', e.assets)
            with contextlib.redirect_stdout(io.StringIO()):
                restore(out, Path(root) / 'restored')
            self.assertEqual(next((Path(root) / 'restored').iterdir()).read_bytes(), data)
            (out / e.assets[0]['parts'][0]['path']).write_bytes(b'bad!')
            with self.assertRaises(ValueError):
                restore(out, Path(root) / 'corrupt')

    def test_size_limit_is_failure(self):
        with tempfile.TemporaryDirectory() as root:
            e = dump.Exporter('a/b', root, max_bytes=4)
            with patch.object(e, 'request', return_value=Response(b'12345')):
                e.download('https://github.com/user-attachments/assets/abc')
            self.assertEqual(e.assets[0]['status'], 'failed')
            self.assertEqual(e.bytes, 0)

    def test_metadata_failure_is_nonzero_and_manifest_survives(self):
        with tempfile.TemporaryDirectory() as root:
            e = dump.Exporter('a/b', Path(root) / 'archive')
            with patch.object(e, 'collect', side_effect=RuntimeError('secret should not be serialized')), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(e.run(), 1)
            manifest = (e.out / 'manifest.json').read_text()
            self.assertFalse(json.loads(manifest)['complete'])
            self.assertNotIn('secret', manifest)

    def test_review_and_release_endpoints_are_included(self):
        with tempfile.TemporaryDirectory() as root:
            e = dump.Exporter('a/b', root)
            calls = []
            def pages(path):
                calls.append(path)
                return [{'number': 1, 'pull_request': {}}] if path.startswith('/issues?') else []
            with patch.object(e, 'api', return_value={}), patch.object(e, 'pages', side_effect=pages), patch.object(e, 'readable_issue'):
                e.collect()
            for path in ['/issues/1/comments', '/pulls/1/reviews', '/pulls/1/review-comments']:
                if path.endswith('review-comments'):
                    path = '/pulls/1/comments'
                self.assertIn(path, calls)
            self.assertIn('/tags', calls)


if __name__ == '__main__':
    unittest.main()

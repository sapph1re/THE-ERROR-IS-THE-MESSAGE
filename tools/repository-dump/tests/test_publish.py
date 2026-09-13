import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import publish


class Publication(unittest.TestCase):
    def test_batched_push_and_complete_manifest_last(self):
        previous = Path.cwd()
        def git(*args):
            return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', *args], stderr=subprocess.DEVNULL, text=True).strip()
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            try:
                os.chdir(root)
                git('init', '--bare', 'remote.git')
                git('init', 'local')
                os.chdir(root / 'local')
                git('config', 'user.name', 'Local test')
                git('config', 'user.email', 'test@example.invalid')
                git('config', 'core.hooksPath', '/dev/null')
                git('remote', 'add', 'origin', str(root / 'remote.git'))
                git('checkout', '-b', 'repository-archive')
                Path('initial.txt').write_text('fixture')
                git('add', 'initial.txt')
                git('commit', '-m', 'Fixture')
                Path('archive').mkdir()
                manifest = {'repository': 'fixture/test', 'complete': True}
                Path('archive/manifest.json').write_text(json.dumps(manifest))
                for i in range(3):
                    Path(f'archive/part-{i}').write_bytes(b'1234')
                with patch.object(publish, 'BATCH', 5):
                    publish.publish()
                latest = git('--git-dir', str(root / 'remote.git'), 'show', 'repository-archive:archive/manifest.json')
                self.assertTrue(json.loads(latest)['complete'])
                self.assertEqual(git('log', '-1', '--format=%s'), 'Finalize archive publication manifest')
                Path('archive/part-0').unlink()
                publish.publish()
                self.assertNotIn('archive/part-0', git('ls-tree', '-r', '--name-only', 'HEAD'))
            finally:
                os.chdir(previous)

import unittest
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from package_linux import START_SCRIPT, validate_inputs, validate_release


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.values = dict(request_id='a'*32, installer_name='WorldOverhaul-0.1.4-win-x64.msi',
                           release_tag='launcher-v0.1.4', release_marker='release-20260911T200000Z-abcdef01',
                           msi_sha256='b'*64, helper_sha256='c'*64)

    def test_versioned_bundle_and_draft(self):
        self.assertEqual(validate_inputs(self.values), 'WorldOverhaul-0.1.4-linux.run')
        validate_release(dict(isDraft=True, body='Notes\n<!-- '+self.values['release_marker']+' -->'), self.values)

    def test_rejects_path_injection_and_mismatched_inputs(self):
        for key, value in [('installer_name', '../x.msi'), ('release_tag', 'launcher-v0.1.5'),
                           ('request_id', '$(echo evil)'), ('msi_sha256', 'abc'), ('release_marker', '--flag')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_inputs(dict(self.values, **{key: value}))

    def test_never_packages_published_or_unowned_release(self):
        for release in (dict(isDraft=False, body='<!-- '+self.values['release_marker']+' -->'),
                        dict(isDraft=True, body='Someone else')):
            with self.subTest(release=release), self.assertRaises(ValueError):
                validate_release(release, self.values)

    def test_isolated_validation_tag(self):
        self.values['release_tag'] = 'linux-package-test-' + 'd'*32
        self.assertEqual(validate_inputs(self.values), 'WorldOverhaul-0.1.4-linux.run')

    def test_accepts_the_distinct_updater_bootstrap_release(self):
        self.values['release_tag'] = 'launcher-updater-v0.1.4'
        self.values['release_marker'] = 'updater-bootstrap-20260927'
        self.assertEqual(validate_inputs(self.values), 'WorldOverhaul-0.1.4-linux.run')
        validate_release(dict(isDraft=True, body='Notes\n<!-- updater-bootstrap-20260927 -->'), self.values)

    def test_rejects_mismatched_updater_tag_and_unapproved_markers(self):
        for tag in ('launcher-updater-v0.1.5', 'launcher-updater-v0.1.40', 'launcher-updater-0.1.4',
                    'launcher-updater-v0.1.4-extra', 'launcher-v0.1.40', 'launcher-v0.1.4x'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                validate_inputs(dict(self.values, release_tag=tag))
        for marker in ('updater-bootstrap-20260928', 'updater-bootstrap-20260927x',
                       'updater-bootstrap-2026092', 'Updater-bootstrap-20260927',
                       'updater-bootstrap-20260927 ', '--flag'):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                validate_inputs(dict(self.values, release_marker=marker))

    @unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'Linux startup behavior')
    def test_startup_preserves_cwd_arguments_and_exit_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); bundle = root/'extracted files'; bundle.mkdir()
            original = root/'original directory'; original.mkdir()
            (bundle/'start.sh').write_text(START_SCRIPT)
            (bundle/'install-linux.sh').write_text('''#!/usr/bin/env bash
python3 - "$@" <<'PY'
import json, os, sys
print(json.dumps([os.getcwd(), sys.argv[1:]]))
PY
exit 7
''')
            result = subprocess.run(['bash', str(bundle/'start.sh'), '--game', './folder with spaces/SOVIET64.exe'],
                                    cwd=bundle, env=dict(os.environ, USER_PWD=str(original)), text=True, capture_output=True)
            self.assertEqual(result.returncode, 7)
            self.assertEqual(json.loads(result.stdout), [str(original), ['--game', './folder with spaces/SOVIET64.exe']])


if __name__ == '__main__':
    unittest.main()

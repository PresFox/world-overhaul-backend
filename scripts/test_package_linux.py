import unittest
from package_linux import validate_inputs, validate_release


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


if __name__ == '__main__':
    unittest.main()

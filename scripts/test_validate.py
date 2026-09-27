import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from release_catalog import legacy_projection, validate_catalogue_rules
from validate import project_legacy, validate, validate_version, validate_version_v4, validate_workshop


class WorkshopTypes(unittest.TestCase):
    def test_schema_four_content_only(self):
        validate_workshop({'schemaVersion': 4, 'requiredWorkshopIds': [{'id': '43', 'type': 'content'}], 'incompatibleWorkshopIds': ['99']})
        for schema, entries in [(4, [{'id': '42', 'type': 'component', 'version': '1.0.0'}]), (5, []), (True, [])]:
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                validate_workshop({'schemaVersion': schema, 'requiredWorkshopIds': entries, 'incompatibleWorkshopIds': []})

    def test_both_types(self):
        validate_workshop({"requiredWorkshopIds": [{"id": "42", "type": "component", "version": "1.0.0"}, {"id": "43", "type": "content"}], "incompatibleWorkshopIds": ["99"]})
        validate_workshop({"requiredWorkshopIds": [], "incompatibleWorkshopIds": []})

    def test_invalid_required_entries(self):
        for entry in ["42", {"id": "42"}, {"id": "42", "type": None}, {"id": "42", "type": "Component"},
                      {"id": "42", "type": "unknown"}, {"id": 42, "type": "content"},
                      {"id": "0", "type": "content"}, {"id": "01", "type": "content"},
                      {"id": "18446744073709551616", "type": "content"}, {"id": "42", "type": "content", "extra": 1}]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                validate_workshop({"requiredWorkshopIds": [entry], "incompatibleWorkshopIds": []})

    def test_duplicates_and_overlap(self):
        first = {"id": "42", "type": "component", "version": "1.0.0"}
        for required, incompatible in [([first, first], []), ([first, {"id": "42", "type": "content"}], []), ([first], ["42"])]:
            with self.assertRaises(ValueError):
                validate_workshop({"requiredWorkshopIds": required, "incompatibleWorkshopIds": incompatible})

    def test_versions(self):
        for item in [{"id": "42", "type": "component"}, {"id": "42", "type": "content", "version": "1"},
                     *({"id": "42", "type": "component", "version": v} for v in [None, 1, "", "../bad", "x" * 65])]:
            with self.subTest(item=item), self.assertRaises(ValueError):
                validate_workshop({"requiredWorkshopIds": [item], "incompatibleWorkshopIds": []})


class InjectorVersion(unittest.TestCase):
    def test_separate_file_versions(self):
        import copy
        valid = {"schemaVersion": 2, "releaseUrl": "https://github.com/PresFox/world-overhaul-backend/releases", "backupBackendUrl": "",
                 **{name: {"version": "0.1.0", "downloadUrl": ""} for name in ("injector", "loader", "workshopManager")}}
        validate_version(valid)
        for key in ("injector", "loader", "workshopManager"):
            for field, value in (("version", "latest"), ("version", "1.0"), ("version", "2147483648.0.0"), ("downloadUrl", "http://example.com/file"), ("downloadUrl", None)):
                bad = copy.deepcopy(valid); bad[key][field] = value
                with self.subTest(key=key, field=field, value=value), self.assertRaises(ValueError):
                    validate_version(bad)
            bad = copy.deepcopy(valid); del bad[key]
            with self.assertRaises(ValueError): validate_version(bad)
        with self.assertRaises(ValueError): validate_version({**valid, "releaseUrl": ""})
        with self.assertRaises(ValueError): validate_version({**valid, "releaseUrl": "http://example.com"})

    def test_bughook(self):
        valid = {"schemaVersion": 1, "version": "0.1.0", "downloadUrl": "", "backupBackendUrl": ""}
        for value in ("", "https://discord.com/api/webhooks/123/fixture"):
            validate_version({**valid, "Bughook": value})
        for value in (None, 42, "http://example.com/hook"):
            with self.assertRaises(ValueError):
                validate_version({**valid, "Bughook": value})

    def test_banner(self):
        valid = {"schemaVersion": 1, "version": "0.1.0", "downloadUrl": "", "backupBackendUrl": ""}
        banner = {"enabled": False, "img": "", "href": "", "height": 0}
        validate_version({**valid, "banner": banner})
        validate_version({**valid, "banner": {**banner, "enabled": True, "img": "images/banner.png", "href": "https://example.com/news", "height": 160}})
        for key, value in [("enabled", "false"), ("enabled", True), ("height", "0"), ("height", True), ("height", 801), ("img", "../image.png"), ("href", "http://example.com")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_version({**valid, "banner": {**banner, key: value}})

    def test_version_feed(self):
        valid = {"schemaVersion": 1, "version": "0.1.0", "downloadUrl": "", "backupBackendUrl": "https://example.com/backend/"}
        validate_version(valid)
        validate_version({**valid, "downloadUrl": "https://example.com/injector.zip"})
        for key, value in [("schemaVersion", True), ("schemaVersion", 2), ("version", ""), ("version", 1), ("downloadUrl", None), ("downloadUrl", "http://example.com/file"), ("downloadUrl", "https://example.com/file#fragment"), ("backupBackendUrl", "https://example.com/backend/?query"), ("backupBackendUrl", "//example.com/")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_version({**valid, key: value})


def branch_fixture():
    def component(item_id, paths):
        return {'workshopId': item_id, 'version': '0.1.0', 'dlls': [
            {'path': path, 'version': '0.1.0.0', 'sha256': 'a' * 64} for path in paths]}
    return {'schemaVersion': 3, 'injector': {'version': '0.1.0', 'downloadUrl': ''},
            'releaseUrl': 'https://example.com/releases', 'backupBackendUrl': '', 'branches': {
                branch: {'components': {'core': component(str(offset), ['WorldOverhaulLoader.dll', 'bin/workshopManager.dll']),
                                        'infrastructure': component(str(offset + 1), ['bin/WorldOverhaul.dll'])}}
                for branch, offset in (('stable', 10), ('beta', 20))}}


class BranchCatalogue(unittest.TestCase):
    def test_valid_and_future_components(self):
        feed = branch_fixture(); validate_version(feed)
        feed['branches']['beta']['components']['vehicles'] = {'workshopId': '30', 'version': '1.0.0',
            'dlls': [{'path': 'bin/vehicles.dll', 'version': '1.0.0', 'sha256': 'b' * 64}]}
        validate_version(feed)

    def test_strict_paths_versions_hashes_and_branch_ids(self):
        import copy
        for field, bad_values in {'path': ['../bad.dll', '/x.dll', 'include/launcher.dll', 'bin/../x.dll', 'bin/CON.dll'],
                                  'version': [None, '', 'latest', '1.0', 1],
                                  'sha256': ['', 'z' * 64, None, 123]}.items():
            for value in bad_values:
                feed = branch_fixture(); feed['branches']['stable']['components']['core']['dlls'][0][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError): validate_version(feed)
        for item_id in ('10', '11', '0', '', '01', '18446744073709551616', 20):
            feed = branch_fixture(); feed['branches']['beta']['components']['core']['workshopId'] = item_id
            with self.subTest(item_id=item_id), self.assertRaises(ValueError): validate_version(feed)
        feed = branch_fixture()
        feed['branches']['stable']['components']['infrastructure']['dlls'].append(copy.deepcopy(feed['branches']['stable']['components']['core']['dlls'][0]))
        with self.assertRaises(ValueError): validate_version(feed)

    def test_unassigned_draft_is_not_a_publishable_stable_release(self):
        feed = branch_fixture()
        core = feed['branches']['stable']['components']['core']; core['workshopId'] = ''; core['version'] = ''
        for dll in core['dlls']: dll['version'] = ''; dll['sha256'] = ''
        validate_version(feed, allow_unassigned=True)
        with self.assertRaises(ValueError): validate_version(feed)

    def test_unreleased_beta_is_unavailable_and_cannot_partially_activate(self):
        for branch in ('stable', 'beta'):
            feed = branch_fixture()
            for component in feed['branches'][branch]['components'].values():
                component['version'] = ''
                for dll in component['dlls']: dll['version'] = ''; dll['sha256'] = ''
            validate_version(feed)
            feed['branches'][branch]['components']['core']['version'] = '0.1.0'
            with self.assertRaises(ValueError): validate_version(feed)

    def test_content_rules_and_catalogue_have_distinct_ownership(self):
        from release_catalog import validate_catalogue_rules
        feed = branch_fixture()
        rules = {'schemaVersion': 4, 'requiredWorkshopIds': [{'id': '99', 'type': 'content'}], 'incompatibleWorkshopIds': ['98']}
        validate_workshop(rules); validate_catalogue_rules(feed, rules)
        rules['requiredWorkshopIds'][0]['id'] = '10'
        with self.assertRaises(ValueError): validate_catalogue_rules(feed, rules)
        rules['requiredWorkshopIds'] = []; rules['incompatibleWorkshopIds'] = ['20']
        with self.assertRaises(ValueError): validate_catalogue_rules(feed, rules)
        rules['requiredWorkshopIds'] = [{'id': '99', 'type': 'component', 'version': '1.0.0'}]
        with self.assertRaises(ValueError): validate_workshop(rules)


def v4_fixture():
    """Schema 4: the schema 3 catalogue plus one injector package per branch."""
    feed = branch_fixture()
    feed['schemaVersion'] = 4
    for branch, offset in (('stable', 50), ('beta', 60)):
        feed['branches'][branch]['injector'] = {'workshopId': str(offset), 'version': '0.1.0',
                                                'manifestSha256': 'c' * 64}
    return feed


class VersionV4(unittest.TestCase):
    def test_valid_feed_and_exclusive_schemas(self):
        validate_version_v4(v4_fixture())
        validate_version_v4({**v4_fixture(), 'Bughook': 'https://discord.com/api/webhooks/123/fixture'})
        with self.assertRaises(ValueError): validate_version(v4_fixture())
        with self.assertRaises(ValueError): validate_version_v4(branch_fixture())
        for schema in (True, 3, 5, '4'):
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                validate_version_v4({**v4_fixture(), 'schemaVersion': schema})
        stale = v4_fixture()
        stale['loader'] = {'version': '0.1.0', 'downloadUrl': ''}
        with self.assertRaises(ValueError): validate_version_v4(stale)
        for branch in ('stable', 'beta'):
            legacy = v4_fixture()
            del legacy['branches'][branch]['injector']
            with self.subTest(branch=branch), self.assertRaises(ValueError):
                validate_version_v4(legacy)

    def test_injector_triplet_is_all_or_nothing(self):
        for field in ('workshopId', 'version', 'manifestSha256'):
            for value in ('', 'x'):
                feed = v4_fixture()
                feed['branches']['stable']['injector'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_version_v4(feed)
        for mutate in (lambda injector: injector.pop('version'), lambda injector: injector.update(extra='1')):
            feed = v4_fixture(); mutate(feed['branches']['stable']['injector'])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate_version_v4(feed)

    def test_injector_hash_version_and_id_formats(self):
        invalid = {'manifestSha256': ['C' * 64, 'a' * 63, 'a' * 65, 'g' * 64, None, 42, True],
                   'version': ['latest', '1.0', '', None, 1, '2147483648.0.0', '0.1.0.0.0'],
                   'workshopId': ['0', '01', '', None, '18446744073709551616', 18446744073709551615]}
        for field, values in invalid.items():
            for value in values:
                feed = v4_fixture()
                feed['branches']['beta']['injector'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_version_v4(feed)
        assigned = v4_fixture()
        assigned['branches']['beta']['injector']['workshopId'] = '18446744073709551615'
        validate_version_v4(assigned)

    def test_injector_ids_are_distinct_runtime_packages(self):
        for branch, value in (('beta', '50'), ('stable', '10'),
                              ('beta', '20')):
            feed = v4_fixture(); feed['branches'][branch]['injector']['workshopId'] = value
            with self.subTest(branch=branch, value=value), self.assertRaises(ValueError):
                validate_version_v4(feed)

    def test_injector_publication_is_independent_of_component_releases(self):
        empty = {'workshopId': '', 'version': '', 'manifestSha256': ''}

        def unrelease_branch(feed, branch):
            for component in feed['branches'][branch]['components'].values():
                component['version'] = ''
                for dll in component['dlls']:
                    dll['version'] = ''; dll['sha256'] = ''

        # An unreleased injector package is valid while the branch components are live.
        for branch in ('stable', 'beta'):
            feed = v4_fixture(); feed['branches'][branch]['injector'] = empty
            with self.subTest(branch=branch, injector='unreleased', components='live'):
                validate_version_v4(feed)
                validate_version_v4(feed, allow_unassigned=True)

        # An assigned injector package is valid while the branch components are unreleased.
        for branch in ('stable', 'beta'):
            feed = v4_fixture(); unrelease_branch(feed, branch)
            with self.subTest(branch=branch, injector='assigned', components='unreleased'):
                validate_version_v4(feed)
                validate_version_v4(feed, allow_unassigned=True)

        # An entirely unreleased branch stays publishable, and both states may coexist.
        feed = v4_fixture(); unrelease_branch(feed, 'beta'); feed['branches']['beta']['injector'] = empty
        validate_version_v4(feed)
        feed = v4_fixture(); feed['branches']['stable']['injector'] = empty; unrelease_branch(feed, 'beta')
        validate_version_v4(feed)
        feed = v4_fixture(); feed['branches']['beta']['injector'] = empty; unrelease_branch(feed, 'stable')
        validate_version_v4(feed)

        # A partially assigned injector package is never valid, even as a local draft.
        for field in ('workshopId', 'version', 'manifestSha256'):
            for value in ('', 'x'):
                feed = v4_fixture(); feed['branches']['stable']['injector'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_version_v4(feed)
                with self.subTest(field=field, value=value, allow_unassigned=True), self.assertRaises(ValueError):
                    validate_version_v4(feed, allow_unassigned=True)


class RuntimeContentOwnership(unittest.TestCase):
    def rules(self, required=('99',), incompatible=()):
        return {'schemaVersion': 4, 'requiredWorkshopIds': [{'id': item, 'type': 'content'} for item in required],
                'incompatibleWorkshopIds': list(incompatible)}

    def test_branch_injector_ids_never_enter_content_rules(self):
        validate_catalogue_rules(v4_fixture(), self.rules())
        for rules in (self.rules(required=('50',)), self.rules(required=('60',)),
                      self.rules(incompatible=('50',)), self.rules(incompatible=('60',))):
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                validate_catalogue_rules(v4_fixture(), rules)

    def test_content_rules_are_branch_independent(self):
        for branch in ('stable', 'beta'):
            feed = v4_fixture()
            for name in ('core', 'infrastructure'):
                rules = self.rules(required=(feed['branches'][branch]['components'][name]['workshopId'],))
                with self.subTest(branch=branch, component=name), self.assertRaises(ValueError):
                    validate_catalogue_rules(feed, rules)
        legacy = branch_fixture()  # schema 3 catalogues report only component IDs
        with self.assertRaises(ValueError):
            validate_catalogue_rules(legacy, self.rules(required=('20',)))


class LegacyProjection(unittest.TestCase):
    def test_shared_metadata_passes_through_and_branch_injectors_are_dropped(self):
        feed = v4_fixture()
        feed['banner'] = {'enabled': False, 'img': '', 'href': '', 'height': 0}
        feed['Bughook'] = 'https://discord.com/api/webhooks/123/fixture'
        projection = legacy_projection(feed)
        self.assertEqual(set(projection), {'schemaVersion', 'injector', 'releaseUrl', 'backupBackendUrl', 'branches', 'banner', 'Bughook'})
        self.assertEqual(projection['schemaVersion'], 3)
        for key in ('injector', 'releaseUrl', 'backupBackendUrl', 'banner', 'Bughook'):
            self.assertEqual(projection[key], feed[key])
        for branch, entry in feed['branches'].items():
            self.assertEqual(projection['branches'][branch], {'components': entry['components']})
            self.assertEqual(set(projection['branches'][branch]), {'components'})
        validate_version(projection)
        projection['branches']['stable']['components']['core']['dlls'][0]['sha256'] = 'e' * 64
        self.assertEqual(feed['branches']['stable']['components']['core']['dlls'][0]['sha256'], 'a' * 64)

    def test_projection_rejects_unknown_or_legacy_shapes(self):
        with self.assertRaises(ValueError): legacy_projection(branch_fixture())
        for key in ('loader', 'extra'):
            feed = v4_fixture(); feed[key] = 1
            with self.subTest(key=key), self.assertRaises(ValueError): legacy_projection(feed)
        feed = v4_fixture(); feed['branches']['stable']['extra'] = 1
        with self.assertRaises(ValueError): legacy_projection(feed)

    def test_generation_writes_a_lf_utf8_legacy_file(self):
        feed = v4_fixture()
        for component in feed['branches']['beta']['components'].values():
            component['version'] = ''
            for dll in component['dlls']:
                dll['version'] = ''; dll['sha256'] = ''
        feed['branches']['beta']['injector'] = {'workshopId': '', 'version': '', 'manifestSha256': ''}
        with tempfile.TemporaryDirectory(prefix='worldoverhaul-projection-') as temporary:
            root = Path(temporary)
            (root / 'version-v4.json').write_text(json.dumps(feed), encoding='utf-8')
            destination = root / 'version.json'
            with contextlib.redirect_stdout(io.StringIO()) as output:
                project_legacy(allow_unassigned=True, root=root, destination=destination)
            self.assertIn('legacy projection', output.getvalue())
            generated = destination.read_bytes()
            self.assertFalse(generated.startswith(b'\xef\xbb\xbf'))
            self.assertNotIn(b'\r', generated)
            rendered = json.loads(generated.decode('utf-8'))
            self.assertEqual(rendered, legacy_projection(feed))
            validate_version(rendered, allow_unassigned=True)
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                project_legacy(allow_unassigned=True, root=root)
            self.assertEqual(json.loads(printed.getvalue()), rendered)
            with self.assertRaises(ValueError):
                project_legacy(root=root / 'missing')


class SiteValidation(unittest.TestCase):
    NEWS = {'schemaVersion': 1, 'items': [{'id': 'a', 'title': 't', 'publishedAt': '2026-09-01T00:00:00Z', 'summary': 's'}]}
    UPDATES = {'schemaVersion': 1, 'releases': []}

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='worldoverhaul-site-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write_site(self, feed=None, legacy=None, rules=None, v4=True):
        feed = v4_fixture() if feed is None else feed
        rules = {'schemaVersion': 4, 'requiredWorkshopIds': [{'id': '99', 'type': 'content'}],
                 'incompatibleWorkshopIds': ['98']} if rules is None else rules
        legacy = legacy_projection(feed) if legacy is None else legacy
        for name, data in (('news.json', self.NEWS), ('updates.json', self.UPDATES),
                           ('workshop.json', rules), ('version.json', legacy)):
            (self.root / name).write_text(json.dumps(data), encoding='utf-8')
        if v4:
            (self.root / 'version-v4.json').write_text(json.dumps(feed), encoding='utf-8')

    def run_site_validation(self, allow_unassigned=False):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            validate(allow_unassigned=allow_unassigned, root=self.root)
        return output.getvalue()

    def test_consistent_site_publishes_both_feeds(self):
        self.write_site()
        self.assertIn('version-v4.json matches its legacy projection', self.run_site_validation())

    def test_site_without_v4_keeps_the_schema_three_path(self):
        self.write_site()
        (self.root / 'version-v4.json').unlink()
        self.assertNotIn('version-v4.json', self.run_site_validation())

    def test_site_without_v4_keeps_legacy_schema_two_path(self):
        legacy = {'schemaVersion': 2, 'injector': {'version': '0.1.0', 'downloadUrl': ''},
                  'loader': {'version': '0.1.0', 'downloadUrl': ''},
                  'workshopManager': {'version': '0.1.0', 'downloadUrl': ''},
                  'releaseUrl': 'https://example.com/releases', 'backupBackendUrl': ''}
        rules = {'schemaVersion': 3, 'requiredWorkshopIds': [{'id': '42', 'type': 'component', 'version': '1.0.0'}],
                 'incompatibleWorkshopIds': []}
        self.write_site(legacy=legacy, rules=rules, v4=False)
        self.run_site_validation()

    def test_legacy_projection_must_match_the_published_v4_feed(self):
        baseline = legacy_projection(v4_fixture())
        def drop_beta(feed): del feed['branches']['beta']
        def change_hash(feed): feed['branches']['stable']['components']['core']['dlls'][0]['sha256'] = 'd' * 64
        def change_injector(feed): feed['injector']['version'] = '9.9.9'
        def add_banner(feed): feed['banner'] = {'enabled': False, 'img': '', 'href': '', 'height': 0}
        for mutate in (drop_beta, change_hash, change_injector, add_banner):
            legacy = json.loads(json.dumps(baseline)); mutate(legacy)
            self.write_site(legacy=legacy)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.run_site_validation()

    def test_invalid_v4_feed_is_rejected_even_with_a_matching_projection(self):
        feed = v4_fixture()
        feed['branches']['beta']['injector']['workshopId'] = feed['branches']['beta']['components']['core']['workshopId']
        self.write_site(feed=feed, legacy=legacy_projection(v4_fixture()))
        with self.assertRaises(ValueError):
            self.run_site_validation()

    def test_runtime_injector_ids_cannot_be_content_rules_on_site(self):
        for rules in ({'schemaVersion': 4, 'requiredWorkshopIds': [{'id': '50', 'type': 'content'}], 'incompatibleWorkshopIds': []},
                      {'schemaVersion': 4, 'requiredWorkshopIds': [], 'incompatibleWorkshopIds': ['60']}):
            self.write_site(rules=rules)
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                self.run_site_validation()


if __name__ == "__main__":
    unittest.main()

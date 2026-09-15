import unittest
from validate import validate_workshop, validate_version


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


if __name__ == "__main__":
    unittest.main()

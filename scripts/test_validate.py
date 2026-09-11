import unittest
from validate import validate_workshop, validate_version


class WorkshopTypes(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

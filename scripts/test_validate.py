import unittest
from validate import validate_workshop


class WorkshopTypes(unittest.TestCase):
    def test_both_types(self):
        validate_workshop({"requiredWorkshopIds": [{"id": "42", "type": "component"}, {"id": "43", "type": "content"}], "incompatibleWorkshopIds": ["99"]})
        validate_workshop({"requiredWorkshopIds": [], "incompatibleWorkshopIds": []})

    def test_invalid_required_entries(self):
        for entry in ["42", {"id": "42"}, {"id": "42", "type": None}, {"id": "42", "type": "Component"},
                      {"id": "42", "type": "unknown"}, {"id": 42, "type": "content"},
                      {"id": "0", "type": "content"}, {"id": "01", "type": "content"},
                      {"id": "18446744073709551616", "type": "content"}, {"id": "42", "type": "content", "extra": 1}]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                validate_workshop({"requiredWorkshopIds": [entry], "incompatibleWorkshopIds": []})

    def test_duplicates_and_overlap(self):
        first = {"id": "42", "type": "component"}
        for required, incompatible in [([first, first], []), ([first, {"id": "42", "type": "content"}], []), ([first], ["42"])]:
            with self.assertRaises(ValueError):
                validate_workshop({"requiredWorkshopIds": required, "incompatibleWorkshopIds": incompatible})


if __name__ == "__main__":
    unittest.main()

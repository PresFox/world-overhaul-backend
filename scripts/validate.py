"""Validate public feed contracts using only the Python standard library."""
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1] / "site"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON property: {key}")
        result[key] = value
    return result


def read(name, keys, version=1):
    path = ROOT / name
    require(path.stat().st_size <= 1024 * 1024, f"{name} exceeds 1 MiB")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    require(type(data) is dict and set(data) == {"schemaVersion", *keys}, f"Unexpected fields in {name}")
    require(type(data["schemaVersion"]) is int and data["schemaVersion"] == version, f"Unsupported schema in {name}")
    for key in keys:
        require(type(data[key]) is list, f"{name}: {key} must be an array")
    return data


def text(value, label):
    require(type(value) is str and value.strip() != "", f"{label} must be nonempty text")


def https(value):
    text(value, "URL")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password
            and not any(c.isspace() for c in value), "Expected a public HTTPS URL without credentials")


def validate_workshop(rules):
    def workshop_id(value):
        require(type(value) is str and re.fullmatch(r"[1-9][0-9]*", value) and int(value) <= 18446744073709551615,
                "Workshop IDs must be positive uint64 decimal strings")
    require(type(rules.get("schemaVersion", 3)) is int and rules.get("schemaVersion", 3) in (3, 4), "Unsupported Workshop schema")
    required = set()
    for item in rules["requiredWorkshopIds"]:
        require(type(item) is dict and "id" in item and "type" in item, "Required mod needs id and type")
        workshop_id(item["id"])
        require(item["type"] in ("component", "content"), "Required mod type must be component or content")
        if rules.get("schemaVersion") == 4:
            require(item["type"] == "content", "Schema 4 requires content only; components belong in version.json")
        expected = {"id", "type", "version"} if item["type"] == "component" else {"id", "type"}
        require(set(item) == expected, "Components require version; content has no custom version")
        if item["type"] == "component":
            require(type(item["version"]) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}", item["version"]), "Invalid component release version")
        require(item["id"] not in required, "Duplicate required Workshop ID")
        required.add(item["id"])
    incompatible = rules["incompatibleWorkshopIds"]
    for value in incompatible:
        workshop_id(value)
    require(len(incompatible) == len(set(incompatible)), "Duplicate incompatible Workshop ID")
    require(not required & set(incompatible), "A Workshop ID cannot be both required and incompatible")


def validate_version(data):
    require(type(data) is dict, "Invalid version feed")
    schema = data.get("schemaVersion")
    require(type(schema) is int and schema in (1, 2), "Unsupported version feed schema")
    expected = ({"schemaVersion", "version", "downloadUrl", "backupBackendUrl"} if schema == 1 else
                {"schemaVersion", "injector", "loader", "workshopManager", "releaseUrl", "backupBackendUrl"})
    require(set(data) - {"banner", "Bughook"} == expected, "Invalid version feed fields")
    urls = [(key, data.get(key, "")) for key in ("backupBackendUrl", "Bughook")]
    if schema == 1:
        require(type(data["version"]) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}", data["version"]), "Invalid injector version")
        urls.append(("downloadUrl", data["downloadUrl"]))
    else:
        for name in ("injector", "loader", "workshopManager"):
            file = data[name]
            require(type(file) is dict and set(file) == {"version", "downloadUrl"}, "Invalid file release fields")
            version = file["version"]
            require(type(version) is str and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?", version)
                    and all(int(part) <= 2147483647 for part in version.split('.')), "Expected numeric file version")
            urls.append((name + " downloadUrl", file["downloadUrl"]))
        text(data["releaseUrl"], "releaseUrl")
        urls.append(("releaseUrl", data["releaseUrl"]))
    for key, value in urls:
        require(type(value) is str, f"{key} must be a string")
        if not value:
            continue
        https(value)
        parsed = urlsplit(value)
        require(len(value) <= 2048 and not parsed.fragment and not any(c in value for c in ('\\', '"', '#')) and not any(ord(c) < 32 or ord(c) == 127 for c in value), f"Invalid {key}")
        if key == "backupBackendUrl":
            require(not parsed.query and parsed.path.endswith('/'), "Backup backend must be a directory URL ending in /")
    if "banner" in data:
        banner = data["banner"]
        require(type(banner) is dict and set(banner) == {"enabled", "img", "href", "height"}, "Invalid banner fields")
        require(type(banner["enabled"]) is bool, "Banner enabled must be boolean")
        require(type(banner["height"]) is int and 0 <= banner["height"] <= 800, "Banner height must be 0..800")
        for key in ("img", "href"):
            value = banner[key]
            require(type(value) is str and len(value) <= 2048, "Invalid banner URL")
            if not value:
                continue
            parsed = urlsplit(value)
            if parsed.scheme:
                https(value)
                require(not parsed.fragment and not any(c in value for c in ('\\', '"', '#'))
                        and not any(ord(c) < 32 or ord(c) == 127 for c in value), "Invalid banner URL")
            else:
                decoded = unquote(value)
                require(not decoded.startswith('/') and not any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c in '\\":#' for c in decoded)
                        and not any(p in ('.', '..') for p in decoded.split('?', 1)[0].split('/')), "Invalid relative banner URL")
        require(not banner["enabled"] or bool(banner["img"]), "Enabled banner requires an image")


def validate():
    news = read("news.json", ["items"])
    ids = set()
    for item in news["items"]:
        require(type(item) is dict and {"id", "title", "publishedAt", "summary"} <= set(item)
                and set(item) <= {"id", "title", "publishedAt", "summary", "articleUrl", "imageUrl"}, "Invalid news fields")
        for key in ["id", "title", "publishedAt", "summary"]:
            text(item[key], key)
        require(item["id"] not in ids, "Duplicate news ID")
        ids.add(item["id"])
        require(datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00")).tzinfo is not None,
                "News publication date must include timezone")
        for key in ["articleUrl", "imageUrl"]:
            if key in item:
                https(item[key])

    updates = read("updates.json", ["releases"])
    channels = set()
    for item in updates["releases"]:
        require(type(item) is dict and set(item) == {"component", "channel", "version", "releaseUrl"}, "Invalid release fields")
        require(item["component"] in ["injector", "loader", "world_overhaul"], "Unknown release component")
        require(item["channel"] in ["stable", "testers"], "Unknown release channel")
        text(item["version"], "version")
        https(item["releaseUrl"])
        key = (item["component"], item["channel"])
        require(key not in channels, "Only one current release per component/channel")
        channels.add(key)

    rules_schema = json.loads((ROOT / "workshop.json").read_text(encoding="utf-8"), object_pairs_hook=unique_keys).get("schemaVersion")
    require(type(rules_schema) is int and rules_schema in (3, 4), "Unsupported Workshop schema")
    rules = read("workshop.json", ["requiredWorkshopIds", "incompatibleWorkshopIds"], version=rules_schema)
    validate_workshop(rules)
    version_path = ROOT / "version.json"
    require(version_path.stat().st_size <= 1024 * 1024, "Version feed exceeds 1 MiB")
    validate_version(json.loads(version_path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys))
    print(f"Valid: {len(news['items'])} news items, {len(updates['releases'])} releases, "
          f"{len(rules['requiredWorkshopIds'])} required and {len(rules['incompatibleWorkshopIds'])} incompatible mods")


if __name__ == "__main__":
    validate()

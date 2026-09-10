"""Validate public feed contracts using only the Python standard library."""
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

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


def read(name, keys):
    path = ROOT / name
    require(path.stat().st_size <= 1024 * 1024, f"{name} exceeds 1 MiB")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    require(type(data) is dict and set(data) == {"schemaVersion", *keys}, f"Unexpected fields in {name}")
    require(type(data["schemaVersion"]) is int and data["schemaVersion"] == 1, f"Unsupported schema in {name}")
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

    rules = read("workshop.json", ["requiredWorkshopIds", "incompatibleWorkshopIds"])
    for key in ["requiredWorkshopIds", "incompatibleWorkshopIds"]:
        for value in rules[key]:
            require(type(value) is str and re.fullmatch(r"[1-9][0-9]*", value) and int(value) <= 18446744073709551615,
                    f"{key}: Workshop IDs must be positive uint64 decimal strings")
        require(len(rules[key]) == len(set(rules[key])), f"Duplicate ID in {key}")
    require(not set(rules["requiredWorkshopIds"]) & set(rules["incompatibleWorkshopIds"]),
            "A Workshop ID cannot be both required and incompatible")
    print(f"Valid: {len(news['items'])} news items, {len(updates['releases'])} releases, "
          f"{len(rules['requiredWorkshopIds'])} required and {len(rules['incompatibleWorkshopIds'])} incompatible mods")


if __name__ == "__main__":
    validate()

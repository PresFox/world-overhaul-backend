"""Shared branch catalogue contract for Pages validation and the Windows releaser."""
import re


def require(condition, message):
    if not condition:
        raise ValueError(message)


def workshop_id(value, allow_unassigned=False):
    if allow_unassigned and value == "":
        return
    require(type(value) is str and re.fullmatch(r"[1-9][0-9]*", value)
            and int(value) < 2**64, "Workshop ID is unassigned or is not a positive uint64 string")


def file_version(value, allow_unassigned=False):
    if allow_unassigned and value == "":
        return
    require(type(value) is str and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?", value)
            and all(int(part) <= 2147483647 for part in value.split('.')), "Invalid or unassigned DLL version")


def dll_path(value):
    require(type(value) is str and 0 < len(value) <= 240 and value.lower().endswith('.dll'), "Expected a relative DLL path")
    require(not any(ord(c) < 32 or c in '<>:"\\|?*' for c in value), "Invalid DLL path")
    for part in value.split('/'):
        require(part not in ('', '.', '..') and not part.endswith(('.', ' '))
                and not re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', part, re.I), "Invalid DLL path segment")
    require(value == 'WorldOverhaulLoader.dll' or value.startswith('bin/'), "Runtime DLLs belong at WorldOverhaulLoader.dll or below bin/")


def validate_branches(branches, allow_unassigned=False):
    require(type(branches) is dict and set(branches) == {'stable', 'beta'}, "Expected stable and beta branches")
    ids = set()
    for branch, entry in branches.items():
        require(type(entry) is dict and set(entry) == {'components'}, "Invalid branch fields")
        components = entry['components']
        require(type(components) is dict and {'core', 'infrastructure'} <= components.keys(), "Each branch requires core and infrastructure")
        # Either branch may be uninitialized during the first publication.
        # Never resolve an unavailable branch through the other branch.
        inactive = all(type(c) is dict and c.get('version') == '' for c in components.values())
        draft = allow_unassigned or inactive
        destinations = set()
        for name, component in components.items():
            require(re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name), "Invalid component name")
            require(type(component) is dict and set(component) == {'workshopId', 'version', 'dlls'}, "Invalid component fields")
            item_id = component['workshopId']
            workshop_id(item_id, draft)
            if item_id:
                require(item_id not in ids, "Workshop IDs must be distinct between components and branches")
                ids.add(item_id)
            package_version = component['version']
            require((draft and package_version == '') or
                    (type(package_version) is str and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', package_version)), "Invalid or unassigned package version")
            require(type(component['dlls']) is list and component['dlls'], "Component must list its DLLs")
            for dll in component['dlls']:
                require(type(dll) is dict and set(dll) == {'path', 'version', 'sha256'}, "Invalid DLL fields")
                dll_path(dll['path']); file_version(dll['version'], draft)
                require((draft and dll['sha256'] == '') or (type(dll['sha256']) is str
                        and re.fullmatch(r'[0-9a-f]{64}', dll['sha256'])), "Invalid or unassigned DLL checksum")
                path = dll['path'].lower()
                require(path not in destinations, "Overlapping DLL ownership within a branch")
                destinations.add(path)
            if name == 'core':
                require({'WorldOverhaulLoader.dll', 'bin/workshopManager.dll'} <= {d['path'] for d in component['dlls']}, "Core must include Loader and Workshop Manager")
            if name == 'infrastructure':
                require('bin/WorldOverhaul.dll' in {d['path'] for d in component['dlls']}, "Infrastructure must include WorldOverhaul.dll")


def validate_catalogue_rules(feed, rules):
    """A runtime package must never also enter the game's content whitelist."""
    require(rules.get('schemaVersion') == 4, "Branch catalogues require workshop.json schema 4")
    required = {item['id'] for item in rules['requiredWorkshopIds']}
    incompatible = set(rules['incompatibleWorkshopIds'])
    ids = {component['workshopId'] for branch in feed['branches'].values()
           for component in branch['components'].values() if component['workshopId']}
    require(not ids & required, "Runtime components belong only in version.json")
    require(not ids & incompatible, "A branch component cannot be marked incompatible")

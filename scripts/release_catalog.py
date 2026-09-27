"""Shared branch catalogue contract for Pages validation and the Windows releaser."""
import copy
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


def manifest_sha256(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value),
            "Injector manifest checksum is unassigned or is not a lowercase SHA256")


def dll_path(value):
    require(type(value) is str and 0 < len(value) <= 240 and value.lower().endswith('.dll'), "Expected a relative DLL path")
    require(not any(ord(c) < 32 or c in '<>:"\\|?*' for c in value), "Invalid DLL path")
    for part in value.split('/'):
        require(part not in ('', '.', '..') and not part.endswith(('.', ' '))
                and not re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', part, re.I), "Invalid DLL path segment")
    require(value == 'WorldOverhaulLoader.dll' or value.startswith('bin/'), "Runtime DLLs belong at WorldOverhaulLoader.dll or below bin/")


def draft_branch(components, allow_unassigned):
    """A branch may stay unassigned locally or be entirely unreleased in a feed.

    Never resolve an unavailable branch through the other branch.
    """
    inactive = type(components) is dict and all(type(c) is dict and c.get('version') == '' for c in components.values())
    return allow_unassigned or inactive


def validate_components(components, ids, draft):
    """Validate one branch's components and collect their runtime Workshop IDs."""
    require(type(components) is dict and {'core', 'infrastructure'} <= components.keys(), "Each branch requires core and infrastructure")
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


def validate_branch_injector(injector, ids):
    """Schema 4 branch injector package; all three fields assigned or all three empty.

    The injector's publication state is independent of the branch components: an
    unreleased injector package is valid while the components are live, and an
    assigned injector package is valid while the components are unreleased.
    """
    require(type(injector) is dict and set(injector) == {'workshopId', 'version', 'manifestSha256'},
            "Invalid branch injector fields")
    item_id, version, digest = injector['workshopId'], injector['version'], injector['manifestSha256']
    if item_id == '' and version == '' and digest == '':
        return
    require(all(type(value) is str and value != '' for value in (item_id, version, digest)),
            "Branch injector needs workshopId, version and manifestSha256 together")
    workshop_id(item_id)
    file_version(version)
    manifest_sha256(digest)
    require(item_id not in ids, "Workshop IDs must be distinct between components and branches")
    ids.add(item_id)


def validate_branches(branches, allow_unassigned=False):
    """Legacy schema 3 catalogue: components only."""
    require(type(branches) is dict and set(branches) == {'stable', 'beta'}, "Expected stable and beta branches")
    ids = set()
    for entry in branches.values():
        require(type(entry) is dict and set(entry) == {'components'}, "Invalid branch fields")
        validate_components(entry['components'], ids, draft_branch(entry['components'], allow_unassigned))


def validate_v4_branches(branches, allow_unassigned=False):
    """Schema 4 catalogue: the schema 3 components plus one independent injector package per branch."""
    require(type(branches) is dict and set(branches) == {'stable', 'beta'}, "Expected stable and beta branches")
    ids = set()
    for entry in branches.values():
        require(type(entry) is dict and set(entry) == {'components', 'injector'}, "Invalid branch fields")
        draft = allow_unassigned or draft_branch(entry['components'], False)
        validate_components(entry['components'], ids, draft)
        validate_branch_injector(entry['injector'], ids)


def runtime_workshop_ids(feed):
    """Every runtime package ID in a schema 3 or schema 4 branch catalogue."""
    require(type(feed) is dict and feed.get('schemaVersion') in (3, 4), "Unsupported version feed schema")
    ids = set()
    for branch in feed['branches'].values():
        for component in branch['components'].values():
            if component['workshopId']:
                ids.add(component['workshopId'])
        injector = branch.get('injector')
        if type(injector) is dict and injector.get('workshopId'):
            ids.add(injector['workshopId'])
    return ids


def validate_catalogue_rules(feed, rules):
    """A runtime package must never also enter the game's content whitelist."""
    require(rules.get('schemaVersion') == 4, "Branch catalogues require workshop.json schema 4")
    required = {item['id'] for item in rules['requiredWorkshopIds']}
    incompatible = set(rules['incompatibleWorkshopIds'])
    ids = runtime_workshop_ids(feed)
    require(not ids & required, "Runtime components and injectors belong only in version.json")
    require(not ids & incompatible, "A branch runtime package cannot be marked incompatible")


def legacy_projection(feed):
    """Project a schema 4 feed onto the schema 3 shape that legacy launchers read.

    Branch injector packages are dropped because schema 3 has nowhere to carry
    them. The shared installer entry, branch components, release URL, backup
    backend, banner and bug-report endpoint pass through unchanged, so a legacy
    client keeps reading exactly the values it read before the migration.
    """
    require(type(feed) is dict and feed.get('schemaVersion') == 4, "Legacy projection requires a schema 4 feed")
    require(set(feed) <= {'schemaVersion', 'injector', 'releaseUrl', 'backupBackendUrl', 'branches', 'banner', 'Bughook'},
            "Unexpected fields in a schema 4 feed")
    projection = {'schemaVersion': 3, 'injector': copy.deepcopy(feed['injector']),
                  'releaseUrl': feed['releaseUrl'], 'backupBackendUrl': feed['backupBackendUrl'], 'branches': {}}
    for branch, entry in feed['branches'].items():
        require(type(entry) is dict and set(entry) <= {'components', 'injector'}, "Unexpected fields in a schema 4 branch")
        projection['branches'][branch] = {'components': copy.deepcopy(entry['components'])}
    for name in ('banner', 'Bughook'):
        if name in feed:
            projection[name] = copy.deepcopy(feed[name])
    return projection

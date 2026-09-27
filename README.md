# World Overhaul backend

Public news, update information and Workshop compatibility data for the World
Overhaul launcher for **Workers & Resources: Soviet Republic**.

GitHub Pages publishes the contents of `site/`. This repository contains the
public feeds, their validation/documentation and the Linux release packaging
workflow. Installer binaries are release assets, not repository content.

## Linux installer packaging

`package-linux.yml` runs on Ubuntu 24.04 through an explicit `workflow_dispatch`
from the Windows Releaser. It downloads the MSI and matching `install-linux.sh`
from that job's draft release, checks the supplied SHA256 values and wraps them
with Makeself 2.7.1 pinned to commit 3815292f7359a4ccab8e27bdbe8a844947c51e4c.
It tests the archive checksum (including corruption rejection), exact extracted
bytes and the real `--help` entry point. It does not install the MSI, run Steam,
launch the game, or publish the draft.

The job attaches `WorldOverhaul-<version>-linux.run` and an internal manifest.
The Releaser binds that manifest to the request ID, workflow commit/run/attempt
and original input hashes, downloads and verifies the bundle, removes the helper
and manifest from the draft, then publishes only the MSI and `.run`. Failures
leave the draft unpublished; Retry resumes an active run or reruns a failed one.
This packaging job uses `contents: write` with its repository-scoped
`GITHUB_TOKEN`. The local publisher needs Actions access through its existing
GitHub CLI login. Workflow code must be installed on `main`.

Linux players run `bash WorldOverhaul-<version>-linux.run`. Advanced helper
arguments go after Makeself's separator, for example
`bash WorldOverhaul-<version>-linux.run -- --terminal` or `-- --uninstall`.
Uninstall uses the bundle for the installed MSI version. Python 3.8+ and the
selected Wine/Proton environment are still required. Packaging tests do not
establish live Wine/Proton compatibility.

## Endpoints

| Feed | URL |
| --- | --- |
| Shared launcher, branch components and per-branch injectors | https://presfox.github.io/world-overhaul-backend/version-v4.json |
| Schema 3 projection of the branch feed read by older launchers | https://presfox.github.io/world-overhaul-backend/version.json |
| News | https://presfox.github.io/world-overhaul-backend/news.json |
| Updates | https://presfox.github.io/world-overhaul-backend/updates.json |
| Workshop requirements and incompatibilities | https://presfox.github.io/world-overhaul-backend/workshop.json |

The earlier `compatibility.json` URL remains a deployment-generated alias of
`workshop.json`. Edit only `site/workshop.json` for Workshop rules.

`version-v4.json` uses schema **4** and is the branch feed. `version.json` remains
the schema **3** projection that older launchers read, so both files are published
and must agree: validation rejects a `version.json` that differs from the exact
projection of `version-v4.json`. `workshop.json` uses schema **4** and holds the
shared content requirements and incompatibilities only. `python scripts/validate.py`
checks every feed plus that projection; `--allow-unassigned` accepts local drafts
and must never gate publication.

`python scripts/validate.py --project-legacy [PATH]` prints the schema 3 projection
of `site/version-v4.json`, or writes it to `PATH` when one is given. The Releaser
regenerates `version.json` that way after every branch publication instead of
hand-editing the projection.

Both feeds keep the shared `injector: {version, downloadUrl}`, `releaseUrl`,
`backupBackendUrl` and optional `banner`/`Bughook` unchanged; the projection copies
them verbatim. Loader and Workshop Manager no longer have top-level releases or
direct-download URLs. They are Workshop files.

`branches.stable.components` and `branches.beta.components` are objects keyed by
permanent component names. Initially both contain `core` and `infrastructure`.
Readers must support additional component keys without a launcher rebuild.
Each component has exactly:

- `workshopId`: positive uint64 decimal **string**, distinct across all branches/components.
- `version`: the Workshop package version, `major.minor.patch`, matching `manifest.json`.
- `dlls`: an array of `{path, version, sha256}`. `path` is relative to the installed
  WorldOverhaul root; `version` is the actual numeric PE file version (three/four
  parts); `sha256` is the 64-character lowercase hash of the packaged DLL.

Core owns `WorldOverhaulLoader.dll` and `bin/workshopManager.dll`. Infrastructure
owns `bin/WorldOverhaul.dll`. DLL paths cannot overlap within a branch. Additional
DLLs may live below `bin/`; launcher/dependency files under `include/` are outside
this catalogue. Never substitute a package version for a missing PE version.

`branches.<branch>.injector` is that branch's own launcher package:
`{workshopId, version, manifestSha256}`. `workshopId` is a positive uint64 decimal
string, `version` is the injected launcher version, and `manifestSha256` is the
64-character lowercase SHA-256 of the package's schema-1 `manifest.json`. The feed
digest authenticates manifest content; it is not proof of package identity, and the
updater still verifies the downloaded package against it. The three fields are
assigned together or left as three empty strings; partial entries are invalid.
Injector publication is independent of component publication: either may remain
unreleased while the other has valid release metadata.

Runtime IDs are unique across the whole feed: component and branch injector
`workshopId` values must all differ, in every branch. No runtime ID may appear in
`workshop.json`'s required-content or incompatible lists; runtime packages are
delivered through Workshop subscriptions described by the branch feed.

Empty IDs, package versions, DLL versions, hashes and branch injector fields mean
**unassigned local draft data**, never fallback to Stable. An entirely unreleased
Beta component branch can remain unavailable in a published feed. Active component
branches require complete component data; injector entries independently require
either a complete triplet or three empty strings.

Releaser inputs are Core / Infrastructure / shared Content / branch-specific Injector,
a `stable` or `beta` branch, and independent Build locally / Clean release modes.
Component selection bumps that branch's package version (initial `0.1.0`) and
reads the packaged DLL metadata. Infrastructure passes its package version into
`WORLD_OVERHAUL_PACKAGE_VERSION`; Core uses its binaries' actual resource versions.
Confirm all selected Steam uploads before advertising their catalogue entries.
Publishing Beta runtime packages leaves Stable, launcher metadata and news intact.
Beta publication writes and stages only version-v4.json and its regenerated
version.json projection; it creates no GitHub release.
Publish shared Content and Injector through Stable. All generated Workshop VDFs
use visibility 3, both for local preparation and upload.
Only Injector selection builds/publishes an MSI; Core alone never builds one.

Build locally needs no GitHub/Steam credentials and leaves the hosted catalogue
unchanged. It emits package folders plus `workshop-vdf/<component>-<branch>.vdf`
and a `components.preview.json` containing actual package/DLL metadata. An empty
catalogue ID becomes `0` in a creation VDF and local manifest. After Steam assigns
the item ID, enter it in the catalogue and rebuild; ID-0 packages are not ready
for launcher distribution. The latest local package of each component/branch is
retained; superseded completed packages are pruned, keeping journals and hashes.

The launcher agent owns branch selection, subscriptions, file installation and
readiness. The bootstrap installer contract is `$RELEASE_BRANCH stable|beta` in
its staged injector.ini; normal MSI preservation of an existing INI still applies.
A branch switch must resolve the complete selected catalogue, including older
versions when returning to Stable. Clients that only understand version.json keep
working through the schema 3 projection; a launcher that reads version-v4.json must
prefer it and fall back to version.json only when the sibling file is missing (404),
never when it is present but invalid.

The backup is an HTTPS backend directory ending in `/`,
currently the raw GitHub `main/site/` directory. It is not an alternative download.
The injector saves validated values in injector.ini as `$LATEST_INJECTOR_VERSION`,
`$INJECTOR_DOWNLOAD_URL` and `$BACKUP_BACKEND_URL`. Failed refreshes retain previous
metadata. Version and Workshop requests try the configured backup if the primary
fails or returns invalid data; cancellation does not trigger fallback. The raw
backup shares GitHub infrastructure, so it is not an independent hosting provider.
The launcher release remains an installer update; runtime DLL delivery is through
the selected branch's Workshop packages.

The optional `Bughook` string contains the configured HTTPS bug-report webhook.
It is public feed data, published with the owner's explicit approval. This field
alone does not send reports; launcher report submission is not implemented.
An empty value or absent field means no endpoint configured.

The optional `banner` object reserves a future clickable image banner:

```json
"banner": {
  "enabled": false,
  "img": "",
  "href": "",
  "height": 0
}
```

It is disabled for now. The launcher accepts and validates this metadata; image
rendering and click handling are not implemented yet. `img` and `href` accept
HTTPS URLs or relative backend paths. `height` accepts 0–800 logical pixels;
0 reserves automatic sizing from the image aspect ratio. An enabled banner
requires a nonempty image URL. Older feeds without `banner` remain accepted.

## Editing and publishing

1. Edit the appropriate file under `site/`, either on GitHub or locally. Branch
   data is edited in `version-v4.json`; regenerate `version.json` with
   `--project-legacy` instead of editing the projection separately.
2. For local edits, run `python scripts/validate.py` from the repository root.
3. Commit and push to `main` (or open a pull request first).
4. The **Validate and publish launcher feeds** workflow validates all feeds and
   deploys `site/` only after validation succeeds. Pull requests validate only.
5. Check the workflow result and the published JSON. Pages/CDN caches can take
   a little time to reflect a deployment.

No manual Pages rebuild is needed. Failed validation leaves the last successful
site deployed. Only the `site/` directory goes into the Pages artifact.

## News contract

`news.json` contains `schemaVersion` and an `items` array. Each item requires:

- `id`: stable, unique text identifier.
- `title`: headline.
- `publishedAt`: ISO 8601 timestamp including timezone.
- `summary`: full plain-text body for the launcher news card. Use `\n\n` between paragraphs.
- Optional `articleUrl` and `imageUrl`: absolute HTTPS URLs.

Home displays the title, local publication date and full body below its banner,
newest first, with a separate bordered card for each post. The current launcher
does not render the optional article/image fields. Refresh news reloads this
feed using the configured primary and backup backend; a failed refresh retains
posts already loaded during that launcher session and does not block Play.
Launcher limits: 100 posts, 120 characters per ID, 200 per title, 20,000 per body,
and 1 MiB total feed size. Dates must include time and timezone.

Example item (illustrative, not published):

```json
{
  "id": "railway-development-update",
  "title": "Railway development update",
  "publishedAt": "2026-09-10T12:00:00Z",
  "summary": "A short description of the update."
}
```

Put newest items first. Keep files as valid JSON without comments or trailing commas.

## Update contract

`updates.json` contains `schemaVersion` and a `releases` array. Each record has
`component` (`injector`, `loader`, or `world_overhaul`), `channel` (`stable` or
`testers`), a `version` string, and an HTTPS `releaseUrl`. Keep one current record
per component/channel. An empty array means no advertised update information.

Link injector/Loader releases to GitHub Releases and mod releases to their
appropriate release/Workshop page. This is discovery metadata, not an installer
manifest or evidence of download authenticity. Executable signature and release
integrity verification must remain in the installer/updater implementation.

## Workshop compatibility contract

`workshop.json` contains `schemaVersion`, `requiredWorkshopIds` and
`incompatibleWorkshopIds`. Schema 4 required entries contain an `id` and a `type`
of exactly `"content"`; they have no custom version. Runtime component and branch
injector IDs and versions belong exclusively in version-v4.json. IDs remain
**decimal strings**, preserving uint64 precision. Incompatible entries remain ID
strings. For example (illustrative IDs only):

```json
{
  "schemaVersion": 4,
  "requiredWorkshopIds": [
    {"id": "234567890", "type": "content"}
  ],
  "incompatibleWorkshopIds": []
}
```

The launcher must combine these shared content requirements with the selected
version-v4.json branch's runtime packages, including that branch's injector.
Incompatibility rules remain shared. Reject an ID that is both required and
incompatible, or used as both content and a runtime package; validation rejects
any runtime ID that also appears in either list of `workshop.json`. Backend
validation retains legacy schema 3 support for migration.

Component packages provide a schema-1 manifest.json with matching workshopId,
version and copy-only/update/remove operations. The launcher verifies hashes and
prepares runtime files before allowing Play. Ordinary content provides no custom
manifest; it stays in Workshop and required content is admitted to the whitelist.
Publish the component to Steam and verify availability before updating this feed's
expected package version. Never reuse a release version for changed payload bytes.

- Empty lists declare no rules.
- IDs must be positive uint64 values and unique within a list.
- An ID cannot occur in both lists.
- Add only deliberately established requirements/incompatibilities.
- A mod absent from the incompatible list is not thereby proven compatible.

## Injector configuration

The local launcher INI can point to these feeds:

```ini
$BACKEND_URL "https://presfox.github.io/world-overhaul-backend/"
$VERSION_URL "version.json"
$NEWS_URL "news.json"
$UPDATES_URL "updates.json"
$COMPATIBILITY_URL "workshop.json"
```

For the branch migration, `workshop.json` supplies the shared content and
incompatibility sets; the branch feed supplies the selected branch's component and
injector requirements. A configured `$VERSION_URL` ending in `version.json` names
the legacy projection, so the launcher requests the sibling `version-v4.json` first
and falls back to the configured file only on 404. Custom URLs keep working. The
launcher must keep these sources distinct and prepare their combined requirements
before Play. Branch changes must reconcile component subscriptions and install the
selected versions, including a downgrade when returning from Beta to Stable.

The launcher agent owns the corresponding INI representation, refresh behavior,
Steam subscription/download handling, Core manifest permissions and file update
transaction. These backend changes do not implement or validate those launcher
behaviors. Preserve unrelated preferences and native whitelist selections during
the migration. Reject incomplete branches and retain usable prior configuration
when a response is invalid; never silently substitute another branch.

This public static service does not accept uploads or store private settings.

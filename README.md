# World Overhaul backend

Public news, update information and Workshop compatibility data for the World
Overhaul launcher for **Workers & Resources: Soviet Republic**.

GitHub Pages publishes the contents of `site/`. This repository contains only
the public feed files, their validation and documentation. It does not contain
game files, the injector source, mod binaries, credentials or tester reports.

## Endpoints

| Feed | URL |
| --- | --- |
| Injector version and backup backend | https://presfox.github.io/world-overhaul-backend/version.json |
| News | https://presfox.github.io/world-overhaul-backend/news.json |
| Updates | https://presfox.github.io/world-overhaul-backend/updates.json |
| Workshop requirements and incompatibilities | https://presfox.github.io/world-overhaul-backend/workshop.json |

The earlier `compatibility.json` URL remains a deployment-generated alias of
`workshop.json`. Edit only `site/workshop.json` for Workshop rules.

Workshop rules use `schemaVersion: 3`; the other feeds use version 1. Three Workshop
items are required. No injector download has been published yet.

`version.json` contains `schemaVersion`, `version`, `downloadUrl` and
`backupBackendUrl`. The current injector version is `0.1.0`; an empty download URL
means no downloadable release is advertised. Set it to the actual HTTPS release
asset URL when published. The backup is an HTTPS backend directory ending in `/`,
currently the raw GitHub `main/site/` directory. It is not an alternative download.
The injector saves validated values in injector.ini as `$LATEST_INJECTOR_VERSION`,
`$INJECTOR_DOWNLOAD_URL` and `$BACKUP_BACKEND_URL`. Failed refreshes retain previous
metadata. Version and Workshop requests try the configured backup if the primary
fails or returns invalid data; cancellation does not trigger fallback. The raw
backup shares GitHub infrastructure, so it is not an independent hosting provider.
This is discovery metadata only; it does not trigger an executable update.

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

1. Edit the appropriate file under `site/`, either on GitHub or locally.
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
`incompatibleWorkshopIds`. Required entries contain an `id` and a `type` of
exactly `"component"` or `"content"`. Components also require an exact `version`;
content entries have no custom version. IDs remain **decimal strings**, preserving
uint64 precision. Incompatible entries remain ID strings. For example (illustrative IDs only):

```json
{
  "schemaVersion": 3,
  "requiredWorkshopIds": [
    {"id": "123456789", "type": "component", "version": "1.0.0"},
    {"id": "234567890", "type": "content"}
  ],
  "incompatibleWorkshopIds": []
}
```

The injector preserves types as `$REQUIRED_WORKSHOP_ID 123456789 COMPONENT 1.0.0`
or `$REQUIRED_WORKSHOP_ID 234567890 CONTENT` in `WorldOverhaul/injector.ini`.
Legacy local entries without a type are read as CONTENT. Schema 3 JSON always
requires an explicit type and a component version. Invalid fields reject the
complete update. Type-only and version-only changes update the INI.
Versions are case-sensitive, 1–64 characters: letters, digits, dot, underscore,
plus or hyphen, starting with a letter or digit. Older injectors reject schema 3
and retain their last valid configuration.

Component packages provide a schema-1 manifest.json with matching workshopId,
version and copy-only/update/remove operations. The launcher verifies hashes and
prepares runtime files before allowing Play. Ordinary content provides no custom
manifest; it stays in Workshop and required content is admitted to the whitelist.
Publish the component to Steam and verify availability before updating this feed's
expected version. Never reuse a release version for changed payload bytes.

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

The injector synchronises Workshop rules at startup, during a successful Steam
inventory refresh, and through Settings > Sync Workshop rules. `workshop.json`
is authoritative for the local `$REQUIRED_WORKSHOP_ID` and
`$INCOMPATIBLE_WORKSHOP_ID` lists: additions and removals replace the local sets;
empty arrays clear them. Equal sets do not rewrite the INI. Other preferences,
comments are preserved. Failed requests,
invalid JSON or conflicting file edits retain the previous valid configuration.

The development injector checks subscriptions and completed downloads at startup,
Workshop refresh, preparation retry and before Play. It validates Steam's async
subscription/download results and installed/current state. Exact component
version mismatch requests one update per attempt, then blocks if unresolved.
A configured feed that cannot be refreshed retains the INI but blocks preparation;
an offline bypass is not defined. Required content is added to the whitelist,
preserving its native enable flag and prior selections. Removing a required ID
does not unsubscribe or deselect it. Native hooks remain disabled in development.
News/update retrieval and incompatible-mod classification remain future work.

This public static service does not accept uploads or store private settings.

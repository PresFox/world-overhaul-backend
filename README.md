# World Overhaul backend

Public news, update information and Workshop compatibility data for the World
Overhaul launcher for **Workers & Resources: Soviet Republic**.

GitHub Pages publishes the contents of `site/`. This repository contains only
the public feed files, their validation and documentation. It does not contain
game files, the injector source, mod binaries, credentials or tester reports.

## Endpoints

| Feed | URL |
| --- | --- |
| News | https://presfox.github.io/world-overhaul-backend/news.json |
| Updates | https://presfox.github.io/world-overhaul-backend/updates.json |
| Workshop compatibility | https://presfox.github.io/world-overhaul-backend/compatibility.json |

All feeds use `schemaVersion: 1`. Initial arrays are deliberately empty: there
are no announced releases or active Workshop rules in this initial deployment.

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
- `summary`: plain text for the launcher news card.
- Optional `articleUrl` and `imageUrl`: absolute HTTPS URLs.

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

`compatibility.json` contains `schemaVersion`, `requiredWorkshopIds` and
`incompatibleWorkshopIds`. Both lists contain **decimal strings**, for example
`"123456789"`, preserving uint64 precision across JSON consumers.

- Empty lists declare no rules.
- IDs must be positive uint64 values and unique within a list.
- An ID cannot occur in both lists.
- Add only deliberately established requirements/incompatibilities.
- A mod absent from the incompatible list is not thereby proven compatible.

## Injector configuration

The local launcher INI can point to these feeds:

```ini
$NEWS_URL "https://presfox.github.io/world-overhaul-backend/news.json"
$UPDATES_URL "https://presfox.github.io/world-overhaul-backend/updates.json"
$COMPATIBILITY_URL "https://presfox.github.io/world-overhaul-backend/compatibility.json"
```

The injector currently loads and validates these URL settings. Remote feed
retrieval/display and Workshop rule enforcement are not implemented yet.
Before implementing them, define how remote compatibility lists combine with
local INI rules. The hosted lists do not change a player's Steam subscriptions.

This public static service does not accept uploads or store private settings.

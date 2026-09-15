# Branch catalogue (schema 3)

version.json now holds a shared injector release plus branches.stable.components
and branches.beta.components. Each component contains workshopId (decimal string),
version (package version), and dlls ({path, version, sha256}). DLL paths are relative
to WorldOverhaul and versions are embedded PE file versions. Preserve banner,
Bughook, backupBackendUrl and shared launcher fields during component publication.

A branch whose component package versions are all empty is unreleased/unavailable.
Do not fall back to another branch. Initial publication must select both Core and
Infrastructure so the complete branch receives verified package and DLL metadata.
Once active, every component must have complete versions and SHA-256 hashes.

The initial migration registers the assigned IDs without claiming old creation
packages are ready: those initial manifests used workshopId 0. The next release
builds and uploads corrected packages before advertising their versions.

Stable: Core 3802122646; Infrastructure 3799262663.
Beta: Core 3802125089; Infrastructure 3802125843.

Beta publication changes only version.json and creates no GitHub release or news
post. Workshop VDF visibility is 3. workshop.json schema 4 contains only shared
content requirements and incompatibilities. Launcher implementation is separate.

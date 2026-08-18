# piphi-nework-registry

Public PiPhi registry catalog consumed by the Registry API.

Want to submit a new integration? Use the `Submit Integration` issue form and see [CONTRIBUTING.md](./CONTRIBUTING.md).

Submission issues are validated automatically by GitHub Actions before they move to human review.

Maintainer review guidance lives in [REVIEWING.md](./REVIEWING.md).

Approved submissions can also generate a proposed registry entry automatically to speed up publication.

Existing entries can be synchronized with their source manifests through the
`Sync Registry Entry` GitHub Actions workflow. That workflow is intended for
developers and maintainers who want a safer alternative to manually editing
`registry.json` when a published integration version changes.

Recommended developer flow:
- run `Sync Registry Entry`
- choose the existing `registry_id`
- optionally provide a repository override, manifest path override, or release tag
- let the workflow open or update a pull request with the registry changes

If the source integration repositories are private, configure a repository
secret named `REGISTRY_SOURCE_GITHUB_TOKEN` with read access to those
repositories. The sync workflow falls back to the default `GITHUB_TOKEN` for
public repositories.

The repository must also allow GitHub Actions to create pull requests under
Settings > Actions > General > Workflow permissions.

Current contract:
- `registry.json` lives at the repository root
- it contains a JSON array of registry entries
- each entry points to a plugin/integration repository and its manifest path
- `deployment_mode` can distinguish normal installs from sidecars/helpers
- `trust_level` shows how PiPhi classifies publisher trust
- `risk_level` shows the operational sensitivity of the package
- `image` is the runtime/container image reference when applicable
- `icon_url` is the catalog icon artwork
- `banner_url` can be used later for larger catalog artwork
- `runtime_requirements` summarizes notable runtime requirements and privileges
- `marketplace.metadata_version` is `2` for every published listing and carries
  authoritative homeowner copy, compatibility, connectivity, access, discovery,
  regional, language, publisher, support, privacy, and release metadata

Starter entries have been added for:
- Atmotube Pro (BLE)
- Awair Element (Local API)
- Official PiPhi Network GPS Integration
- TP-Link Kasa (Local API)
- LG ThinQ Connect
- PiPhi Network 433MHz Devices
- MQTT Broker
- Zigbee2MQTT Sidecar

Assets:
- shared placeholder icon: `icons/placeholder.svg`
- Atmotube icon: `icons/atmotube.svg`
- Awair icon: `icons/awair.svg`
- GPS icon: `icons/gps.svg`
- TP-Link Kasa icon: `icons/tp-link-kasa.svg`
- LG ThinQ icon: `icons/lg-thinq.svg`
- 433MHz icon: `icons/rtl433.svg`
- MQTT sidecar icon: `icons/mqtt-sidecar.svg`
- Zigbee2MQTT sidecar icon: `icons/zigbee2mqtt.svg`
- Tuya icon: `icons/tuya.svg`

## Registry-hosted brand icons

### Developer-packaged artwork

New integrations should ship PNG artwork in a `brand/` directory beside their
manifest. For the standard `src/manifest.json` layout, the registry records
`"brand_path": "src/brand"`. PiPhi Core retrieves these files from the selected
release, validates and caches them locally, and serves them to the App Store from
the Core origin. Supported filenames are `icon.png`, `icon@2x.png`, `logo.png`,
`logo@2x.png`, plus corresponding `dark_` variants.

The registry `icon_url` remains a compatibility fallback for older integrations
that have not yet packaged their own artwork.

Brand artwork may be synchronized into `icons/brands/` for entries that declare
`marketplace.brand_domain`. The App Store then consumes the registry-hosted
`icon_url`, so globally distributed PiPhi installations do not share a browser-side
Brandfetch quota or require Brandfetch to be available in the home.

The `Refresh Brand Icons` workflow is deliberately disabled until the repository
has both of the following configuration values:

- repository variable `BRANDFETCH_CACHE_ALLOWED=true`, set only after the account's
  Brandfetch agreement permits caching or self-hosting;
- repository secret `BRANDFETCH_API_KEY`, used by the authenticated Brand API.

The public Logo API client ID is not sufficient for registry synchronization.
When enabled, the workflow refreshes artwork on the 1st and 15th of each month,
records its refresh timestamp and SHA-256 digest in `registry.json`, validates the
result, and opens or updates a reviewable pull request. A failed refresh leaves the
currently published registry icons unchanged.

Run the same process locally only after cache rights are confirmed:

```bash
BRANDFETCH_CACHE_ALLOWED=true \
BRANDFETCH_API_KEY=... \
GITHUB_REPOSITORY=PiPhi-io/piphi-nework-registry \
python scripts/sync_brandfetch_icons.py
```

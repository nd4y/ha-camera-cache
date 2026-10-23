# Camera Cache for Home Assistant

Instant snapshot previews from **one frame in RAM**, refreshed in the background.
An optional dashboard card shows the displayed frame's age and an explicit stale
warning. No video archive, new credentials, external service or extra port.

[![HACS custom integration](https://img.shields.io/badge/HACS-Custom%20integration-blue.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=nd4y&repository=ha-camera-cache&category=integration)
[![Checks](https://github.com/nd4y/ha-camera-cache/actions/workflows/check.yml/badge.svg)](https://github.com/nd4y/ha-camera-cache/actions/workflows/check.yml)

## Install with HACS

Requires Home Assistant **2026.9.0 or later** and an existing camera that provides
JPEG or PNG snapshots. Local and cloud camera integrations can both be sources.

1. Open the HACS badge, or add `https://github.com/nd4y/ha-camera-cache` under
   HACS > Custom repositories with category **Integration**.
2. Download Camera Cache and restart Home Assistant when requested by HACS.
3. Settings > Devices & services > Add integration > **Camera Cache**.
4. Choose the source camera, an optional display name and timing settings.

Each source can have its own cache. The default interval is **3 seconds**, stale
threshold **6 seconds**, and timeout **10 seconds**. The source is selected in the
native UI; no personal entity IDs, URLs or provider accounts are bundled.
Registered source entities are followed through entity-ID renames. A deleted
source is never silently replaced by a new entity with the same name.

## Dashboard card

The integration registers its bundled card automatically for storage-mode
Lovelace resources. Add **Camera Cache** from the card picker and select the
cached camera. The original source is used automatically by **Live view**;
`live_entity` can override it.

```yaml
type: custom:camera-cache-card
entity: camera.your_cached_camera
name: Entrance
```

`entity` is the only required setting. Optional: `name`, `live_entity`,
`language` (`en` or `ru`; otherwise follows HA). The visual editor provides
camera selectors. Colors and spacing follow the active HA theme.

With YAML-mode Lovelace resources, add this module once:

```yaml
resources:
  - url: /camera_cache_static/camera-cache-card.js?v=0.1.0
    type: module
```

After an upgrade, update the version suffix yourself in YAML mode. In storage
mode the integration updates its own versioned resource automatically. Refresh
open dashboards after upgrading so they load the new JavaScript.

## Behavior and limits

- A preview request returns existing bytes immediately and never waits for the
  source. Refreshes run independently, with no overlapping requests or backlog.
- Failed, timed-out, unsupported or oversized snapshots do not replace the last
  good frame. Retries back off, up to the larger of 30 seconds or the configured
  interval. No exception message containing a provider URL is exposed.
- The previous image remains visible while its replacement loads. Age belongs
  to the displayed image. Errors and elapsed stale thresholds show a warning.
- HA timestamps are anchored to browser monotonic time, so a phone/server wall
  clock difference does not produce false warnings. On initial connection the
  age estimate can differ by one state-update interval; it keeps aging if state
  updates stop.
- Cold start after restart, disable, unload or power loss needs one source
  snapshot before a preview exists. Images are bounded to 2 MiB per cache.
- Frames are not written to files, `www`, recorder or Frigate. Ordinary entity
  status metadata may be retained by HA recorder. Existing browser image caching
  remains governed by HA's camera endpoint.
- Snapshots use the standard authenticated HA camera proxy. The public static
  endpoint serves only the secret-free card code. No network or account
  permissions are added.
- A cloud source still makes periodic requests to its provider. This integration
  does not provide an independent video stream or enable/disable recording in
  any other integration. **Live view** opens the original camera through HA.
- Changing options reloads only that cache and clears its old in-memory frame.
  Removing the integration entry stops its own worker. Source cameras and their
  settings remain unchanged.

## Updates and removal

HACS tracks published GitHub releases, downloads the integration and bundled card
together, and exposes its normal update entity. After an integration update,
restart HA if prompted; the resource version is synchronized at startup.
To remove a cache, remove its entry in Devices & services. Remove cards that used
it. Once all cache entries and cards are removed, uninstall the repository in
HACS and remove `/camera_cache_static/...` from dashboard resources if retained.

This is a **custom repository**, not a claim of inclusion in the default HACS
catalogue or official HA certification.

## Development

CI runs pure cache/configuration tests, real HA adapter/config-flow/resource
tests, browser failure/recovery and clock-skew tests, privacy checks and release
packaging. Tests use synthetic snapshots only. Production camera frames,
credentials, installation backups and private diagnostics are excluded.

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/test_memory_card.mjs
# Browser dependency: playwright-core@1.64.0, matching the CI container.
node tests/test_memory_browser.mjs "$PWD" /path/to/browser-tools
python scripts/package.py
```

Releases are built by the release workflow from a tag on the default branch,
after all checks pass. The ZIP and checksums contain only integration runtime
files. License: MIT.

## По-русски

Добавьте репозиторий в HACS как **Integration**, установите и перезапустите HA.
Затем добавьте интеграцию **Camera Cache**, выберите исходную камеру и интервал.
Карточка **Camera Cache** показывает последний кадр, его возраст и предупреждение
об устаревании. Кадр хранится в памяти, без видеоархива. Настройки доступны через
кнопку «Настроить» интеграции; обновления приходят через HACS.

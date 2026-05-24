# Production Readiness

This registry is the control surface for deciding whether an integration or sidecar is ready to publish, install from Core, and support in production.

## Definition of Done

An integration or sidecar is production ready when all of these are true:

- The manifest version, registry version, and image tag match.
- Every runtime image is explicitly tagged; no floating production images.
- CI runs tests, compile/type checks, manifest JSON validation, and Docker build checks when a Dockerfile exists.
- The runtime implements the PiPhi contract routes declared in its manifest.
- `/health` reports dependency status, last successful sync, last error, and stale data state.
- `/diagnostics` redacts API tokens, passwords, client secrets, serial credentials, and broker credentials.
- Config apply, config sync, deconfigure, and reinstall flows are covered by tests.
- Cloud integrations handle rate limits, auth failures, retries, and token expiry safely.
- Hardware integrations document required host privileges and have a real-device smoke test result.
- Sidecars document host mounts, device access, restart behavior, and rollback behavior.
- The package installs from the registry into PiPhi Core and survives a restart/reconfigure cycle.

## Release Gates

Before publishing a stable tag:

- Run the repo test suite locally.
- Run the repo CI workflow on GitHub.
- Run `python scripts/validate_registry.py registry.json` in this registry repo.
- Use the registry sync workflow after each integration release.
- Record hardware/API smoke test notes in the integration release notes.

## Current Work Queue

| Package | Type | Remaining production work |
| --- | --- | --- |
| Awair Element | integration | Registry synced to `0.1.8`; confirm release image exists and run local-network smoke test. |
| 433MHz Devices | integration | Registry synced to `0.1.4`; confirm RTL-SDR smoke test and Core install flow. |
| rtl_433 Bridge | sidecar | Registry synced to `0.1.2`; confirm Docker image and host radio permissions. |
| Zigbee2MQTT Sidecar | sidecar | Registry synced to `0.1.1`; add hardware smoke results for USB and network coordinators. |
| MQTT Broker | sidecar | CI added; add release workflow and broker auth/TLS production profile. |
| Matter Sidecar | sidecar | Image tag pinned; finish adapter implementation checks and commissioning smoke test. |
| GPS | integration | CI added; confirm package changes, Docker image tag, and USB device smoke test. |
| ThinQ Connect | integration | CI added; resolve dirty changes and verify token/error handling. |
| TP-Link Kasa | integration | CI added; resolve dirty changes and verify local discovery/control smoke test. |
| Airthings Consumer Cloud | integration | Added to registry; verify API credentials, rate limits, and stale-data health. |
| Aqara Open API | integration | Added to registry; verify cloud auth, event/state mapping, and rate limits. |
| Tesla EV | integration | Added to registry; add release workflow and verify Fleet API auth/wake-up flows. |
| Kaiterra API | integration | Added to registry; image tag aligned to `0.1.1`; verify cloud API smoke test. |
| WeatherXM | integration | Added to registry; verify whether this or WeatherXM API is the canonical package. |
| WeatherXM API | integration | Added to registry; verify whether this or WeatherXM is the canonical package. |
| Atmotube Pro BLE | integration | CI added; add release workflow/package artifact and BLE smoke tests. |
| Airthings BLE | integration | Registry entry remains, but no matching local repo is present; either restore repo or retire entry. |

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
| Awair Element | integration | Release `0.1.13` published; run the local-network hardware smoke test. |
| 433MHz Devices | integration | Release `0.1.7` published; confirm RTL-SDR smoke test and Core install flow. |
| rtl_433 Bridge | sidecar | Registry synced to `0.1.2`; confirm Docker image and host radio permissions. |
| Zigbee2MQTT Sidecar | sidecar | Release `0.1.12` published; add hardware smoke results for USB and network coordinators. |
| Zigbee | integration | Release `0.1.9` published; add coordinator and device-pairing smoke results. |
| MQTT Broker | sidecar | CI added; add release workflow and broker auth/TLS production profile. |
| Matter Sidecar | sidecar | Prerelease `0.2.0-alpha.2` published; finish commissioning and fabric-lifecycle smoke tests before stable promotion. |
| GPS | integration | Release `1.1.2` published; complete the USB-device smoke test. |
| ThinQ Connect | integration | Release `0.1.11` published; verify token expiry and appliance-control error handling. |
| TP-Link Kasa | integration | Release `0.1.12` published; verify discovery, externally changed state, and local control. |
| Airthings Consumer Cloud | integration | Release and experience package `0.1.7` published; verify credentials, rate limits, and stale-data health. |
| Aqara Open API | integration | Release `0.1.3` published; verify cloud auth, event/state mapping, and rate limits. |
| Tesla EV | integration | Release `0.2.3` published; verify Fleet API auth and wake-up flows. |
| Kaiterra API | integration | Release `0.1.5` published with corrected image metadata; verify the cloud API smoke test. |
| WeatherXM | integration | Release `0.1.4` published; verify whether this or WeatherXM API is the canonical package. |
| I2C | integration | Release `0.1.3` published; complete representative sensor hardware smoke tests. |
| SPI | integration | Release `0.1.3` published; complete representative peripheral hardware smoke tests. |
| Tuya | integration | Release `0.1.4` published; verify cloud auth, state refresh, and command confirmation. |
| Sense | integration | Release `0.1.2` published; verify live monitor reconnect and stale-data behavior. |
| WeatherXM API | integration | Added to registry; verify whether this or WeatherXM is the canonical package. |
| Atmotube Pro BLE | integration | CI added; add release workflow/package artifact and BLE smoke tests. |
| Airthings BLE | integration | Registry entry remains, but no matching local repo is present; either restore repo or retire entry. |

#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

VALID_ENTRY_TYPES = {"integration", "platform_service"}
VALID_DEPLOYMENT_MODES = {"standalone", "sidecar"}
VALID_PLATFORMS = {"linux", "windows", "macos"}
REQUIRED_FIELDS = {
    "id",
    "name",
    "version",
    "type",
    "trust_level",
    "risk_level",
    "description",
    "platforms",
    "owner",
    "repo_name",
    "repo_url",
    "manifest_path",
    "maintainer",
}
IMAGE_WITH_TAG = re.compile(r"^(?:[a-z0-9.-]+(?::[0-9]+)?/)?[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9._-]+$")


def load_entries(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("registry.json must contain a JSON array")
    return payload


def validate_entry(entry: dict[str, Any], index: int) -> list[str]:
    prefix = f"entry[{index}] {entry.get('id', '<missing-id>')}"
    errors: list[str] = []

    missing = sorted(field for field in REQUIRED_FIELDS if field not in entry)
    for field in missing:
        errors.append(f"{prefix}: missing required field {field}")

    entry_type = entry.get("type")
    if entry_type not in VALID_ENTRY_TYPES:
        errors.append(f"{prefix}: type must be one of {sorted(VALID_ENTRY_TYPES)}")

    deployment_mode = entry.get("deployment_mode", "standalone")
    if deployment_mode not in VALID_DEPLOYMENT_MODES:
        errors.append(f"{prefix}: deployment_mode must be one of {sorted(VALID_DEPLOYMENT_MODES)}")
    if entry_type == "platform_service" and deployment_mode != "sidecar":
        errors.append(f"{prefix}: platform_service entries must set deployment_mode=sidecar")

    platforms = entry.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        errors.append(f"{prefix}: platforms must be a non-empty list")
    else:
        invalid = sorted(str(platform) for platform in platforms if platform not in VALID_PLATFORMS)
        if invalid:
            errors.append(f"{prefix}: invalid platforms {invalid}")

    image = entry.get("image")
    if image and not IMAGE_WITH_TAG.match(str(image)):
        errors.append(f"{prefix}: image must include an explicit tag, got {image!r}")

    maintainer = entry.get("maintainer")
    if not isinstance(maintainer, dict) or not maintainer.get("name"):
        errors.append(f"{prefix}: maintainer.name is required")

    return errors


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "registry.json")
    entries = load_entries(path)
    errors: list[str] = []
    seen: set[str] = set()

    for index, entry in enumerate(entries):
        entry_id = str(entry.get("id") or "").strip()
        if not entry_id:
            errors.append(f"entry[{index}]: id is required")
        elif entry_id in seen:
            errors.append(f"entry[{index}] {entry_id}: duplicate id")
        seen.add(entry_id)
        errors.extend(validate_entry(entry, index))

    if errors:
        print("Registry validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Registry validation passed for {len(entries)} entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

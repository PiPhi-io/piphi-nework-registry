#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from marketplace_metadata import validate_marketplace_v2

VALID_ENTRY_TYPES = {"integration", "platform_service", "widget"}
VALID_DEPLOYMENT_MODES = {"standalone", "sidecar"}
VALID_PLATFORMS = {"linux", "windows", "macos", "web"}
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
BRAND_DOMAIN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
SHA256 = re.compile(r"^[a-f0-9]{64}$")
ARTIFACT_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


def valid_package_path(value: object) -> bool:
    candidate = str(value or "").strip()
    if not candidate or candidate.startswith(("/", "\\")) or "\\" in candidate:
        return False
    parts = candidate.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


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
    if entry_type == "widget" and deployment_mode != "standalone":
        errors.append(f"{prefix}: widget entries must use standalone deployment mode")

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

    artifact = entry.get("artifact")
    if entry_type == "widget":
        if not isinstance(artifact, dict):
            errors.append(f"{prefix}: widget artifact must be an object")
        else:
            if not valid_package_path(artifact.get("release_asset")):
                errors.append(f"{prefix}: widget artifact.release_asset must be a safe package filename")
            manifest_asset = artifact.get("manifest_asset")
            if manifest_asset is not None and not valid_package_path(manifest_asset):
                errors.append(f"{prefix}: widget artifact.manifest_asset must be a safe package filename")
            integrity = str(artifact.get("integrity") or "").strip()
            governance = (entry.get("marketplace") or {}).get("governance") if isinstance(entry.get("marketplace"), dict) else {}
            is_draft = isinstance(governance, dict) and governance.get("publication_status") == "draft" and governance.get("rollout_percent") == 0
            if not integrity and not is_draft:
                errors.append(f"{prefix}: published widget artifact.integrity is required")
            elif integrity and not ARTIFACT_DIGEST.fullmatch(integrity):
                errors.append(f"{prefix}: widget artifact.integrity must be sha256:<64 lowercase hex characters>")

    brand_path = entry.get("brand_path")
    if brand_path is not None and not valid_package_path(brand_path):
        errors.append(f"{prefix}: brand_path must be a safe relative package path")

    maintainer = entry.get("maintainer")
    if not isinstance(maintainer, dict) or not maintainer.get("name"):
        errors.append(f"{prefix}: maintainer.name is required")

    marketplace = entry.get("marketplace")
    for error in validate_marketplace_v2(marketplace, entry_type=str(entry_type or "")):
        errors.append(f"{prefix}: {error}")
    if isinstance(marketplace, dict):
        brand_domain = str(marketplace.get("brand_domain") or "").strip()
        if brand_domain and not BRAND_DOMAIN.fullmatch(brand_domain):
            errors.append(f"{prefix}: marketplace.brand_domain is invalid")
        icon_source = str(marketplace.get("icon_source") or "").strip()
        if icon_source and icon_source != "brandfetch":
            errors.append(f"{prefix}: marketplace.icon_source must be brandfetch when set")
        if icon_source == "brandfetch":
            if not brand_domain:
                errors.append(f"{prefix}: Brandfetch icons require marketplace.brand_domain")
            if not str(marketplace.get("icon_refreshed_at") or "").strip():
                errors.append(f"{prefix}: Brandfetch icons require marketplace.icon_refreshed_at")
            if not SHA256.fullmatch(str(marketplace.get("icon_sha256") or "")):
                errors.append(f"{prefix}: Brandfetch icons require a valid marketplace.icon_sha256")

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

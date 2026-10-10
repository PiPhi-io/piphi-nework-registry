#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from marketplace_metadata import validate_marketplace_v2
from submission_utils import fetch_manifest_from_github, load_registry_entries, parse_repo_url


SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Propose a reviewed integration or widget registry update.")
    parser.add_argument("--registry-id", required=True)
    parser.add_argument("--entry-type", choices=("integration", "widget"), required=True)
    parser.add_argument("--repo-url", required=True)
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--artifact-integrity", default="")
    parser.add_argument("--registry-path", default="registry.json")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def widget_marketplace(source: dict[str, Any], repo_url: str) -> dict[str, Any]:
    supplied = source.get("marketplace")
    if isinstance(supplied, dict):
        return supplied
    identity = source.get("identity") if isinstance(source.get("identity"), dict) else {}
    name = str(source.get("name") or identity.get("package_id") or "Widget").strip()
    widgets = source.get("widgets") if isinstance(source.get("widgets"), list) else []
    capabilities: list[str] = []
    for widget in widgets:
        if not isinstance(widget, dict):
            continue
        slots = widget.get("binding_slots") if isinstance(widget.get("binding_slots"), list) else []
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            for capability in slot.get("capability_requirements") or []:
                value = str(capability).strip()
                if value and value not in capabilities:
                    capabilities.append(value)
    sdk_range = str(source.get("sdk_version_range") or ">=0.6.1,<0.7").strip()
    owner, _ = parse_repo_url(repo_url)
    return {
        "metadata_version": 2,
        "display_name": name,
        "summary": str(source.get("description") or f"{name} dashboard widgets.").strip(),
        "category": "other",
        "regions": ["WW"],
        "languages": ["en"],
        "publisher": {
            "name": owner,
            "website_url": repo_url,
            "support_url": f"{repo_url}/issues",
            "security_contact": "support@piphi.io",
        },
        "access": [],
        "compatibility": [
            {"capability": capability, "host_protocol": "piphi.widget.host/1", "widget_sdk": sdk_range}
            for capability in (capabilities or ["custom"])
        ],
        "documentation_url": repo_url,
        "support_url": f"{repo_url}/issues",
        "changelog_url": f"{repo_url}/releases",
        "quality_tier": "unrated",
        "governance": {
            "schema_version": 1,
            "publication_status": "draft",
            "rollout_percent": 0,
            "lifecycle_status": "active",
            "qualification": {"status": "unverified"},
        },
    }


def widget_entry(
    source: dict[str, Any], repo_url: str, manifest_path: str, ref: str, integrity: str
) -> dict[str, Any]:
    identity = source.get("identity") if isinstance(source.get("identity"), dict) else {}
    publisher_id = str(identity.get("publisher_id") or "").strip()
    package_id = str(identity.get("package_id") or "").strip()
    version = str(identity.get("version") or "").strip()
    registry_id = f"{publisher_id}.{package_id}"
    owner, repo_name = parse_repo_url(repo_url)
    if ref != f"v{version}":
        raise ValueError(f"Release ref '{ref}' must match widget version v{version}.")
    if integrity and not SHA256.fullmatch(integrity):
        raise ValueError("Widget artifact integrity must be sha256:<64 lowercase hex characters>.")
    marketplace = widget_marketplace(source, repo_url)
    errors = validate_marketplace_v2(marketplace, entry_type="widget")
    if errors:
        raise ValueError("Widget marketplace metadata is invalid: " + "; ".join(errors))
    return {
        "id": registry_id,
        "name": str(source.get("name") or package_id).strip(),
        "version": version,
        "type": "widget",
        "deployment_mode": "standalone",
        "trust_level": "official" if owner == "PiPhi-io" else "community",
        "risk_level": "low",
        "description": str(source.get("description") or "").strip(),
        "rewardable": False,
        "platforms": ["web"],
        "owner": owner,
        "repo_name": repo_name,
        "repo_url": repo_url,
        "ref": ref,
        "manifest_path": manifest_path,
        "artifact": {
            "release_asset": f"{package_id}-{version}.zip",
            "manifest_asset": f"{package_id}-{version}.manifest.json",
            "integrity": integrity or None,
        },
        "tags": [package_id, "dashboard", "widget-sdk"],
        "runtime_requirements": [],
        "maintainer": {
            "name": "PiPhi Network" if owner == "PiPhi-io" else owner,
            "website": repo_url,
            "support_email": "support@piphi.io",
        },
        "marketplace": marketplace,
    }


def integration_image(source: dict[str, Any]) -> str:
    direct = str(source.get("image") or "").strip()
    if direct:
        return direct
    runtime = source.get("runtime") if isinstance(source.get("runtime"), dict) else {}
    for target in runtime.values():
        if not isinstance(target, dict):
            continue
        container = target.get("container") if isinstance(target.get("container"), dict) else {}
        image = str(container.get("image") or "").strip()
        if image:
            return image
    return ""


def integration_entry(source: dict[str, Any], repo_url: str, manifest_path: str, ref: str) -> dict[str, Any]:
    registry_id = str(source.get("id") or "").strip()
    version = str(source.get("version") or "").strip()
    if ref != f"v{version}":
        raise ValueError(f"Release ref '{ref}' must match integration version v{version}.")
    marketplace = source.get("marketplace")
    errors = validate_marketplace_v2(marketplace, entry_type="integration")
    if errors:
        raise ValueError("Integration marketplace metadata is invalid: " + "; ".join(errors))
    owner, repo_name = parse_repo_url(repo_url)
    deployment = str(source.get("deployment_mode") or "standalone").strip()
    requirements = source.get("runtime_requirements") if isinstance(source.get("runtime_requirements"), list) else []
    high = {"privileged_container", "host_networking", "host_filesystem_mounts"}
    risk = "high" if any(item in high for item in requirements) else "moderate" if deployment == "sidecar" or requirements else "low"
    entry: dict[str, Any] = {
        "id": registry_id,
        "name": str(source.get("name") or "").strip(),
        "version": version,
        "type": "platform_service" if deployment == "sidecar" else "integration",
        "trust_level": "official" if owner == "PiPhi-io" else "community",
        "risk_level": risk,
        "description": str(source.get("description") or "").strip(),
        "rewardable": False,
        "platforms": source.get("platforms") or ["linux"],
        "owner": owner,
        "repo_name": repo_name,
        "repo_url": repo_url,
        "ref": ref,
        "manifest_path": manifest_path,
        "runtime_requirements": requirements,
        "maintainer": source.get("maintainer") or {"name": owner, "website": repo_url},
        "marketplace": marketplace,
    }
    if deployment == "sidecar":
        entry["deployment_mode"] = "sidecar"
    image = integration_image(source)
    if image:
        entry["image"] = image
    return entry


def preserve_reviewed_fields(entry: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    if not existing:
        return entry
    for field in ("trust_level", "rewardable", "icon_url", "banner_url"):
        if field in existing:
            entry[field] = existing[field]
    old_marketplace = existing.get("marketplace")
    new_marketplace = entry.get("marketplace")
    if isinstance(old_marketplace, dict) and isinstance(new_marketplace, dict):
        for field in ("quality_tier", "governance"):
            if field in old_marketplace:
                new_marketplace[field] = old_marketplace[field]
    return entry


def main() -> int:
    args = parse_args()
    registry_path = Path(args.registry_path).resolve()
    entries = load_registry_entries(registry_path)
    source, resolved_ref = fetch_manifest_from_github(
        repo_url=args.repo_url,
        manifest_path=args.manifest_path,
        token=os.getenv("GITHUB_TOKEN"),
        ref=args.ref,
    )
    entry = (
        widget_entry(source, args.repo_url, args.manifest_path, args.ref, args.artifact_integrity)
        if args.entry_type == "widget"
        else integration_entry(source, args.repo_url, args.manifest_path, args.ref)
    )
    if entry["id"] != args.registry_id:
        raise ValueError(f"Resolved manifest id '{entry['id']}' does not match requested id '{args.registry_id}'.")
    existing_index = next((index for index, item in enumerate(entries) if item.get("id") == args.registry_id), None)
    existing = entries[existing_index] if existing_index is not None else None
    if existing and not isinstance(source.get("marketplace"), dict) and isinstance(existing.get("marketplace"), dict):
        entry["marketplace"] = existing["marketplace"]
    entry = preserve_reviewed_fields(entry, existing)
    if existing_index is None:
        entries.append(entry)
    else:
        entries[existing_index] = entry
    if args.dry_run:
        print(json.dumps(entry, indent=2))
        return 0
    registry_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    outputs = {
        "registry_id": args.registry_id,
        "version": entry["version"],
        "source_ref": resolved_ref,
        "operation": "update" if existing is not None else "add",
        "branch_name": "automation/propose-" + re.sub(r"[^a-z0-9-]+", "-", args.registry_id.lower()).strip("-"),
        "commit_message": f"registry: propose {args.registry_id} v{entry['version']}",
        "pr_title": f"registry: propose {args.registry_id} v{entry['version']}",
    }
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")
    print(f"{outputs['operation']} {args.registry_id} v{entry['version']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"propose_registry_entry.py failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

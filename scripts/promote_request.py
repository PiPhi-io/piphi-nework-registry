#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from submission_utils import fetch_manifest_from_github, load_registry_entries, parse_repo_url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote a Core request JSON file into registry.json.")
    parser.add_argument("--request-path", required=True, help="Path to requests/*.json.")
    parser.add_argument("--registry-path", default="registry.json", help="Path to registry.json.")
    parser.add_argument("--dry-run", action="store_true", help="Print the generated entry without writing files.")
    return parser.parse_args()


def normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        token = str(item or "").strip().lower()
        if token and token not in normalized:
            normalized.append(token)
    return normalized


def image_repository(image: str) -> str:
    cleaned = str(image or "").strip()
    if not cleaned:
        return ""
    if "@" in cleaned:
        cleaned = cleaned.split("@", 1)[0]
    last_slash = cleaned.rfind("/")
    last_colon = cleaned.rfind(":")
    if last_colon > last_slash:
        return cleaned[:last_colon]
    return cleaned


def infer_manifest_image_repository(manifest: dict[str, Any]) -> str | None:
    top_level = image_repository(str(manifest.get("image") or ""))
    if top_level:
        return top_level
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        return None
    discovered: set[str] = set()
    for target in runtime.values():
        if not isinstance(target, dict):
            continue
        container = target.get("container")
        if not isinstance(container, dict):
            continue
        image = image_repository(str(container.get("image") or ""))
        if image:
            discovered.add(image)
    if len(discovered) == 1:
        return next(iter(discovered))
    return None


def default_icon_url(deployment_mode: str) -> str:
    icon_name = "mqtt-sidecar.svg" if deployment_mode == "sidecar" else "placeholder.svg"
    return f"https://raw.githubusercontent.com/PiPhi-io/piphi-nework-registry/main/icons/{icon_name}"


def build_entry(request: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    proposed = request.get("proposed_registry_entry")
    if not isinstance(proposed, dict):
        raise ValueError("Request does not include a proposed_registry_entry object.")

    repo_url = str(proposed.get("repo_url") or request.get("repo_url") or "").strip()
    if not repo_url:
        raise ValueError("Request does not include a GitHub repository URL.")
    owner, repo_name = parse_repo_url(repo_url)
    deployment_mode = str(proposed.get("deployment_mode") or "standalone").strip() or "standalone"
    manifest_platforms = normalize_list(manifest.get("platforms"))
    proposed_platforms = normalize_list(proposed.get("platforms"))
    platforms = manifest_platforms or proposed_platforms
    if not platforms:
        raise ValueError("Manifest or proposed entry must define supported platforms.")

    maintainer = proposed.get("maintainer")
    if not isinstance(maintainer, dict):
        maintainer = {}
    manifest_maintainer = manifest.get("maintainer")
    if isinstance(manifest_maintainer, dict):
        maintainer = {**maintainer, **{key: value for key, value in manifest_maintainer.items() if value}}
    maintainer.setdefault("name", "Community")

    entry: dict[str, Any] = {
        "id": str(manifest.get("id") or proposed.get("id") or "").strip(),
        "name": str(manifest.get("name") or proposed.get("name") or request.get("brand") or "").strip(),
        "version": str(manifest.get("version") or proposed.get("version") or "").strip(),
        "type": str(proposed.get("type") or "integration").strip(),
        "trust_level": str(proposed.get("trust_level") or "community").strip(),
        "risk_level": str(proposed.get("risk_level") or "moderate").strip(),
        "description": str(
            manifest.get("description")
            or proposed.get("description")
            or request.get("notes")
            or f"Community requested plugin for {request.get('brand') or 'a smart home device'}."
        ).strip(),
        "rewardable": bool(proposed.get("rewardable") or False),
        "platforms": platforms,
        "icon_url": str(proposed.get("icon_url") or default_icon_url(deployment_mode)).strip(),
        "owner": owner,
        "repo_name": repo_name,
        "repo_url": repo_url,
        "manifest_path": str(proposed.get("manifest_path") or "src/manifest.json").strip(),
        "tags": normalize_list(proposed.get("tags")) or normalize_list([request.get("category"), request.get("brand")]),
        "runtime_requirements": normalize_list(proposed.get("runtime_requirements")),
        "maintainer": maintainer,
    }
    if deployment_mode != "standalone":
        entry["deployment_mode"] = deployment_mode

    image = infer_manifest_image_repository(manifest)
    if image:
        entry["image"] = image

    required = ["id", "name", "version", "type", "description", "owner", "repo_name", "repo_url", "manifest_path"]
    missing = [field for field in required if not str(entry.get(field) or "").strip()]
    if missing:
        raise ValueError(f"Generated registry entry is missing required fields: {', '.join(missing)}")
    return entry


def write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def main() -> int:
    args = parse_args()
    request_path = Path(args.request_path)
    registry_path = Path(args.registry_path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise ValueError("Request file must contain a JSON object.")

    proposed = request.get("proposed_registry_entry")
    if not isinstance(proposed, dict):
        raise ValueError("Request file must include proposed_registry_entry to promote.")

    repo_url = str(proposed.get("repo_url") or request.get("repo_url") or "").strip()
    manifest_path = str(proposed.get("manifest_path") or "src/manifest.json").strip()
    manifest, resolved_ref = fetch_manifest_from_github(
        repo_url=repo_url,
        manifest_path=manifest_path,
        token=os.getenv("GITHUB_TOKEN"),
    )
    entry = build_entry(request, manifest)
    entries = load_registry_entries(registry_path)
    entry_id = str(entry["id"])
    if any(str(existing.get("id") or "").strip() == entry_id for existing in entries):
        raise ValueError(f"Registry entry '{entry_id}' already exists.")

    entries.append(entry)
    entries.sort(key=lambda item: str(item.get("name") or item.get("id") or "").lower())
    request["status"] = "converted"
    request["registry_entry_id"] = entry_id
    request["converted_at"] = datetime.now(timezone.utc).isoformat()

    write_output("registry_id", entry_id)
    write_output("version", str(entry["version"]))
    write_output("source_ref", resolved_ref)
    write_output("commit_message", f"registry: add {entry_id}")
    write_output("pr_title", f"registry: add {entry['name']}")

    if args.dry_run:
        print(json.dumps(entry, indent=2))
        return 0

    registry_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Promoted {request_path} to registry entry {entry_id} from {resolved_ref}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"promote_request.py failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

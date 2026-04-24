#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from submission_utils import fetch_manifest_from_github, load_registry_entries, parse_repo_url


SYNC_MODES = ("full_manifest", "version_only")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize an existing registry entry with the manifest published in a GitHub repository."
        )
    )
    parser.add_argument("--registry-id", required=True, help="Registry entry id to update.")
    parser.add_argument(
        "--repo-url",
        default=None,
        help="Optional GitHub repository URL. Defaults to the existing registry entry repo_url.",
    )
    parser.add_argument(
        "--manifest-path",
        default=None,
        help="Optional manifest path. Defaults to the existing registry entry manifest_path.",
    )
    parser.add_argument(
        "--ref",
        default=None,
        help="Optional Git ref, tag, or branch to fetch from. Defaults to the repo default branch.",
    )
    parser.add_argument(
        "--sync-mode",
        choices=SYNC_MODES,
        default="full_manifest",
        help="Whether to sync only the version or also safe manifest-backed metadata.",
    )
    parser.add_argument(
        "--registry-path",
        default="registry.json",
        help="Path to registry.json. Defaults to the repository root registry.json.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the updated entry without writing files.")
    return parser.parse_args()


def write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


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
    top_level_image = image_repository(str(manifest.get("image") or ""))
    if top_level_image:
        return top_level_image

    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        return None

    discovered: set[str] = set()
    for runtime_target in runtime.values():
        if not isinstance(runtime_target, dict):
            continue
        container = runtime_target.get("container")
        if not isinstance(container, dict):
            continue
        repo = image_repository(str(container.get("image") or ""))
        if repo:
            discovered.add(repo)

    if len(discovered) == 1:
        return next(iter(discovered))
    return None


def normalize_manifest_platforms(manifest: dict[str, Any]) -> list[str]:
    raw_platforms = manifest.get("platforms")
    if not isinstance(raw_platforms, list):
        return []
    normalized: list[str] = []
    for item in raw_platforms:
        token = str(item or "").strip().lower()
        if token and token not in normalized:
            normalized.append(token)
    return normalized


def normalize_maintainer(manifest: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    current = existing.get("maintainer")
    maintainer = dict(current) if isinstance(current, dict) else {}
    source = manifest.get("maintainer")
    if not isinstance(source, dict):
        return maintainer

    for key in ("name", "website", "support_email"):
        value = str(source.get(key) or "").strip()
        if value:
            maintainer[key] = value
    return maintainer


def set_if_changed(entry: dict[str, Any], key: str, value: Any, updated_fields: set[str]) -> None:
    if value is None:
        return
    if entry.get(key) != value:
        entry[key] = value
        updated_fields.add(key)


def build_commit_message(registry_id: str, version: str) -> str:
    return f"registry: sync {registry_id} to v{version}"


def build_pr_title(registry_id: str, version: str) -> str:
    return f"registry: sync {registry_id} to v{version}"


def main() -> int:
    args = parse_args()
    registry_path = Path(args.registry_path).resolve()
    entries = load_registry_entries(registry_path)
    registry_id = str(args.registry_id).strip()
    target_entry = next((entry for entry in entries if str(entry.get("id") or "").strip() == registry_id), None)
    if target_entry is None:
        raise ValueError(f"Registry entry '{registry_id}' was not found in {registry_path.name}")

    repo_url = str(args.repo_url or target_entry.get("repo_url") or "").strip()
    if not repo_url:
        raise ValueError("Repository URL is missing and could not be inferred from the existing registry entry.")
    manifest_path = str(args.manifest_path or target_entry.get("manifest_path") or "src/manifest.json").strip()
    if not manifest_path:
        raise ValueError("Manifest path is missing and could not be inferred from the existing registry entry.")

    manifest, resolved_ref = fetch_manifest_from_github(
        repo_url=repo_url,
        manifest_path=manifest_path,
        token=os.getenv("GITHUB_TOKEN"),
        ref=args.ref,
    )

    manifest_id = str(manifest.get("id") or "").strip()
    if not manifest_id:
        raise ValueError("Fetched manifest is missing an id field.")
    if manifest_id != registry_id:
        raise ValueError(
            f"Fetched manifest id '{manifest_id}' does not match requested registry id '{registry_id}'."
        )

    version = str(manifest.get("version") or "").strip()
    if not version:
        raise ValueError("Fetched manifest is missing a version field.")

    owner, repo_name = parse_repo_url(repo_url)
    updated_fields: set[str] = set()

    set_if_changed(target_entry, "version", version, updated_fields)
    set_if_changed(target_entry, "owner", owner, updated_fields)
    set_if_changed(target_entry, "repo_name", repo_name, updated_fields)
    set_if_changed(target_entry, "repo_url", repo_url, updated_fields)
    set_if_changed(target_entry, "manifest_path", manifest_path, updated_fields)

    manifest_image = infer_manifest_image_repository(manifest)
    if manifest_image:
        set_if_changed(target_entry, "image", manifest_image, updated_fields)

    if args.sync_mode == "full_manifest":
        manifest_name = str(manifest.get("name") or "").strip()
        manifest_description = str(manifest.get("description") or "").strip()
        manifest_platforms = normalize_manifest_platforms(manifest)
        manifest_maintainer = normalize_maintainer(manifest, target_entry)

        if manifest_name:
            set_if_changed(target_entry, "name", manifest_name, updated_fields)
        if manifest_description:
            set_if_changed(target_entry, "description", manifest_description, updated_fields)
        if manifest_platforms:
            set_if_changed(target_entry, "platforms", manifest_platforms, updated_fields)
        if manifest_maintainer:
            set_if_changed(target_entry, "maintainer", manifest_maintainer, updated_fields)

    serialized = json.dumps(entries, indent=2) + "\n"
    changed = bool(updated_fields)

    write_output("changed", "true" if changed else "false")
    write_output("registry_id", registry_id)
    write_output("repo_url", repo_url)
    write_output("manifest_path", manifest_path)
    write_output("source_ref", resolved_ref)
    write_output("version", version)
    write_output("sync_mode", args.sync_mode)
    write_output("updated_fields", ",".join(sorted(updated_fields)))
    write_output("commit_message", build_commit_message(registry_id, version))
    write_output("pr_title", build_pr_title(registry_id, version))

    if args.dry_run:
        print(json.dumps(target_entry, indent=2))
        return 0

    if changed:
        registry_path.write_text(serialized, encoding="utf-8")

    step_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        with open(step_summary_path, "a", encoding="utf-8") as handle:
            handle.write(f"## Registry Sync `{registry_id}`\n\n")
            handle.write(f"- Source repository: `{repo_url}`\n")
            handle.write(f"- Manifest path: `{manifest_path}`\n")
            handle.write(f"- Source ref: `{resolved_ref}`\n")
            handle.write(f"- Sync mode: `{args.sync_mode}`\n")
            handle.write(f"- Resolved version: `{version}`\n")
            if changed:
                handle.write(f"- Updated fields: `{', '.join(sorted(updated_fields))}`\n")
            else:
                handle.write("- No registry changes were required.\n")

    print(f"changed={str(changed).lower()} version={version} source_ref={resolved_ref}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"sync_registry_entry.py failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

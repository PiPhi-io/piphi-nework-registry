#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from submission_utils import fetch_manifest_from_github, load_registry_entries, parse_repo_url


VALID_REQUEST_STATUSES = {"requested", "accepted", "rejected", "converted"}
VALID_ENTRY_TYPES = {"integration", "platform_service", "widget"}
VALID_TRUST_LEVELS = {"official", "verified", "community", "experimental"}
VALID_RISK_LEVELS = {"low", "moderate", "high"}
REQUEST_REQUIRED_FIELDS = {
    "schema_version",
    "request_id",
    "status",
    "brand",
    "requested_by",
    "created_at",
}
PROPOSED_ENTRY_REQUIRED_FIELDS = {
    "id",
    "name",
    "type",
    "version",
    "owner",
    "repo_name",
    "repo_url",
    "manifest_path",
    "trust_level",
    "risk_level",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Core-created plugin request JSON files.")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Request files or directories to validate. Defaults to requests/.",
    )
    parser.add_argument(
        "--registry-path",
        default="registry.json",
        help="Path to registry.json for duplicate checks.",
    )
    parser.add_argument(
        "--skip-remote",
        action="store_true",
        help="Skip GitHub repository and manifest fetch checks.",
    )
    return parser.parse_args()


def discover_request_files(paths: list[str]) -> list[Path]:
    candidates = [Path(path) for path in paths] if paths else [Path("requests")]
    files: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir():
            files.extend(candidate.glob("*.json"))
        elif candidate.exists():
            files.append(candidate)
    return sorted({path.resolve() for path in files})


def load_request(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request file must contain a JSON object")
    return payload


def parse_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def validate_proposed_entry(
    *,
    entry: dict[str, Any],
    request_path: Path,
    registry_ids: set[str],
    seen_request_entry_ids: set[str],
    token: str | None,
    skip_remote: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    prefix = f"{request_path}: proposed_registry_entry"

    missing = sorted(field for field in PROPOSED_ENTRY_REQUIRED_FIELDS if not str(entry.get(field) or "").strip())
    for field in missing:
        errors.append(f"{prefix}: missing required field {field}")

    entry_id = str(entry.get("id") or "").strip()
    if entry_id:
        if entry_id in registry_ids:
            errors.append(f"{prefix}: id '{entry_id}' already exists in registry.json")
        if entry_id in seen_request_entry_ids:
            errors.append(f"{prefix}: duplicate proposed id '{entry_id}' across request files")
        seen_request_entry_ids.add(entry_id)

    entry_type = str(entry.get("type") or "").strip()
    if entry_type and entry_type not in VALID_ENTRY_TYPES:
        errors.append(f"{prefix}: type must be one of {sorted(VALID_ENTRY_TYPES)}")

    trust_level = str(entry.get("trust_level") or "").strip()
    if trust_level and trust_level not in VALID_TRUST_LEVELS:
        errors.append(f"{prefix}: trust_level must be one of {sorted(VALID_TRUST_LEVELS)}")

    risk_level = str(entry.get("risk_level") or "").strip()
    if risk_level and risk_level not in VALID_RISK_LEVELS:
        errors.append(f"{prefix}: risk_level must be one of {sorted(VALID_RISK_LEVELS)}")

    repo_url = str(entry.get("repo_url") or "").strip()
    manifest_path = str(entry.get("manifest_path") or "").strip()
    owner = str(entry.get("owner") or "").strip()
    repo_name = str(entry.get("repo_name") or "").strip()
    parsed_owner = parsed_repo = ""
    if repo_url:
        try:
            parsed_owner, parsed_repo = parse_repo_url(repo_url)
        except ValueError as exc:
            errors.append(f"{prefix}: {exc}")
        if parsed_owner and owner and parsed_owner != owner:
            errors.append(f"{prefix}: owner does not match repo_url owner '{parsed_owner}'")
        if parsed_repo and repo_name and parsed_repo != repo_name:
            errors.append(f"{prefix}: repo_name does not match repo_url repo '{parsed_repo}'")

    if repo_url and manifest_path and not skip_remote:
        try:
            manifest, resolved_ref = fetch_manifest_from_github(
                repo_url=repo_url,
                manifest_path=manifest_path,
                token=token,
            )
            manifest_id = str(manifest.get("id") or "").strip()
            manifest_version = str(manifest.get("version") or "").strip()
            if manifest_id and entry_id and manifest_id != entry_id:
                warnings.append(
                    f"{prefix}: proposed id '{entry_id}' does not match manifest id '{manifest_id}'"
                )
            if not manifest_id:
                errors.append(f"{prefix}: fetched manifest at {resolved_ref} is missing id")
            if not manifest_version:
                errors.append(f"{prefix}: fetched manifest at {resolved_ref} is missing version")
        except Exception as exc:
            errors.append(f"{prefix}: unable to fetch manifest from repository: {exc}")
    elif repo_url and manifest_path and skip_remote:
        warnings.append(f"{prefix}: remote manifest checks skipped")

    return errors, warnings


def validate_request_file(
    *,
    path: Path,
    payload: dict[str, Any],
    registry_ids: set[str],
    seen_request_ids: set[str],
    seen_request_entry_ids: set[str],
    token: str | None,
    skip_remote: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    prefix = str(path)

    missing = sorted(field for field in REQUEST_REQUIRED_FIELDS if not str(payload.get(field) or "").strip())
    for field in missing:
        errors.append(f"{prefix}: missing required field {field}")

    if payload.get("schema_version") != 1:
        errors.append(f"{prefix}: schema_version must be 1")

    request_id = str(payload.get("request_id") or "").strip()
    if request_id:
        if request_id in seen_request_ids:
            errors.append(f"{prefix}: duplicate request_id '{request_id}'")
        seen_request_ids.add(request_id)

    status = str(payload.get("status") or "").strip()
    if status and status not in VALID_REQUEST_STATUSES:
        errors.append(f"{prefix}: status must be one of {sorted(VALID_REQUEST_STATUSES)}")

    if not parse_datetime(payload.get("created_at")):
        errors.append(f"{prefix}: created_at must be an ISO datetime")

    repo_url = str(payload.get("repo_url") or "").strip()
    if repo_url:
        try:
            parse_repo_url(repo_url)
        except ValueError:
            warnings.append(f"{prefix}: repo_url is not a GitHub repository URL; manifest checks skipped")

    proposed = payload.get("proposed_registry_entry")
    if proposed is None:
        warnings.append(f"{prefix}: no proposed_registry_entry yet")
    elif not isinstance(proposed, dict):
        errors.append(f"{prefix}: proposed_registry_entry must be an object or null")
    else:
        proposed_errors, proposed_warnings = validate_proposed_entry(
            entry=proposed,
            request_path=path,
            registry_ids=registry_ids,
            seen_request_entry_ids=seen_request_entry_ids,
            token=token,
            skip_remote=skip_remote,
        )
        errors.extend(proposed_errors)
        warnings.extend(proposed_warnings)

    return errors, warnings


def write_step_summary(files: list[Path], errors: list[str], warnings: list[str]) -> None:
    raw_summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if not raw_summary_path:
        return
    summary_path = Path(raw_summary_path)
    lines = [
        "## Plugin Request Validation",
        "",
        f"- Request files checked: `{len(files)}`",
        f"- Errors: `{len(errors)}`",
        f"- Warnings: `{len(warnings)}`",
        "",
    ]
    if errors:
        lines.append("### Errors")
        lines.extend(f"- {error}" for error in errors)
        lines.append("")
    if warnings:
        lines.append("### Warnings")
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    files = discover_request_files(args.paths)
    if not files:
        print("No plugin request files found.")
        return 0

    registry_ids = {
        str(entry.get("id") or "").strip()
        for entry in load_registry_entries(Path(args.registry_path))
        if str(entry.get("id") or "").strip()
    }
    seen_request_ids: set[str] = set()
    seen_request_entry_ids: set[str] = set()
    token = os.environ.get("GITHUB_TOKEN")
    errors: list[str] = []
    warnings: list[str] = []

    for path in files:
        try:
            payload = load_request(path)
        except Exception as exc:
            errors.append(f"{path}: unable to load request JSON: {exc}")
            continue
        file_errors, file_warnings = validate_request_file(
            path=path,
            payload=payload,
            registry_ids=registry_ids,
            seen_request_ids=seen_request_ids,
            seen_request_entry_ids=seen_request_entry_ids,
            token=token,
            skip_remote=args.skip_remote,
        )
        errors.extend(file_errors)
        warnings.extend(file_warnings)

    write_step_summary(files, errors, warnings)
    if warnings:
        print("Plugin request validation warnings:", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)

    if errors:
        print("Plugin request validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Plugin request validation passed for {len(files)} request file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

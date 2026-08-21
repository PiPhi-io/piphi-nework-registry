#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from submission_utils import load_registry_entries


SHA256_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
PASS_FLAGS = (
    "health_contract_valid",
    "runtime_contract_valid",
    "entities_contract_valid",
    "events_contract_valid",
    "explicit_replay_acknowledgement",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote immutable runtime qualification evidence into registry governance."
    )
    parser.add_argument("--registry-id", required=True)
    parser.add_argument("--report-path", required=True, type=Path)
    parser.add_argument("--evidence-url", required=True)
    parser.add_argument("--core-version", required=True)
    parser.add_argument("--registry-path", default="registry.json", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _text(value: Any) -> str:
    return str(value or "").strip()


def validate_report(report: Any, *, registry_id: str) -> list[str]:
    if not isinstance(report, dict):
        return ["qualification report must be a JSON object"]
    errors: list[str] = []
    if report.get("schema_version") != 2:
        errors.append("qualification report schema_version must be 2")
    if _text(report.get("runtime_name")) != registry_id:
        errors.append("qualification runtime_name must match the registry id")
    if report.get("passed") is not True:
        errors.append("qualification report must have passed=true")
    failures = report.get("failures")
    if not isinstance(failures, list) or failures:
        errors.append("qualification report failures must be an empty list")
    for flag in PASS_FLAGS:
        if report.get(flag) is not True:
            errors.append(f"qualification report {flag} must be true")
    if not SHA256_DIGEST.fullmatch(_text(report.get("image_digest"))):
        errors.append("qualification image_digest must be an immutable sha256 digest")
    if not GIT_SHA.fullmatch(_text(report.get("core_source_commit"))):
        errors.append("qualification core_source_commit must be a full Git SHA")
    for field in (
        "health_status",
        "contract_status",
        "entities_status",
        "events_status",
        "first_status",
        "replay_status",
    ):
        status = report.get(field)
        if isinstance(status, bool) or not isinstance(status, int) or not 200 <= status < 300:
            errors.append(f"qualification report {field} must be a successful HTTP status")
    return errors


def build_qualification(
    report: dict[str, Any], *, evidence_url: str, core_version: str, tested_at: datetime
) -> dict[str, Any]:
    if not re.fullmatch(r"https?://[^\s]+", evidence_url):
        raise ValueError("evidence_url must be an HTTP(S) URL")
    if not core_version.strip():
        raise ValueError("core_version is required")
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "status": "passed",
        "tested_core_versions": [core_version.strip()],
        "tested_at": tested_at.astimezone(timezone.utc).isoformat(),
        "evidence_url": evidence_url,
        "report_digest": "sha256:" + hashlib.sha256(canonical).hexdigest(),
        "runtime_image_digest": report["image_digest"],
        "core_source_commit": report["core_source_commit"],
    }


def promote_entry(
    entries: list[dict[str, Any]],
    *,
    registry_id: str,
    report: dict[str, Any],
    evidence_url: str,
    core_version: str,
    tested_at: datetime,
) -> dict[str, Any]:
    errors = validate_report(report, registry_id=registry_id)
    if errors:
        raise ValueError("; ".join(errors))
    entry = next((item for item in entries if _text(item.get("id")) == registry_id), None)
    if entry is None:
        raise ValueError(f"Registry entry '{registry_id}' was not found")
    marketplace = entry.get("marketplace")
    if not isinstance(marketplace, dict):
        raise ValueError("Registry entry has no Marketplace Metadata v2 object")
    governance = marketplace.get("governance")
    if not isinstance(governance, dict):
        raise ValueError("Registry entry has no governance contract")
    if _text(governance.get("lifecycle_status")) != "active":
        raise ValueError("Only active integrations can be promoted")
    if _text(governance.get("publication_status")) not in {"beta", "stable"}:
        raise ValueError("Only beta or stable integrations can be promoted")

    governance["qualification"] = build_qualification(
        report,
        evidence_url=evidence_url,
        core_version=core_version,
        tested_at=tested_at,
    )
    if _text(marketplace.get("quality_tier") or "unrated") in {"unrated", "bronze"}:
        marketplace["quality_tier"] = "silver"
    return entry


def write_output(name: str, value: str) -> None:
    path = os.getenv("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def main() -> int:
    args = parse_args()
    report = json.loads(args.report_path.read_text(encoding="utf-8"))
    entries = load_registry_entries(args.registry_path)
    tested_at = datetime.now(timezone.utc)
    entry = promote_entry(
        entries,
        registry_id=args.registry_id.strip(),
        report=report,
        evidence_url=args.evidence_url.strip(),
        core_version=args.core_version.strip(),
        tested_at=tested_at,
    )
    write_output("registry_id", args.registry_id.strip())
    write_output("quality_tier", _text(entry["marketplace"].get("quality_tier")))
    write_output("report_digest", _text(entry["marketplace"]["governance"]["qualification"]["report_digest"]))
    if args.dry_run:
        print(json.dumps(entry, indent=2))
        return 0
    args.registry_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"Promoted runtime qualification for {args.registry_id} to Silver quality.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"promote_qualification.py failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

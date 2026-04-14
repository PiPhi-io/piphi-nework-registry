#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
VALID_ENTRY_TYPES = {"integration", "platform_service"}
VALID_DEPLOYMENT_MODES = {"standalone", "sidecar"}
VALID_PLATFORMS = {"linux", "windows", "macos"}

from submission_utils import (
    fetch_json,
    fetch_manifest_from_github,
    load_registry_entries,
    parse_issue_form,
    parse_repo_url,
    split_lines,
    url_exists,
)


def validate_submission(fields: dict[str, str], registry_path: Path, token: str | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    integration_name = fields.get("integration_name", "")
    integration_id = fields.get("integration_id", "")
    entry_type = fields.get("entry_type", "")
    deployment_mode = fields.get("deployment_mode", "")
    repo_url = fields.get("repository_url", "")
    manifest_path = fields.get("manifest_path", "")
    description = fields.get("short_description", "")
    maintainer_name = fields.get("maintainer_name", "")
    support_contact = fields.get("support_contact", "")
    icon_url = fields.get("icon_url", "")
    platform_lines = {item.lower() for item in split_lines(fields.get("supported_platforms", ""))}

    if not integration_name:
        errors.append("Integration name is required.")
    if not integration_id:
        errors.append("Integration ID is required.")
    if entry_type not in VALID_ENTRY_TYPES:
        errors.append(f"Entry type must be one of: {', '.join(sorted(VALID_ENTRY_TYPES))}.")
    if deployment_mode not in VALID_DEPLOYMENT_MODES:
        errors.append(f"Deployment mode must be one of: {', '.join(sorted(VALID_DEPLOYMENT_MODES))}.")
    if not manifest_path:
        errors.append("Manifest path is required.")
    if not description:
        errors.append("Short description is required.")
    if not maintainer_name:
        errors.append("Maintainer name is required.")
    if not support_contact:
        errors.append("Support contact is required.")
    if not platform_lines:
        errors.append("At least one supported platform must be selected.")
    if platform_lines and not platform_lines.issubset(VALID_PLATFORMS):
        errors.append(
            f"Supported platforms must be selected from: {', '.join(sorted(VALID_PLATFORMS))}."
        )

    existing_entries = load_registry_entries(registry_path)
    if integration_id and any(str(entry.get("id", "")).strip().lower() == integration_id.strip().lower() for entry in existing_entries):
        errors.append(f"Integration ID '{integration_id}' already exists in registry.json.")

    owner = repo = ""
    default_branch = ""
    manifest_payload: dict[str, Any] | None = None
    if repo_url:
        try:
            owner, repo = parse_repo_url(repo_url)
            repo_metadata = fetch_json(f"https://api.github.com/repos/{owner}/{repo}", token=token)
            default_branch = str(repo_metadata.get("default_branch") or "").strip()
            if repo_metadata.get("private"):
                errors.append("Repository must be public.")
        except Exception as exc:
            errors.append(f"Unable to inspect repository URL: {exc}")

    if owner and repo and default_branch and manifest_path:
        try:
            manifest_payload, _ = fetch_manifest_from_github(repo_url, manifest_path, token=token)
        except Exception as exc:
            errors.append(f"Unable to fetch manifest from repository: {exc}")

    if manifest_payload is not None:
        manifest_id = str(manifest_payload.get("id") or "").strip()
        manifest_name = str(manifest_payload.get("name") or "").strip()
        manifest_platforms = {
            str(item).strip().lower() for item in (manifest_payload.get("platforms") or []) if str(item).strip()
        }
        if manifest_id and integration_id and manifest_id != integration_id:
            errors.append(
                f"Submitted integration ID '{integration_id}' does not match manifest ID '{manifest_id}'."
            )
        if manifest_name and integration_name and manifest_name != integration_name:
            warnings.append(
                f"Submitted integration name '{integration_name}' does not exactly match manifest name '{manifest_name}'."
            )
        if platform_lines and manifest_platforms and platform_lines != manifest_platforms:
            warnings.append(
                "Selected supported platforms do not exactly match the manifest platforms."
            )

    if icon_url and not url_exists(icon_url):
        errors.append("Icon URL is not reachable.")
    if not icon_url:
        warnings.append("No icon URL was provided. Registry placeholder icon will be used unless reviewers request custom artwork.")

    return errors, warnings


def write_outputs(errors: list[str], warnings: list[str], fields: dict[str, str]) -> None:
    status = "passed" if not errors else "failed"
    summary_lines = [
        f"## Submission Validation {status.title()}",
        "",
        f"- Integration: `{fields.get('integration_name', 'unknown')}`",
        f"- Integration ID: `{fields.get('integration_id', 'unknown')}`",
        f"- Repository: `{fields.get('repository_url', 'unknown')}`",
        f"- Manifest Path: `{fields.get('manifest_path', 'unknown')}`",
        "",
    ]

    if errors:
        summary_lines.append("### Errors")
        summary_lines.extend(f"- {item}" for item in errors)
        summary_lines.append("")

    if warnings:
        summary_lines.append("### Warnings")
        summary_lines.extend(f"- {item}" for item in warnings)
        summary_lines.append("")

    if not errors:
        summary_lines.append("### Result")
        summary_lines.append("- Automated validation passed. This submission is ready for human review.")
    else:
        summary_lines.append("### Result")
        summary_lines.append("- Automated validation failed. Please address the errors above and update this issue.")

    body = "\n".join(summary_lines).strip() + "\n"
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as file_handle:
            file_handle.write(f"validation_status={status}\n")
            file_handle.write("validation_comment<<EOF\n")
            file_handle.write(body)
            file_handle.write("EOF\n")
    print(body)


def main() -> int:
    issue_body = os.getenv("ISSUE_BODY", "")
    if not issue_body.strip():
        print("ISSUE_BODY is empty", file=sys.stderr)
        return 1

    fields = parse_issue_form(issue_body)
    registry_path = Path(os.getenv("REGISTRY_PATH", "registry.json")).resolve()
    token = os.getenv("GITHUB_TOKEN")

    errors, warnings = validate_submission(fields, registry_path=registry_path, token=token)
    write_outputs(errors, warnings, fields)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

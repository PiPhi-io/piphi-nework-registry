#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from submission_utils import fetch_manifest_from_github, parse_issue_form, parse_repo_url, split_lines


def choose_default_icon_url(deployment_mode: str) -> str:
    if deployment_mode == "sidecar":
        return "https://raw.githubusercontent.com/PiPhi-io/piphi-nework-registry/main/icons/mqtt-sidecar.svg"
    return "https://raw.githubusercontent.com/PiPhi-io/piphi-nework-registry/main/icons/placeholder.svg"


def parse_tags(raw_value: str) -> list[str]:
    if not raw_value.strip():
        return []
    normalized: list[str] = []
    for raw_tag in raw_value.replace("\n", ",").split(","):
        tag = raw_tag.strip().lower()
        if tag and tag not in normalized:
            normalized.append(tag)
    return normalized


def normalize_runtime_requirements(raw_value: str) -> list[str]:
    mapping = {
        "Requires host networking": "host_networking",
        "Requires privileged container mode": "privileged_container",
        "Requires USB or device access": "usb_or_device_access",
        "Requires host filesystem mounts": "host_filesystem_mounts",
        "Requires secrets or API tokens": "secrets_or_api_tokens",
        "Runs as a helper/sidecar for another integration": "sidecar_runtime",
        "Requires direct hardware access": "direct_hardware_access",
    }
    normalized: list[str] = []
    for item in split_lines(raw_value):
        token = mapping.get(item)
        if token and token not in normalized:
            normalized.append(token)
    return normalized


def infer_risk_level(deployment_mode: str, runtime_requirements: list[str]) -> str:
    if any(
        token in {"privileged_container", "host_networking", "host_filesystem_mounts"}
        for token in runtime_requirements
    ):
        return "high"
    if deployment_mode == "sidecar" or any(
        token in {"usb_or_device_access", "direct_hardware_access", "secrets_or_api_tokens", "sidecar_runtime"}
        for token in runtime_requirements
    ):
        return "moderate"
    return "low"


def build_entry(fields: dict[str, str], manifest: dict[str, object]) -> dict[str, object]:
    repo_url = fields["repository_url"].strip()
    owner, repo_name = parse_repo_url(repo_url)
    deployment_mode = fields.get("deployment_mode", "standalone").strip() or "standalone"
    runtime_requirements = normalize_runtime_requirements(fields.get("runtime_requirements", ""))
    icon_url = fields.get("icon_url", "").strip() or choose_default_icon_url(deployment_mode)
    support_contact = fields.get("support_contact", "").strip()
    maintainer_name = fields.get("maintainer_name", "").strip()

    entry: dict[str, object] = {
        "id": str(manifest.get("id") or fields.get("integration_id") or "").strip(),
        "name": str(manifest.get("name") or fields.get("integration_name") or "").strip(),
        "version": str(manifest.get("version") or "").strip(),
        "type": fields.get("entry_type", "integration").strip() or "integration",
        "deployment_mode": deployment_mode,
        "trust_level": "community",
        "risk_level": infer_risk_level(deployment_mode, runtime_requirements),
        "description": str(manifest.get("description") or fields.get("short_description") or "").strip(),
        "rewardable": False,
        "platforms": split_lines(fields.get("supported_platforms", "")),
        "icon_url": icon_url,
        "owner": owner,
        "repo_name": repo_name,
        "repo_url": repo_url,
        "manifest_path": fields.get("manifest_path", "").strip(),
        "tags": parse_tags(fields.get("tags", "")),
        "runtime_requirements": runtime_requirements,
        "maintainer": {
            "name": maintainer_name,
        },
    }

    manifest_image = str(manifest.get("image") or "").strip()
    if manifest_image:
        entry["image"] = manifest_image

    banner_url = fields.get("banner_url", "").strip()
    if banner_url:
        entry["banner_url"] = banner_url

    if support_contact:
        if support_contact.startswith("http://") or support_contact.startswith("https://"):
            entry["maintainer"]["website"] = support_contact
        else:
            entry["maintainer"]["support_email"] = support_contact

    if deployment_mode == "standalone":
        entry.pop("deployment_mode", None)

    return entry


def write_outputs(entry: dict[str, object]) -> None:
    pretty_json = json.dumps(entry, indent=2, sort_keys=False)
    comment = (
        "## Proposed Registry Entry\n\n"
        "Copy this JSON object into `registry.json` once final review is complete.\n\n"
        "```json\n"
        f"{pretty_json}\n"
        "```\n"
    )

    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as file_handle:
            file_handle.write("generated_entry<<EOF\n")
            file_handle.write(pretty_json)
            file_handle.write("\nEOF\n")
            file_handle.write("generated_comment<<EOF\n")
            file_handle.write(comment)
            file_handle.write("EOF\n")
    print(comment)


def main() -> int:
    issue_body = os.getenv("ISSUE_BODY", "")
    if not issue_body.strip():
        print("ISSUE_BODY is empty", file=sys.stderr)
        return 1

    fields = parse_issue_form(issue_body)
    repo_url = fields.get("repository_url", "").strip()
    manifest_path = fields.get("manifest_path", "").strip()
    if not repo_url or not manifest_path:
        print("Submission is missing repository URL or manifest path", file=sys.stderr)
        return 1

    manifest, _default_branch = fetch_manifest_from_github(
        repo_url=repo_url,
        manifest_path=manifest_path,
        token=os.getenv("GITHUB_TOKEN"),
    )
    entry = build_entry(fields, manifest)
    write_outputs(entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

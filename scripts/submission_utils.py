from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SECTION_PATTERN = re.compile(r"^###\s+(?P<label>.+?)\s*$", re.MULTILINE)
REPO_URL_PATTERN = re.compile(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/#]+?)(?:\.git)?/?$")


def parse_issue_form(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(SECTION_PATTERN.finditer(body))
    for index, match in enumerate(matches):
        section_start = match.end()
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        raw_value = body[section_start:section_end].strip()
        normalized_label = normalize_label(match.group("label"))
        sections[normalized_label] = normalize_section_value(raw_value)
    return sections


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def normalize_section_value(value: str) -> str:
    cleaned_lines: list[str] = []
    for line in value.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [x] ") or stripped.startswith("- [X] "):
            cleaned_lines.append(stripped[6:].strip())
        elif stripped.startswith("- [ ] "):
            continue
        elif stripped:
            cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines).strip()


def split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def build_headers(token: str | None, accept: str) -> dict[str, str]:
    headers = {
        "Accept": accept,
        "User-Agent": "piphi-registry-automation",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_json(url: str, token: str | None = None) -> Any:
    request = urllib.request.Request(
        url,
        headers=build_headers(token=token, accept="application/vnd.github+json"),
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str, token: str | None = None, accept: str = "application/json") -> str:
    request = urllib.request.Request(
        url,
        headers=build_headers(token=token, accept=accept),
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def url_exists(url: str) -> bool:
    request = urllib.request.Request(url, headers=build_headers(token=None, accept="*/*"))
    try:
        with urllib.request.urlopen(request, timeout=20):
            return True
    except urllib.error.URLError:
        return False


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    match = REPO_URL_PATTERN.match(repo_url.strip())
    if not match:
        raise ValueError("Repository URL must be a GitHub repository URL like https://github.com/owner/repo")
    return match.group("owner"), match.group("repo")


def load_registry_entries(registry_path: Path) -> list[dict[str, Any]]:
    if not registry_path.exists():
        return []
    payload = json.loads(registry_path.read_text())
    if not isinstance(payload, list):
        raise ValueError("registry.json must contain a JSON array")
    return payload


def fetch_manifest_from_github(
    repo_url: str,
    manifest_path: str,
    token: str | None = None,
    ref: str | None = None,
) -> tuple[dict[str, Any], str]:
    owner, repo = parse_repo_url(repo_url)
    repo_metadata = fetch_json(f"https://api.github.com/repos/{owner}/{repo}", token=token)
    default_branch = str(repo_metadata.get("default_branch") or "").strip()
    if not default_branch:
        raise ValueError("Unable to determine repository default branch")
    resolved_ref = str(ref or "").strip() or default_branch

    encoded_manifest_path = urllib.parse.quote(manifest_path.strip().lstrip("/"))
    manifest_api_url = (
        f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_manifest_path}"
        f"?ref={urllib.parse.quote(resolved_ref, safe='')}"
    )
    manifest_content = fetch_json(manifest_api_url, token=token)
    if manifest_content.get("type") != "file":
        raise ValueError("Manifest path does not point to a file")
    encoded_content = str(manifest_content.get("content") or "").strip()
    encoding = str(manifest_content.get("encoding") or "").strip().lower()
    if encoded_content and encoding == "base64":
        manifest_payload = json.loads(base64.b64decode(encoded_content).decode("utf-8"))
    else:
        download_url = manifest_content.get("download_url")
        if not download_url:
            raise ValueError("Manifest file does not expose downloadable content")
        manifest_payload = json.loads(fetch_text(download_url, token=token, accept="application/json"))
    return manifest_payload, resolved_ref

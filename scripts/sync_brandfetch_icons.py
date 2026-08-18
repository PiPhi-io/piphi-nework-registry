#!/usr/bin/env python3
"""Refresh registry-hosted brand icons from Brandfetch's licensed Brand API."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


BRANDFETCH_API = "https://api.brandfetch.io/v2/brands/domain"
MAX_ICON_BYTES = 2 * 1024 * 1024
DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)
FORMAT_PRIORITY = ("png", "webp", "jpg", "jpeg")
TYPE_PRIORITY = ("icon", "symbol", "logo")


class BrandIconSyncError(RuntimeError):
    pass


def _request_bytes(url: str, *, api_key: str | None = None) -> tuple[bytes, str]:
    headers = {
        "Accept": "application/json" if api_key else "image/*",
        "User-Agent": "PiPhi-Registry-Brand-Asset-Sync/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        payload = response.read(MAX_ICON_BYTES + 1)
        content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
    if len(payload) > MAX_ICON_BYTES:
        raise BrandIconSyncError(f"asset exceeds {MAX_ICON_BYTES} bytes")
    return payload, content_type


def fetch_brand(domain: str, api_key: str) -> dict[str, Any]:
    payload, content_type = _request_bytes(
        f"{BRANDFETCH_API}/{quote(domain, safe='')}", api_key=api_key
    )
    if content_type != "application/json":
        raise BrandIconSyncError(f"Brand API returned {content_type or 'an unknown content type'}")
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise BrandIconSyncError("Brand API response must be an object")
    return decoded


def select_icon_asset(brand: dict[str, Any]) -> tuple[str, str]:
    logos = brand.get("logos")
    if not isinstance(logos, list):
        raise BrandIconSyncError("brand has no logo collection")

    for logo_type in TYPE_PRIORITY:
        for logo in logos:
            if not isinstance(logo, dict) or str(logo.get("type") or "").lower() != logo_type:
                continue
            formats = logo.get("formats")
            if not isinstance(formats, list):
                continue
            for wanted_format in FORMAT_PRIORITY:
                for candidate in formats:
                    if not isinstance(candidate, dict):
                        continue
                    asset_format = str(candidate.get("format") or "").lower()
                    source = str(candidate.get("src") or "").strip()
                    if asset_format == wanted_format and source.startswith("https://"):
                        return source, "jpg" if asset_format == "jpeg" else asset_format
    raise BrandIconSyncError("brand has no supported icon, symbol, or logo asset")


def _validate_asset(payload: bytes, content_type: str, extension: str) -> None:
    expected_types = {
        "png": {"image/png"},
        "webp": {"image/webp"},
        "jpg": {"image/jpeg"},
    }
    if not payload:
        raise BrandIconSyncError("asset is empty")
    if content_type not in expected_types[extension]:
        raise BrandIconSyncError(
            f"expected {extension} artwork but received {content_type or 'an unknown content type'}"
        )
    signatures = {
        "png": payload.startswith(b"\x89PNG\r\n\x1a\n"),
        "webp": payload.startswith(b"RIFF") and payload[8:12] == b"WEBP",
        "jpg": payload.startswith(b"\xff\xd8\xff"),
    }
    if not signatures[extension]:
        raise BrandIconSyncError(f"{extension} response has an invalid file signature")


def _load_registry(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise BrandIconSyncError("registry must contain a JSON array")
    return payload


def _brand_entries(entries: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    selected: list[tuple[dict[str, Any], str]] = []
    for entry in entries:
        marketplace = entry.get("marketplace")
        if not isinstance(marketplace, dict):
            continue
        domain = str(marketplace.get("brand_domain") or "").strip().lower().rstrip(".")
        if not domain:
            continue
        if not DOMAIN_PATTERN.fullmatch(domain):
            raise BrandIconSyncError(f"{entry.get('id')}: invalid brand_domain {domain!r}")
        selected.append((entry, domain))
    if not selected:
        raise BrandIconSyncError("registry has no marketplace.brand_domain entries")
    return selected


def synchronize(
    *,
    registry_path: Path,
    icons_dir: Path,
    api_key: str,
    repository: str,
    branch: str,
    refreshed_at: str | None = None,
) -> list[str]:
    entries = _load_registry(registry_path)
    selected = _brand_entries(entries)
    timestamp = refreshed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    prepared: list[tuple[dict[str, Any], Path, bytes, str, str]] = []

    with tempfile.TemporaryDirectory(prefix="piphi-brand-icons-") as temporary_directory:
        temporary = Path(temporary_directory)
        for entry, domain in selected:
            entry_id = str(entry.get("id") or "").strip()
            if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", entry_id):
                raise BrandIconSyncError(f"invalid registry id {entry_id!r}")
            brand = fetch_brand(domain, api_key)
            asset_url, extension = select_icon_asset(brand)
            payload, content_type = _request_bytes(asset_url)
            _validate_asset(payload, content_type, extension)
            staged_path = temporary / f"{entry_id}.{extension}"
            staged_path.write_bytes(payload)
            prepared.append(
                (entry, staged_path, payload, extension, hashlib.sha256(payload).hexdigest())
            )

        icons_dir.mkdir(parents=True, exist_ok=True)
        changed: list[str] = []
        for entry, staged_path, payload, extension, digest in prepared:
            entry_id = str(entry["id"])
            destination = icons_dir / f"{entry_id}.{extension}"
            previous = destination.read_bytes() if destination.exists() else None
            destination.write_bytes(staged_path.read_bytes())
            if previous != payload:
                changed.append(destination.as_posix())

            marketplace = entry.setdefault("marketplace", {})
            marketplace["icon_source"] = "brandfetch"
            marketplace["icon_refreshed_at"] = timestamp
            marketplace["icon_sha256"] = digest
            relative_path = destination.relative_to(registry_path.parent).as_posix()
            entry["icon_url"] = (
                f"https://raw.githubusercontent.com/{repository}/{branch}/{relative_path}"
            )

        registry_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
        changed.append(registry_path.as_posix())
        return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry-path", default="registry.json", type=Path)
    parser.add_argument("--icons-dir", default="icons/brands", type=Path)
    parser.add_argument("--api-key", default=os.environ.get("BRANDFETCH_API_KEY", ""))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_DEFAULT_BRANCH", "main"))
    parser.add_argument(
        "--cache-authorized",
        default=os.environ.get("BRANDFETCH_CACHE_ALLOWED", ""),
        help="Must be 'true' after Brandfetch cache/self-hosting rights are confirmed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if str(args.cache_authorized).strip().lower() != "true":
        raise SystemExit(
            "Refusing to cache Brandfetch assets: set BRANDFETCH_CACHE_ALLOWED=true only "
            "after confirming the account permits caching/self-hosting."
        )
    if not str(args.api_key).strip():
        raise SystemExit("BRANDFETCH_API_KEY is required; a Logo API client ID is not sufficient.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", str(args.repository)):
        raise SystemExit("--repository must use the owner/repository form")

    changed = synchronize(
        registry_path=args.registry_path.resolve(),
        icons_dir=args.icons_dir.resolve(),
        api_key=str(args.api_key).strip(),
        repository=str(args.repository),
        branch=str(args.branch),
    )
    print(f"Refreshed {len(changed) - 1} Brandfetch icon asset(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

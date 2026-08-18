from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


VALID_CATEGORIES = {
    "air_quality",
    "appliances",
    "climate",
    "energy",
    "lighting",
    "media",
    "mobility",
    "networking",
    "other",
    "security",
    "sensors",
    "weather",
}
VALID_CONNECTIVITY = {"local", "cloud", "hybrid"}
VALID_OFFLINE_SUPPORT = {"full", "partial", "none"}


def validate_marketplace_v2(
    marketplace: Any, *, entry_type: str = "integration"
) -> list[str]:
    errors: list[str] = []
    if not isinstance(marketplace, dict):
        return ["marketplace must be an object with metadata_version 2"]
    if marketplace.get("metadata_version") != 2:
        errors.append("marketplace.metadata_version must be 2")

    _require_text(marketplace, "display_name", errors)
    _require_text(marketplace, "summary", errors)
    if marketplace.get("category") not in VALID_CATEGORIES:
        errors.append(f"marketplace.category must be one of {sorted(VALID_CATEGORIES)}")
    if marketplace.get("connectivity") not in VALID_CONNECTIVITY:
        errors.append("marketplace.connectivity must be local, cloud, or hybrid")
    if marketplace.get("offline_support") not in VALID_OFFLINE_SUPPORT:
        errors.append("marketplace.offline_support must be full, partial, or none")

    for field in ("device_types", "protocols", "regions", "languages", "discovery_methods"):
        value = marketplace.get(field)
        if not isinstance(value, list) or not value or not all(_text(item) for item in value):
            errors.append(f"marketplace.{field} must be a non-empty list of strings")

    publisher = marketplace.get("publisher")
    if not isinstance(publisher, dict):
        errors.append("marketplace.publisher must be an object")
    else:
        _require_text(publisher, "name", errors, prefix="marketplace.publisher")
        _require_url(publisher, "support_url", errors, prefix="marketplace.publisher")
        contact = _text(publisher.get("security_contact"))
        if not contact or not (_valid_url(contact) or re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", contact)):
            errors.append("marketplace.publisher.security_contact must be an email or HTTP(S) URL")

    if "access" not in marketplace:
        errors.append("marketplace.access must be explicitly declared, including when empty")
    access = marketplace.get("access")
    if isinstance(access, list):
        seen_access: set[str] = set()
        for index, item in enumerate(access):
            if not isinstance(item, dict):
                errors.append(f"marketplace.access[{index}] must be an object")
                continue
            access_id = _text(item.get("id"))
            if not access_id:
                errors.append(f"marketplace.access[{index}].id is required")
            elif access_id in seen_access:
                errors.append(f"marketplace.access contains duplicate id '{access_id}'")
            seen_access.add(access_id)
            _require_text(item, "label", errors, prefix=f"marketplace.access[{index}]")
            _require_text(item, "reason", errors, prefix=f"marketplace.access[{index}]")
            if not isinstance(item.get("required", True), bool):
                errors.append(f"marketplace.access[{index}].required must be boolean")
    elif "access" in marketplace:
        errors.append("marketplace.access must be a list")

    compatibility = marketplace.get("compatibility")
    if entry_type == "integration" and (not isinstance(compatibility, list) or not compatibility):
        errors.append("marketplace.compatibility must list at least one supported device")
    if isinstance(compatibility, list):
        for index, item in enumerate(compatibility):
            if not isinstance(item, dict):
                errors.append(f"marketplace.compatibility[{index}] must be an object")
                continue
            _require_text(item, "brand", errors, prefix=f"marketplace.compatibility[{index}]")
            _require_text(item, "model", errors, prefix=f"marketplace.compatibility[{index}]")

    for field in ("documentation_url", "support_url", "changelog_url"):
        _require_url(marketplace, field, errors)
    if marketplace.get("connectivity") in {"cloud", "hybrid"}:
        _require_url(marketplace, "privacy_url", errors)
    return errors


def _text(value: Any) -> str:
    return str(value or "").strip()


def _valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _require_text(
    payload: dict[str, Any], field: str, errors: list[str], *, prefix: str = "marketplace"
) -> None:
    if not _text(payload.get(field)):
        errors.append(f"{prefix}.{field} is required")


def _require_url(
    payload: dict[str, Any], field: str, errors: list[str], *, prefix: str = "marketplace"
) -> None:
    if not _valid_url(_text(payload.get(field))):
        errors.append(f"{prefix}.{field} must be an HTTP(S) URL")

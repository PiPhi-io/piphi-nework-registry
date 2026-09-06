from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


VALID_CATEGORIES = {
    "air_quality",
    "appliances",
    "climate",
    "camera",
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
VALID_PUBLICATION_STATUSES = {"draft", "beta", "stable", "paused", "withdrawn"}
VALID_LIFECYCLE_STATUSES = {"active", "deprecated", "retired"}
VALID_QUALIFICATION_STATUSES = {"unverified", "passed", "failed", "expired"}
VALID_QUALITY_TIERS = {"unrated", "bronze", "silver", "gold", "platinum"}
SHA256_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


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
    if entry_type != "widget":
        if marketplace.get("connectivity") not in VALID_CONNECTIVITY:
            errors.append("marketplace.connectivity must be local, cloud, or hybrid")
        if marketplace.get("offline_support") not in VALID_OFFLINE_SUPPORT:
            errors.append("marketplace.offline_support must be full, partial, or none")

    _validate_governance(marketplace, errors)

    list_fields = ("regions", "languages") if entry_type == "widget" else (
        "device_types", "protocols", "regions", "languages", "discovery_methods"
    )
    for field in list_fields:
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
    if entry_type in {"integration", "widget"} and (not isinstance(compatibility, list) or not compatibility):
        errors.append("marketplace.compatibility must list at least one supported target")
    if isinstance(compatibility, list):
        for index, item in enumerate(compatibility):
            if not isinstance(item, dict):
                errors.append(f"marketplace.compatibility[{index}] must be an object")
                continue
            if entry_type == "widget":
                _require_text(item, "capability", errors, prefix=f"marketplace.compatibility[{index}]")
                _require_text(item, "host_protocol", errors, prefix=f"marketplace.compatibility[{index}]")
                _require_text(item, "widget_sdk", errors, prefix=f"marketplace.compatibility[{index}]")
            else:
                _require_text(item, "brand", errors, prefix=f"marketplace.compatibility[{index}]")
                _require_text(item, "model", errors, prefix=f"marketplace.compatibility[{index}]")

    for field in ("documentation_url", "support_url", "changelog_url"):
        _require_url(marketplace, field, errors)
    if entry_type != "widget" and marketplace.get("connectivity") in {"cloud", "hybrid"}:
        _require_url(marketplace, "privacy_url", errors)
    return errors


def _validate_governance(marketplace: dict[str, Any], errors: list[str]) -> None:
    quality_tier = _text(marketplace.get("quality_tier") or "unrated").lower()
    if quality_tier not in VALID_QUALITY_TIERS:
        errors.append(f"marketplace.quality_tier must be one of {sorted(VALID_QUALITY_TIERS)}")

    governance = marketplace.get("governance")
    if not isinstance(governance, dict):
        errors.append("marketplace.governance must be an object")
        return
    if governance.get("schema_version") != 1:
        errors.append("marketplace.governance.schema_version must be 1")

    publication = _text(governance.get("publication_status")).lower()
    lifecycle = _text(governance.get("lifecycle_status")).lower()
    rollout = governance.get("rollout_percent")
    if publication not in VALID_PUBLICATION_STATUSES:
        errors.append("marketplace.governance.publication_status is invalid")
    if lifecycle not in VALID_LIFECYCLE_STATUSES:
        errors.append("marketplace.governance.lifecycle_status is invalid")
    if isinstance(rollout, bool) or not isinstance(rollout, int) or not 0 <= rollout <= 100:
        errors.append("marketplace.governance.rollout_percent must be an integer from 0 to 100")
    elif publication == "beta" and not 1 <= rollout < 100:
        errors.append("marketplace.governance beta publication must use rollout_percent from 1 to 99")
    elif publication == "stable" and not 1 <= rollout <= 100:
        errors.append("marketplace.governance stable publication must use rollout_percent from 1 to 100")
    elif publication in {"draft", "paused", "withdrawn"} and rollout != 0:
        errors.append(f"marketplace.governance {publication} publication must use rollout_percent 0")

    notice = _text(governance.get("deprecation_notice"))
    if lifecycle in {"deprecated", "retired"} and not notice:
        errors.append("marketplace.governance.deprecation_notice is required for deprecated or retired apps")
    if lifecycle == "retired" and publication != "withdrawn":
        errors.append("marketplace.governance retired apps must use publication_status withdrawn")

    qualification = governance.get("qualification")
    if not isinstance(qualification, dict):
        errors.append("marketplace.governance.qualification must be an object")
        return
    status = _text(qualification.get("status") or "unverified").lower()
    if status not in VALID_QUALIFICATION_STATUSES:
        errors.append("marketplace.governance.qualification.status is invalid")
        return
    if quality_tier in {"silver", "gold", "platinum"} and status != "passed":
        errors.append(f"marketplace {quality_tier} quality requires passed qualification")
    if quality_tier in {"gold", "platinum"} and publication != "stable":
        errors.append(f"marketplace {quality_tier} quality requires stable publication")
    if quality_tier == "platinum" and rollout != 100:
        errors.append("marketplace platinum quality requires a 100 percent rollout")
    if status != "passed":
        return

    versions = qualification.get("tested_core_versions")
    if not isinstance(versions, list) or not versions or not all(_text(item) for item in versions):
        errors.append("marketplace.governance.qualification.tested_core_versions is required")
    _require_url(qualification, "evidence_url", errors, prefix="marketplace.governance.qualification")
    if not SHA256_DIGEST.fullmatch(_text(qualification.get("report_digest"))):
        errors.append("marketplace.governance.qualification.report_digest must be an immutable sha256 digest")
    if not SHA256_DIGEST.fullmatch(_text(qualification.get("runtime_image_digest"))):
        errors.append("marketplace.governance.qualification.runtime_image_digest must be an immutable sha256 digest")
    if not GIT_SHA.fullmatch(_text(qualification.get("core_source_commit"))):
        errors.append("marketplace.governance.qualification.core_source_commit must be a full Git SHA")
    tested_at = _text(qualification.get("tested_at"))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", tested_at):
        errors.append("marketplace.governance.qualification.tested_at must be an ISO 8601 timestamp")


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

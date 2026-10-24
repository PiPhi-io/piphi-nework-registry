from __future__ import annotations

from typing import Any

ONBOARDING_MODES = {"manual", "discovery", "account", "service", "none"}


def validate_onboarding(value: object, *, entry_type: str) -> list[str]:
    if entry_type == "widget":
        return [] if value is None else ["widget entries must not declare integration onboarding"]
    if not isinstance(value, dict):
        return ["onboarding must be an object"]
    if set(value) != {"mode"}:
        return ["onboarding must contain only mode"]
    mode = value.get("mode")
    if mode not in ONBOARDING_MODES:
        return [f"onboarding.mode must be one of {sorted(ONBOARDING_MODES)}"]
    if entry_type == "platform_service" and mode != "service":
        return ["platform_service entries must use onboarding.mode=service"]
    if entry_type == "integration" and mode == "service":
        return ["integration entries cannot use onboarding.mode=service"]
    return []


def require_manifest_onboarding(manifest: dict[str, Any], *, entry_type: str) -> dict[str, str] | None:
    value = manifest.get("onboarding")
    errors = validate_onboarding(value, entry_type=entry_type)
    if errors:
        raise ValueError("Manifest onboarding contract is invalid: " + "; ".join(errors))
    return value if isinstance(value, dict) else None


def infer_entry_onboarding(entry: dict[str, Any]) -> dict[str, str] | None:
    entry_type = str(entry.get("type") or "integration")
    if entry_type == "widget":
        return None
    if entry_type == "platform_service" or entry.get("deployment_mode") == "sidecar":
        return {"mode": "service"}
    methods = [
        str(value).strip().lower()
        for value in ((entry.get("marketplace") or {}).get("discovery_methods") or [])
        if str(value).strip()
    ]
    if any("account" in method for method in methods):
        return {"mode": "account"}
    manual_markers = ("manual", "configured", "configuration", "profile", "project import", "address")
    active = [method for method in methods if not any(marker in method for marker in manual_markers)]
    return {"mode": "discovery" if active else "manual"}

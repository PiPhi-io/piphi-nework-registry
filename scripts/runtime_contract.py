from __future__ import annotations

from typing import Any

RUNTIME_CONTRACT_VERSION = 1
MANAGED_PORT_BINDING = "core_allocated"
WIDGET_PORT_BINDING = "not_applicable"


def expected_runtime_contract(entry_type: str) -> dict[str, Any] | None:
    if entry_type == "platform_service":
        return {
            "version": RUNTIME_CONTRACT_VERSION,
            "port_binding": MANAGED_PORT_BINDING,
            "port_env": "PORT",
        }
    if entry_type == "widget":
        return {
            "version": RUNTIME_CONTRACT_VERSION,
            "port_binding": WIDGET_PORT_BINDING,
        }
    return None


def validate_runtime_contract(value: object, *, entry_type: str) -> list[str]:
    expected = expected_runtime_contract(entry_type)
    if expected is None:
        if value is None:
            return []
        if not isinstance(value, dict):
            return ["runtime_contract must be an object"]
        if value.get("version") != RUNTIME_CONTRACT_VERSION:
            return [f"runtime_contract.version must be {RUNTIME_CONTRACT_VERSION}"]
        if value.get("port_binding") != MANAGED_PORT_BINDING:
            return ["integration runtime_contract.port_binding must be core_allocated"]
        if value.get("port_env") != "PORT":
            return ["core_allocated runtime contracts must use port_env=PORT"]
        return []

    if not isinstance(value, dict):
        return ["runtime_contract is required and must be an object"]
    if value != expected:
        if entry_type == "widget":
            return ["widget runtime_contract must be exactly version=1 and port_binding=not_applicable"]
        return [
            "platform_service runtime_contract must be exactly version=1, "
            "port_binding=core_allocated, and port_env=PORT"
        ]
    return []


def require_manifest_runtime_contract(manifest: dict[str, Any], *, entry_type: str) -> dict[str, Any] | None:
    value = manifest.get("runtime_contract")
    errors = validate_runtime_contract(value, entry_type=entry_type)
    if errors:
        raise ValueError("Manifest runtime contract is invalid: " + "; ".join(errors))
    if entry_type == "platform_service":
        runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), dict) else {}
        linux = runtime.get("linux") if isinstance(runtime.get("linux"), dict) else {}
        container = linux.get("container") if isinstance(linux.get("container"), dict) else {}
        ports = container.get("ports") if isinstance(container, dict) else None
        primary = ports[0] if isinstance(ports, list) and ports and isinstance(ports[0], dict) else {}
        if "host" in primary:
            raise ValueError("Manifest runtime contract is invalid: the primary managed port must not pin host")
        environment = container.get("environment") if isinstance(container, dict) else None
        if isinstance(environment, dict) and "PORT" in environment:
            raise ValueError("Manifest runtime contract is invalid: Core owns the PORT environment value")
    if isinstance(value, dict):
        return dict(value)
    return expected_runtime_contract(entry_type)

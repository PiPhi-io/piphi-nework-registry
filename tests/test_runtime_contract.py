import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime_contract import (  # noqa: E402
    expected_runtime_contract,
    require_manifest_runtime_contract,
    validate_runtime_contract,
)


def test_platform_services_use_core_allocated_port_contract() -> None:
    expected = {"version": 1, "port_binding": "core_allocated", "port_env": "PORT"}
    assert expected_runtime_contract("platform_service") == expected
    assert validate_runtime_contract(expected, entry_type="platform_service") == []


def test_widgets_explicitly_exclude_listener_ports() -> None:
    expected = {"version": 1, "port_binding": "not_applicable"}
    assert expected_runtime_contract("widget") == expected
    assert validate_runtime_contract(expected, entry_type="widget") == []


def test_contract_rejects_cross_kind_shapes() -> None:
    assert validate_runtime_contract(
        {"version": 1, "port_binding": "not_applicable"}, entry_type="platform_service"
    )


def test_managed_manifest_cannot_pin_the_core_allocated_port() -> None:
    manifest = {
        "runtime_contract": {"version": 1, "port_binding": "core_allocated", "port_env": "PORT"},
        "runtime": {"linux": {"container": {"ports": [{"container": 8090, "host": 8090}]}}},
    }
    try:
        require_manifest_runtime_contract(manifest, entry_type="platform_service")
    except ValueError as error:
        assert "must not pin host" in str(error)
    else:
        raise AssertionError("expected a pinned primary host port to be rejected")
    assert validate_runtime_contract(
        {"version": 1, "port_binding": "core_allocated", "port_env": "PORT"}, entry_type="widget"
    )

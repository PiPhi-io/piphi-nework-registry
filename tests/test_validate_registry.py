from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "validate_registry.py"
SPEC = importlib.util.spec_from_file_location("validate_registry", SCRIPT_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def valid_entry() -> dict:
    return {
        "id": "demo",
        "name": "Demo",
        "version": "1.0.0",
        "type": "integration",
        "trust_level": "official",
        "risk_level": "low",
        "description": "Demo",
        "platforms": ["linux"],
        "owner": "PiPhi-io",
        "repo_name": "demo",
        "repo_url": "https://github.com/PiPhi-io/demo",
        "manifest_path": "manifest.json",
        "maintainer": {"name": "PiPhi"},
        "marketplace": valid_marketplace(),
    }


def valid_marketplace() -> dict:
    return {
        "metadata_version": 2,
        "display_name": "Demo Devices",
        "summary": "Connect supported Demo devices to your home.",
        "category": "other",
        "device_types": ["device"],
        "protocols": ["http"],
        "regions": ["WW"],
        "languages": ["en"],
        "discovery_methods": ["manual"],
        "connectivity": "local",
        "offline_support": "full",
        "publisher": {
            "name": "PiPhi",
            "support_url": "https://example.com/support",
            "security_contact": "security@example.com",
        },
        "access": [],
        "compatibility": [{"brand": "Demo", "model": "One"}],
        "documentation_url": "https://example.com/docs",
        "support_url": "https://example.com/support",
        "changelog_url": "https://example.com/releases",
    }


class RegistryBrandMetadataValidationTests(unittest.TestCase):
    def test_accepts_safe_packaged_brand_path(self) -> None:
        entry = valid_entry()
        entry["brand_path"] = "src/brand"
        self.assertEqual(VALIDATOR.validate_entry(entry, 0), [])

    def test_rejects_brand_path_traversal(self) -> None:
        entry = valid_entry()
        entry["brand_path"] = "../private"
        errors = VALIDATOR.validate_entry(entry, 0)
        self.assertTrue(any("brand_path" in error for error in errors))

    def test_accepts_brand_domain_before_first_asset_refresh(self) -> None:
        entry = valid_entry()
        entry["marketplace"]["brand_domain"] = "example.com"
        self.assertEqual(VALIDATOR.validate_entry(entry, 0), [])

    def test_rejects_untracked_brandfetch_asset(self) -> None:
        entry = valid_entry()
        entry["marketplace"].update({"brand_domain": "example.com", "icon_source": "brandfetch"})
        errors = VALIDATOR.validate_entry(entry, 0)
        self.assertTrue(any("icon_refreshed_at" in error for error in errors))
        self.assertTrue(any("icon_sha256" in error for error in errors))

    def test_rejects_legacy_marketplace_metadata(self) -> None:
        entry = valid_entry()
        entry["marketplace"] = {"connectivity": "local"}
        errors = VALIDATOR.validate_entry(entry, 0)
        self.assertTrue(any("metadata_version must be 2" in error for error in errors))

    def test_rejects_omitted_access_declaration(self) -> None:
        entry = valid_entry()
        del entry["marketplace"]["access"]
        errors = VALIDATOR.validate_entry(entry, 0)
        self.assertTrue(any("access must be explicitly declared" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

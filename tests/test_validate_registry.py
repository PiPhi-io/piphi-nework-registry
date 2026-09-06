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
        "quality_tier": "unrated",
        "governance": {
            "schema_version": 1,
            "publication_status": "stable",
            "rollout_percent": 100,
            "lifecycle_status": "active",
            "qualification": {"status": "unverified"},
        },
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
    def test_accepts_zero_rollout_widget_with_pending_release_integrity(self) -> None:
        entry = valid_entry()
        entry.update({
            "id": "io.piphi.webrtc.camera",
            "type": "widget",
            "platforms": ["web"],
            "artifact": {"release_asset": "piphi-webrtc-camera-widget-0.1.0.tgz", "integrity": None},
        })
        entry["marketplace"] = {
            **valid_marketplace(),
            "category": "camera",
            "governance": {
                "schema_version": 1, "publication_status": "draft", "rollout_percent": 0,
                "lifecycle_status": "active", "qualification": {"status": "unverified"},
            },
            "compatibility": [{
                "capability": "camera_stream", "host_protocol": "piphi.widget.host/1", "widget_sdk": ">=0.4.0",
            }],
        }
        for field in ("device_types", "protocols", "discovery_methods", "connectivity", "offline_support"):
            entry["marketplace"].pop(field, None)
        self.assertEqual(VALIDATOR.validate_entry(entry, 0), [])

    def test_published_widget_requires_immutable_artifact_integrity(self) -> None:
        entry = valid_entry()
        entry.update({"type": "widget", "platforms": ["web"], "artifact": {"release_asset": "widget.tgz", "integrity": None}})
        entry["marketplace"]["compatibility"] = [{"capability": "camera", "host_protocol": "piphi.widget.host/1", "widget_sdk": ">=0.4.0"}]
        errors = VALIDATOR.validate_entry(entry, 0)
        self.assertTrue(any("artifact.integrity is required" in error for error in errors))

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

    def test_rejects_listing_without_governance(self) -> None:
        entry = valid_entry()
        del entry["marketplace"]["governance"]
        errors = VALIDATOR.validate_entry(entry, 0)
        self.assertTrue(any("governance must be an object" in error for error in errors))

    def test_allows_stable_unverified_listing_without_quality_claim(self) -> None:
        self.assertEqual(VALIDATOR.validate_entry(valid_entry(), 0), [])

    def test_verified_quality_requires_immutable_evidence(self) -> None:
        entry = valid_entry()
        entry["marketplace"]["quality_tier"] = "silver"
        errors = VALIDATOR.validate_entry(entry, 0)
        self.assertTrue(any("silver quality requires passed qualification" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

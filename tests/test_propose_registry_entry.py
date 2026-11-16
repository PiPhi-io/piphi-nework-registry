from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from propose_registry_entry import (
    integration_entry,
    preserve_reviewed_fields,
    serialize_registry_change,
    widget_entry,
)


class ProposeRegistryEntryTests(unittest.TestCase):
    def test_widget_entry_normalizes_package_identity_and_artifact(self) -> None:
        source = {
            "identity": {"publisher_id": "io.example", "package_id": "room-air", "version": "0.2.0"},
            "name": "Room Air",
            "description": "Room air readings.",
            "sdk_version_range": ">=0.6.1,<0.7",
            "widgets": [{"binding_slots": [{"capability_requirements": ["co2", "humidity"]}]}],
        }
        entry = widget_entry(
            source,
            "https://github.com/example/room-air-widget",
            "package.source.json",
            "v0.2.0",
            "sha256:" + "a" * 64,
        )
        self.assertEqual(entry["id"], "io.example.room-air")
        self.assertEqual(entry["artifact"]["release_asset"], "room-air-0.2.0.zip")
        self.assertEqual(entry["marketplace"]["governance"]["publication_status"], "draft")
        self.assertEqual(
            [item["capability"] for item in entry["marketplace"]["compatibility"]],
            ["co2", "humidity"],
        )

    def test_existing_reviewed_governance_and_trust_are_preserved(self) -> None:
        entry = {
            "trust_level": "community",
            "maintainer": {"name": "Example"},
            "marketplace": {
                "quality_tier": "unrated",
                "governance": {"publication_status": "draft", "rollout_percent": 0},
            },
        }
        existing = {
            "trust_level": "official",
            "icon_url": "https://example.com/icon.svg",
            "tags": ["reviewed"],
            "maintainer": {"support_email": "support@example.com"},
            "marketplace": {
                "quality_tier": "bronze",
                "governance": {"publication_status": "stable", "rollout_percent": 100},
            },
        }
        updated = preserve_reviewed_fields(entry, existing)
        self.assertEqual(updated["trust_level"], "official")
        self.assertEqual(updated["icon_url"], "https://example.com/icon.svg")
        self.assertEqual(updated["tags"], ["reviewed"])
        self.assertEqual(
            updated["maintainer"]["support_email"], "support@example.com"
        )
        self.assertEqual(updated["marketplace"]["quality_tier"], "bronze")
        self.assertEqual(updated["marketplace"]["governance"]["publication_status"], "stable")

    def test_widget_entry_rejects_mutable_release_ref(self) -> None:
        source = {
            "identity": {"publisher_id": "io.example", "package_id": "room-air", "version": "0.2.0"},
            "name": "Room Air",
            "description": "Room air readings.",
            "widgets": [],
        }
        with self.assertRaisesRegex(ValueError, "does not match io.example.room-air version"):
            widget_entry(source, "https://github.com/example/widget", "package.source.json", "main", "")

    def test_integration_entry_accepts_namespaced_ref_and_digest(self) -> None:
        source = {
            "id": "example-integration",
            "name": "Example",
            "version": "1.2.3",
            "description": "Example integration.",
            "platforms": ["linux"],
            "image": "ghcr.io/example/example-integration:1.2.3",
            "onboarding": {"mode": "manual"},
            "runtime_contract": {
                "version": 1,
                "port_binding": "core_allocated",
                "port_env": "PORT",
            },
            "marketplace": {
                "metadata_version": 2,
                "display_name": "Example",
                "summary": "Example integration.",
                "category": "other",
                "regions": ["WW"],
                "languages": ["en"],
                "publisher": {
                    "name": "Example",
                    "website_url": "https://example.com",
                    "support_url": "https://example.com/support",
                    "security_contact": "security@example.com",
                },
                "access": [],
                "compatibility": [{"brand": "Example", "model": "Example"}],
                "documentation_url": "https://example.com/docs",
                "support_url": "https://example.com/support",
                "changelog_url": "https://example.com/changelog",
                "quality_tier": "unrated",
                "governance": {
                    "schema_version": 1,
                    "publication_status": "draft",
                    "rollout_percent": 0,
                    "lifecycle_status": "active",
                    "qualification": {"status": "unverified"},
                },
                "device_types": ["other"],
                "protocols": ["other"],
                "discovery_methods": ["manual"],
                "connectivity": "local",
                "offline_support": "full",
            },
        }
        digest = "sha256:" + "b" * 64
        entry = integration_entry(
            source,
            "https://github.com/example/apps",
            "apps/example-integration/manifest.json",
            "apps/example-integration/v1.2.3",
            digest,
        )
        self.assertEqual(entry["ref"], "apps/example-integration/v1.2.3")
        self.assertEqual(entry["image_digest"], digest)

    def test_integration_entry_infers_sidecar_from_service_onboarding(self) -> None:
        source = {
            "id": "example-sidecar",
            "name": "Example sidecar",
            "version": "1.2.3",
            "description": "Example sidecar.",
            "platforms": ["linux"],
            "image": "ghcr.io/example/example-sidecar:1.2.3",
            "onboarding": {"mode": "service"},
            "runtime_contract": {
                "version": 1,
                "port_binding": "core_allocated",
                "port_env": "PORT",
            },
            "marketplace": {
                "metadata_version": 2,
                "display_name": "Example sidecar",
                "summary": "Example sidecar.",
                "category": "other",
                "regions": ["WW"],
                "languages": ["en"],
                "publisher": {
                    "name": "Example",
                    "website_url": "https://example.com",
                    "support_url": "https://example.com/support",
                    "security_contact": "security@example.com",
                },
                "access": [
                    {
                        "id": "device_access",
                        "label": "Device access",
                        "reason": "Communicates with a configured local device.",
                        "required": True,
                    }
                ],
                "compatibility": [{"brand": "Example", "model": "Example"}],
                "documentation_url": "https://example.com/docs",
                "support_url": "https://example.com/support",
                "changelog_url": "https://example.com/changelog",
                "quality_tier": "unrated",
                "governance": {
                    "schema_version": 1,
                    "publication_status": "draft",
                    "rollout_percent": 0,
                    "lifecycle_status": "active",
                    "qualification": {"status": "unverified"},
                },
                "device_types": ["other"],
                "protocols": ["other"],
                "discovery_methods": ["manual"],
                "connectivity": "local",
                "offline_support": "full",
            },
        }
        entry = integration_entry(
            source,
            "https://github.com/example/apps",
            "apps/example-sidecar/manifest.json",
            "apps/example-sidecar/v1.2.3",
        )
        self.assertEqual(entry["type"], "platform_service")
        self.assertEqual(entry["deployment_mode"], "sidecar")
        self.assertEqual(
            entry["runtime_requirements"],
            ["sidecar_runtime", "usb_or_device_access", "direct_hardware_access"],
        )
        self.assertEqual(entry["risk_level"], "moderate")

    def test_serialization_preserves_unrelated_registry_formatting(self) -> None:
        original = '[\n  {\n    "id": "existing",\n    "platforms": ["web"]\n  }\n]\n'
        added = serialize_registry_change(
            original,
            "new-widget",
            {"id": "new-widget", "platforms": ["web"]},
            exists=False,
        )
        self.assertIn('"platforms": ["web"]', added)
        self.assertEqual(added.count('"id": "existing"'), 1)
        self.assertEqual(added.count('"id": "new-widget"'), 1)

        updated = serialize_registry_change(
            original,
            "existing",
            {"id": "existing", "platforms": ["linux"]},
            exists=True,
        )
        self.assertIn('"platforms": [\n      "linux"\n    ]', updated)
        self.assertNotIn('"platforms": ["web"]', updated)


if __name__ == "__main__":
    unittest.main()

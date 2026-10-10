from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from propose_registry_entry import preserve_reviewed_fields, widget_entry


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
            "marketplace": {
                "quality_tier": "unrated",
                "governance": {"publication_status": "draft", "rollout_percent": 0},
            },
        }
        existing = {
            "trust_level": "official",
            "icon_url": "https://example.com/icon.svg",
            "marketplace": {
                "quality_tier": "bronze",
                "governance": {"publication_status": "stable", "rollout_percent": 100},
            },
        }
        updated = preserve_reviewed_fields(entry, existing)
        self.assertEqual(updated["trust_level"], "official")
        self.assertEqual(updated["icon_url"], "https://example.com/icon.svg")
        self.assertEqual(updated["marketplace"]["quality_tier"], "bronze")
        self.assertEqual(updated["marketplace"]["governance"]["publication_status"], "stable")

    def test_widget_entry_rejects_mutable_release_ref(self) -> None:
        source = {
            "identity": {"publisher_id": "io.example", "package_id": "room-air", "version": "0.2.0"},
            "name": "Room Air",
            "description": "Room air readings.",
            "widgets": [],
        }
        with self.assertRaisesRegex(ValueError, "must match widget version"):
            widget_entry(source, "https://github.com/example/widget", "package.source.json", "main", "")


if __name__ == "__main__":
    unittest.main()

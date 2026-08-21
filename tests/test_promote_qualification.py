from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "promote_qualification.py"
SPEC = importlib.util.spec_from_file_location("promote_qualification", SCRIPT_PATH)
assert SPEC and SPEC.loader
PROMOTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROMOTION)


def passing_report(runtime_name: str = "demo") -> dict:
    return {
        "schema_version": 2,
        "runtime_name": runtime_name,
        "image_digest": "sha256:" + "a" * 64,
        "core_source_commit": "b" * 40,
        "base_url": "http://runtime.test",
        "command_path": "/command",
        "health_status": 200,
        "contract_status": 200,
        "entities_status": 200,
        "events_status": 200,
        "health_contract_valid": True,
        "runtime_contract_valid": True,
        "entities_contract_valid": True,
        "events_contract_valid": True,
        "first_status": 200,
        "replay_status": 200,
        "command_id": "command-id",
        "idempotency_key": "qualification:demo",
        "explicit_replay_acknowledgement": True,
        "passed": True,
        "failures": [],
    }


def registry_entries() -> list[dict]:
    return [{
        "id": "demo",
        "marketplace": {
            "quality_tier": "bronze",
            "governance": {
                "schema_version": 1,
                "publication_status": "stable",
                "rollout_percent": 100,
                "lifecycle_status": "active",
                "qualification": {"status": "unverified"},
            },
        },
    }]


class RuntimeQualificationPromotionTests(unittest.TestCase):
    def test_promotes_passing_runtime_to_silver_with_immutable_evidence(self) -> None:
        entries = registry_entries()
        entry = PROMOTION.promote_entry(
            entries,
            registry_id="demo",
            report=passing_report(),
            evidence_url="https://github.com/PiPhi-io/PiPhi-Network-Core/actions/runs/123",
            core_version="2.4.0",
            tested_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        )
        self.assertEqual(entry["marketplace"]["quality_tier"], "silver")
        evidence = entry["marketplace"]["governance"]["qualification"]
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["runtime_image_digest"], "sha256:" + "a" * 64)
        self.assertEqual(evidence["core_source_commit"], "b" * 40)
        self.assertTrue(evidence["report_digest"].startswith("sha256:"))

    def test_rejects_report_for_another_runtime(self) -> None:
        with self.assertRaisesRegex(ValueError, "runtime_name"):
            PROMOTION.promote_entry(
                registry_entries(),
                registry_id="demo",
                report=passing_report("other"),
                evidence_url="https://example.test/evidence",
                core_version="2.4.0",
                tested_at=datetime.now(timezone.utc),
            )

    def test_rejects_report_with_failed_contract_flag(self) -> None:
        report = passing_report()
        report["events_contract_valid"] = False
        with self.assertRaisesRegex(ValueError, "events_contract_valid"):
            PROMOTION.promote_entry(
                registry_entries(),
                registry_id="demo",
                report=report,
                evidence_url="https://example.test/evidence",
                core_version="2.4.0",
                tested_at=datetime.now(timezone.utc),
            )

    def test_does_not_overwrite_higher_quality_tier(self) -> None:
        entries = registry_entries()
        entries[0]["marketplace"]["quality_tier"] = "gold"
        entry = PROMOTION.promote_entry(
            entries,
            registry_id="demo",
            report=passing_report(),
            evidence_url="https://example.test/evidence",
            core_version="2.4.0",
            tested_at=datetime.now(timezone.utc),
        )
        self.assertEqual(entry["marketplace"]["quality_tier"], "gold")


if __name__ == "__main__":
    unittest.main()

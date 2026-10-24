import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from migrate_onboarding_contract import migrate  # noqa: E402
from onboarding_contract import infer_entry_onboarding, validate_onboarding  # noqa: E402


class OnboardingContractTests(unittest.TestCase):
    def test_infers_onboarding_from_catalog_semantics(self) -> None:
        self.assertEqual(infer_entry_onboarding({"type": "platform_service"}), {"mode": "service"})
        self.assertIsNone(infer_entry_onboarding({"type": "widget"}))
        self.assertEqual(infer_entry_onboarding({"type": "integration", "marketplace": {"discovery_methods": ["account", "manual"]}}), {"mode": "account"})
        self.assertEqual(infer_entry_onboarding({"type": "integration", "marketplace": {"discovery_methods": ["mDNS", "manual"]}}), {"mode": "discovery"})
        self.assertEqual(infer_entry_onboarding({"type": "integration", "marketplace": {"discovery_methods": ["manual"]}}), {"mode": "manual"})

    def test_migration_is_idempotent(self) -> None:
        entries = [
            {"type": "integration", "marketplace": {"discovery_methods": ["manual"]}},
            {"type": "widget", "onboarding": {"mode": "none"}},
        ]
        self.assertEqual(migrate(entries), 2)
        self.assertEqual(migrate(entries), 0)

    def test_rejects_service_mode_for_an_integration(self) -> None:
        self.assertEqual(validate_onboarding({"mode": "service"}, entry_type="integration"), [
            "integration entries cannot use onboarding.mode=service"
        ])


if __name__ == "__main__":
    unittest.main()

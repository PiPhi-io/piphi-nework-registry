from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "sync_brandfetch_icons.py"
SPEC = importlib.util.spec_from_file_location("sync_brandfetch_icons", SCRIPT_PATH)
assert SPEC and SPEC.loader
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


class BrandfetchIconSyncTests(unittest.TestCase):
    def test_selects_square_icon_before_logo(self) -> None:
        brand = {
            "logos": [
                {"type": "logo", "formats": [{"format": "png", "src": "https://assets/logo.png"}]},
                {
                    "type": "icon",
                    "formats": [
                        {"format": "svg", "src": "https://assets/icon.svg"},
                        {"format": "webp", "src": "https://assets/icon.webp"},
                    ],
                },
            ]
        }
        self.assertEqual(SYNC.select_icon_asset(brand), ("https://assets/icon.webp", "webp"))

    def test_rejects_invalid_brand_domain(self) -> None:
        with self.assertRaisesRegex(SYNC.BrandIconSyncError, "invalid brand_domain"):
            SYNC._brand_entries(
                [{"id": "unsafe", "marketplace": {"brand_domain": "https://example.com"}}]
            )

    def test_synchronizes_asset_and_registry_metadata(self) -> None:
        png = b"\x89PNG\r\n\x1a\nbrand-icon"
        brand = {
            "logos": [
                {"type": "icon", "formats": [{"format": "png", "src": "https://assets/icon.png"}]}
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "registry.json"
            registry_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "demo-brand",
                            "icon_url": "https://example.test/old.svg",
                            "marketplace": {"brand_domain": "example.com"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with (
                patch.object(SYNC, "fetch_brand", return_value=brand),
                patch.object(SYNC, "_request_bytes", return_value=(png, "image/png")),
            ):
                SYNC.synchronize(
                    registry_path=registry_path,
                    icons_dir=root / "icons" / "brands",
                    api_key="test-key",
                    repository="PiPhi-io/registry",
                    branch="main",
                    refreshed_at="2026-08-16T00:00:00+00:00",
                )

            entry = json.loads(registry_path.read_text(encoding="utf-8"))[0]
            self.assertEqual(
                entry["icon_url"],
                "https://raw.githubusercontent.com/PiPhi-io/registry/main/icons/brands/demo-brand.png",
            )
            self.assertEqual(entry["marketplace"]["icon_source"], "brandfetch")
            self.assertEqual(entry["marketplace"]["icon_refreshed_at"], "2026-08-16T00:00:00+00:00")
            self.assertTrue((root / "icons" / "brands" / "demo-brand.png").exists())


if __name__ == "__main__":
    unittest.main()

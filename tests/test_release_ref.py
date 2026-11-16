from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from release_ref import require_release_ref  # noqa: E402


class ReleaseRefTests(unittest.TestCase):
    def test_accepts_standalone_and_namespaced_tags(self) -> None:
        require_release_ref("v1.2.3", registry_id="example", version="1.2.3")
        require_release_ref(
            "apps/example/v1.2.3", registry_id="example", version="1.2.3"
        )

    def test_rejects_mutable_wrong_package_or_wrong_version(self) -> None:
        for ref in ("main", "apps/other/v1.2.3", "apps/example/v1.2.4"):
            with self.subTest(ref=ref), self.assertRaisesRegex(
                ValueError, "does not match example version 1.2.3"
            ):
                require_release_ref(ref, registry_id="example", version="1.2.3")


if __name__ == "__main__":
    unittest.main()

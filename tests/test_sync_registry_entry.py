from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_registry_entry import image_repository, serialize_updated_entry  # noqa: E402


def test_image_repository_removes_a_tag_or_digest() -> None:
    assert image_repository("piphinetwork/example:1.2.3") == "piphinetwork/example"
    assert image_repository("ghcr.io/piphi/example@sha256:abc") == "ghcr.io/piphi/example"


def test_serialize_updated_entry_changes_only_the_requested_object() -> None:
    original = """[
  {
    "id": "first",
    "values": ["keep", "compact"]
  },
  {
    "id": "target",
    "version": "1.0.0",
    "image": "piphinetwork/target:1.0.0",
    "owner": "PiPhi-io"
  },
  {"id": "last", "format": "must remain untouched"}
]
"""
    entries = json.loads(original)
    target = entries[1]
    target["version"] = "1.0.1"
    target["image"] = "piphinetwork/target:1.0.1"
    target["ref"] = "v1.0.1"

    updated = serialize_updated_entry(original, "target", target)

    assert '"values": ["keep", "compact"]' in updated
    assert '{"id": "last", "format": "must remain untouched"}' in updated
    assert '"image": "piphinetwork/target:1.0.1"' in updated
    assert '"ref": "v1.0.1"' in updated
    assert json.loads(updated)[1]["owner"] == "PiPhi-io"

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime_contract import expected_runtime_contract


def migrate(entries: list[dict[str, object]]) -> int:
    changed = 0
    for entry in entries:
        expected = expected_runtime_contract(str(entry.get("type") or ""))
        if expected is not None and entry.get("runtime_contract") != expected:
            entry["runtime_contract"] = expected
            changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Add managed-runtime contract metadata to registry entries.")
    parser.add_argument("path", nargs="?", default="registry.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(args.path)
    entries = json.loads(path.read_text(encoding="utf-8"))
    changed = migrate(entries)
    if args.check:
        print(f"{changed} registry entries need runtime-contract migration." if changed else "Registry runtime contracts are current.")
        return 1 if changed else 0
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {changed} registry entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

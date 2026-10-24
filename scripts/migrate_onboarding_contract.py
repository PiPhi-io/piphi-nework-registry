#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from onboarding_contract import infer_entry_onboarding


def migrate(entries: list[dict[str, object]]) -> int:
    changed = 0
    for entry in entries:
        inferred = infer_entry_onboarding(entry)
        if inferred is None:
            if "onboarding" in entry:
                del entry["onboarding"]
                changed += 1
            continue
        if entry.get("onboarding") != inferred:
            entry["onboarding"] = inferred
            changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate registry entries to the onboarding contract.")
    parser.add_argument("path", nargs="?", default="registry.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(args.path)
    entries = json.loads(path.read_text(encoding="utf-8"))
    changed = migrate(entries)
    if args.check:
        if changed:
            print(f"{changed} registry entries need onboarding migration.")
            return 1
        print("Registry onboarding migration is current.")
        return 0
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Migrated {changed} registry entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

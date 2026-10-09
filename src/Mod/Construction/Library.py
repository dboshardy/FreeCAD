# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: construction material library (design doc §5.1, §9). No FreeCAD imports.
"""Material library: JSON files under Resources/libraries/<region>/, plus user
overrides in <user data>/Construction/libraries/<region>/ (same file layout;
an item with the same id replaces the shipped one)."""

import json
import os

LIBRARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Resources", "libraries")


def _read(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", []) if isinstance(data, dict) else data
    return {item["id"]: item for item in items if "id" in item}


def load(dirs=None):
    """id -> item for every library file under dirs (later dirs override earlier)."""
    items = {}
    for root in dirs or [LIBRARY_DIR]:
        if not os.path.isdir(root):
            continue
        for region in sorted(os.listdir(root)):
            folder = os.path.join(root, region)
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder)):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(folder, name)
                try:
                    items.update(_read(path))
                except (OSError, ValueError, AttributeError) as e:
                    # A broken user file must not hide the rest of the library.
                    print(f"Construction library: skipped {path}: {e}")
    return items


def user_dir():
    import FreeCAD

    return os.path.join(FreeCAD.getUserAppDataDir(), "Construction", "libraries")


def sheets(items, region=None):
    """Sheet-goods items, optionally for one region, sorted by id."""
    return sorted(
        (
            i
            for i in items.values()
            if i.get("category") == "sheet_goods" and (region is None or i.get("region") == region)
        ),
        key=lambda i: i["id"],
    )


def mm(item, key):
    """Value of item['actual'][key] in millimetres."""
    actual = item["actual"]
    factor = {"mm": 1.0, "in": 25.4}[actual.get("unit", "mm")]
    return actual[key] * factor

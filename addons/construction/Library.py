# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: construction material library (design doc §5.1, §9). No FreeCAD imports.
"""Material library: JSON files under Resources/libraries/<region>/, plus user
overrides in <user data>/Construction/libraries/<region>/ (same file layout;
an item with the same id replaces the shipped one)."""

import json
import os

LIBRARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Resources", "libraries")


MATERIALS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Resources", "Materials")


def density_kg_m3(item):
    """Density from the item's Material workbench card (`material_card` UUID);
    None when the item has no card. Needs FreeCAD's Materials module."""
    uuid = item.get("material_card")
    if not uuid:
        return None
    import Materials

    manager = Materials.MaterialManager()
    try:
        card = manager.getMaterial(uuid)
    except LookupError:  # the manager started before Init.py registered our library
        manager.refresh()
        card = manager.getMaterial(uuid)
    return card.getPhysicalValue("Density").getValueAs("kg/m^3").Value


def _read(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", []) if isinstance(data, dict) else data
    # A file's "defaults" apply to each of its items unless the item sets the key.
    defaults = data.get("defaults", {}) if isinstance(data, dict) else {}
    return {item["id"]: {**defaults, **item} for item in items if "id" in item}


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


SHEET_GOODS = "sheet_goods"
LUMBER = "dimensional_lumber"


def of_category(items, category, region=None):
    """Items of one category, optionally for one region, sorted by id."""
    return sorted(
        (
            i
            for i in items.values()
            if i.get("category") == category and (region is None or i.get("region") == region)
        ),
        key=lambda i: i["id"],
    )


def mm(item, key):
    """Value of item['actual'][key] in millimetres."""
    actual = item["actual"]
    factor = {"mm": 1.0, "in": 25.4}[actual.get("unit", "mm")]
    return actual[key] * factor


# ------------------------------------------------------------ editing as rows

AREA_MATERIAL = "area_material"
HARDWARE = "hardware"
# Columns per category: (column, getter key path, kind). Paths: "id", "name",
# "actual.w", ... ; kinds: text, number, numbers (space separated), choice.
COLUMNS = {
    LUMBER: [
        ("id", "id", "text"),
        ("name", "name", "text"),
        ("thickness", "actual.w", "number"),
        ("depth", "actual.h", "number"),
        ("unit", "actual.unit", "text"),
        ("stock lengths mm", "stock_lengths_mm", "numbers"),
        ("price", "price", "number"),
        ("price per", "price_per", "text"),
        ("region", "region", "text"),
    ],
    SHEET_GOODS: [
        ("id", "id", "text"),
        ("name", "name", "text"),
        ("length", "actual.h", "number"),
        ("width", "actual.w", "number"),
        ("thickness", "actual.t", "number"),
        ("unit", "actual.unit", "text"),
        ("grain", "grain_axis", "text"),
        ("price", "price", "number"),
        ("region", "region", "text"),
    ],
    HARDWARE: [
        ("id", "id", "text"),
        ("name", "name", "text"),
        ("price", "price", "number"),
        ("region", "region", "text"),
    ],
    AREA_MATERIAL: [
        ("id", "id", "text"),
        ("name", "name", "text"),
        ("coverage m2", "coverage_m2", "number"),
        ("waste", "waste", "number"),
        ("price", "price", "number"),
        ("region", "region", "text"),
    ],
}
REQUIRED = {"id", "name"}


def _get(item, path):
    for key in path.split("."):
        item = item.get(key) if isinstance(item, dict) else None
    return item


def _set(item, path, value):
    *parents, last = path.split(".")
    for key in parents:
        item = item.setdefault(key, {})
    item[last] = value


def to_rows(items, category):
    """Rows (one per item of the category, sorted by id) of COLUMNS[category]
    values as text."""
    rows = []
    for item in of_category(items, category):
        row = []
        for _, path, kind in COLUMNS[category]:
            value = _get(item, path)
            if path == "grain_axis":
                row.append(value or "none")  # sheets without grain (MDF) turn freely
            elif value is None:
                row.append("")
            elif kind == "numbers":
                row.append(" ".join(f"{v:g}" for v in value))
            elif kind == "number":
                row.append(f"{value:g}")
            else:
                row.append(str(value))
        rows.append(row)
    return rows


def from_rows(rows, category, base=None):
    """Items from rows of COLUMNS[category] text; base: id -> existing item
    whose other keys are kept. Raises ValueError naming the row and column."""
    out = []
    for n, row in enumerate(rows, start=1):
        item = json.loads(json.dumps((base or {}).get(row[0], {})))  # a copy
        item["category"] = category
        for (column, path, kind), text in zip(COLUMNS[category], row):
            text = str(text).strip()
            if path == "grain_axis":
                item[path] = None if text.lower() in ("", "none") else text
                continue
            if not text:
                if column in REQUIRED:
                    raise ValueError(f"row {n}: {column} is missing")
                continue
            try:
                if kind == "number":
                    value = float(text)
                elif kind == "numbers":
                    value = [float(v) for v in text.replace(",", " ").split()]
                else:
                    value = text
            except ValueError:
                raise ValueError(f"row {n}: {column} '{text}' is not a number")
            _set(item, path, value)
        if category in (LUMBER, SHEET_GOODS):
            item.setdefault("actual", {}).setdefault("unit", "mm")
        out.append(item)
    return out


def changed(items, shipped):
    """The items that differ from the shipped ones (or are new): what a user
    library file needs to hold."""
    return [i for i in items if shipped.get(i["id"]) != i]


def write_user_file(path, user_items):
    """A user library file with the items, marked as entered by the user."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "_comment": "Entered in the Construction workbench's Library panel.",
        "source": "Entered by the user",
        "data_license": "user",
        "items": user_items,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def write_csv(path, items, category):
    import csv

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([c for c, _, _ in COLUMNS[category]])
        writer.writerows(to_rows(items, category))


def read_csv(path, category):
    """Rows of a CSV file written by write_csv (the header row skipped,
    columns matched by name)."""
    import csv

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        index = {name.strip(): k for k, name in enumerate(header)}
        missing = [c for c in REQUIRED if c not in index]
        if missing:
            raise ValueError(f"the CSV needs the columns {', '.join(sorted(missing))}")
        return [
            [
                row[index[c]] if c in index and index[c] < len(row) else ""
                for c, _, _ in COLUMNS[category]
            ]
            for row in reader
            if any(cell.strip() for cell in row)
        ]

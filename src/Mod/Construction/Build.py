# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: woodworking build: one object, a parts table and a joints table
# (design doc Phase 5.1). No FreeCAD imports.
"""A build is a parts table and a joints table.

Parts table rows: (name, stock, length, width, thickness, x, y, z, along,
thick). `stock` is a library id: lumber gives the width and thickness, sheet
goods the thickness; a non-empty width or thickness overrides it. `along` is
the axis ("x", "y" or "z") the length (and grain) runs along, `thick` the axis
of the thickness; the width takes the third. x, y, z is the part's minimum
corner.

Joints table rows: (receiver, inserted, joint, options). Receiver and inserted
are part names or fnmatch patterns ("Leg*"); `joint` is a library joint
preset; options override its fields, e.g. "depth=30, shoulder=5".
"""

import re

import Joinery
import Library
from Parts import Part

AXES = "xyz"
PARTS_HEADER = (
    "Name",
    "Stock",
    "Length",
    "Width",
    "Thickness",
    "X",
    "Y",
    "Z",
    "Along",
    "Thick",
)
JOINTS_HEADER = ("Receiver", "Inserted", "Joint", "Options")
MIN_SHELF_OPENING = 50.0  # mm clear between bookcase shelves


def _number(value):
    return None if value in ("", None) else float(value)


def part(row, items):
    """Part from a parts table row. Raises ValueError with the row's name."""
    name, stock, length, width, thick, x, y, z, along, thick_axis = row
    item = items.get(stock)
    if item is None:
        raise ValueError(f"{name}: stock '{stock}' not found in the construction library")
    if along not in AXES or thick_axis not in AXES or along == thick_axis:
        raise ValueError(f"{name}: Along and Thick must be two different axes of x, y, z")
    if item.get("category") == Library.LUMBER:
        role = "board"
        width = _number(width) or Library.mm(item, "h")
        thick = _number(thick) or Library.mm(item, "w")
    else:
        role = "panel"
        width = _number(width)
        thick = _number(thick) or Library.mm(item, "t")
    length = _number(length)
    if not length or not width or length <= 0 or width <= 0:
        raise ValueError(f"{name}: length and width must be positive")
    size = {along: length, thick_axis: thick}
    size[next(a for a in AXES if a not in size)] = width
    pos = tuple(float(v or 0) for v in (x, y, z))
    return Part(name, role, tuple(size[a] for a in AXES), pos, along)


def options(text):
    """'depth=30, shoulder=5' -> {'depth': 30.0, 'shoulder': 5.0}."""
    out = {}
    for entry in filter(None, (e.strip() for e in (text or "").split(","))):
        key, _, value = entry.partition("=")
        try:
            out[key.strip()] = float(value)
        except ValueError:
            out[key.strip()] = value.strip()
    return out


def rules(joint_rows, items):
    out = []
    for receiver, inserted, joint, opts in joint_rows:
        item = items.get(joint)
        if item is None or item.get("category") != "joint":
            raise ValueError(f"joint '{joint}' ({receiver} / {inserted}) not in the library")
        out.append(Joinery.rule(item, receiver, inserted, **options(opts)))
    return out


def build(part_rows, joint_rows, items):
    """([(stock id, Part)] after joinery, in table order; Joinery.Result)."""
    stocks = [row[1] for row in part_rows]
    result = Joinery.apply([part(row, items) for row in part_rows], rules(joint_rows, items))
    return list(zip(stocks, result.boxes)), result


def similar(name):
    """Pattern for every part named like this one: 'Leg 3' -> 'Leg*'."""
    stem = re.sub(r"\s*\d+$", "", name)
    return stem + "*" if stem != name else name


def new_name(names, stem):
    """'Board 3' when 'Board 1' and 'Board 2' exist."""
    n = 1
    while f"{stem} {n}" in names:
        n += 1
    return f"{stem} {n}"


def between(a, b, section):
    """Parts-table geometry for a board spanning the gap between parts a and b:
    (length, x, y, z, along, thick). section: (thickness, width). The board's
    thickness lies across the narrower of the two shared spans, centred; its
    width is flush with the top (or the far side) of the shared span."""
    gaps = [max(b.lo(k) - a.hi(k), a.lo(k) - b.hi(k)) for k in range(3)]
    k = max(range(3), key=lambda n: gaps[n])
    if gaps[k] <= Joinery.EPS:
        raise ValueError(f"{a.name} and {b.name} touch or overlap: no gap to span")
    shared = {n: (max(a.lo(n), b.lo(n)), min(a.hi(n), b.hi(n))) for n in range(3) if n != k}
    t_axis, w_axis = sorted(shared, key=lambda n: shared[n][1] - shared[n][0])
    thick, width = section
    pos = [0.0] * 3
    pos[k] = min(a.hi(k), b.hi(k))
    pos[t_axis] = sum(shared[t_axis]) / 2 - thick / 2
    pos[w_axis] = shared[w_axis][1] - width
    return gaps[k], *pos, AXES[k], AXES[t_axis]


def on_face(part, axis, sign, thick, width=None):
    """Parts-table geometry for a board or panel lying against a face of
    `part` (the face normal is +/- `axis`, 0..2): (length, width, x, y, z,
    along, thick). It runs along the part's longer face direction for the
    part's full length; a panel (width None) covers the face."""
    k = axis
    along, across = sorted((n for n in range(3) if n != k), key=lambda n: -part.size[n])
    pos = list(part.pos)
    pos[k] = part.hi(k) if sign > 0 else part.lo(k) - thick
    width = part.size[across] if width is None else width
    return part.size[along], width, *pos, AXES[along], AXES[k]


def table(
    width=500,
    depth=500,
    height=600,
    overhang=25,
    setback=5,
    leg=("lumber.metric.hw.45x45", 45),
    apron=("lumber.metric.hw.20x95", 20, 95),
    top=("sheet.metric.edge_glued.18", 18),
    top_boards=None,
    joint="joint.mortise_tenon",
    top_joint="joint.figure8",
    shelf=None,
    shelf_height=150,
):
    """(parts rows, joints rows) of a table: four legs, four aprons between
    them (set back from the legs' outer faces, flush with their tops), and a
    top overhanging the leg frame. leg: (stock, size), apron: (stock,
    thickness, width), top: (stock, thickness) of a panel, or top_boards:
    (stock, thickness, width) to glue the top up from boards running along
    the width (all ripped to the same width). shelf: (stock, thickness) adds four
    stretchers like the aprons with their tops at shelf_height and a shelf
    resting on the front and back ones. Sizes in mm."""
    leg_stock, s = leg
    apron_stock, t, w = apron
    top_t = top_boards[1] if top_boards else top[1]
    leg_h = height - top_t
    x0, x1 = overhang, width - overhang - s
    y0, y1 = overhang, depth - overhang - s
    if x1 - x0 <= s or y1 - y0 <= s:
        raise ValueError("the top is too small for the legs and overhang")
    if setback + t > s:
        raise ValueError("the aprons are thicker than the legs allow with this setback")
    if shelf and not w < shelf_height < leg_h - w:
        raise ValueError("the shelf stretchers must fit between the floor and the aprons")
    parts = [
        (f"Leg {n}", leg_stock, leg_h, s, s, x, y, 0, "z", "x")
        for n, (x, y) in enumerate(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), start=1)
    ]

    def rails(name, z):
        return [
            (f"{name} 1", apron_stock, x1 - x0 - s, w, t, x0 + s, y0 + setback, z, "x", "y"),
            (
                f"{name} 2",
                apron_stock,
                y1 - y0 - s,
                w,
                t,
                x1 + s - setback - t,
                y0 + s,
                z,
                "y",
                "x",
            ),
            (
                f"{name} 3",
                apron_stock,
                x1 - x0 - s,
                w,
                t,
                x0 + s,
                y1 + s - setback - t,
                z,
                "x",
                "y",
            ),
            (f"{name} 4", apron_stock, y1 - y0 - s, w, t, x0 + setback, y0 + s, z, "y", "x"),
        ]

    parts += rails("Apron", leg_h - w)
    joints = [("Leg*", "Apron*", joint, "")]
    if top_boards:
        board_stock, _, board_w = top_boards
        n = int(-(-depth // board_w))  # boards needed, all ripped to the same width
        rip = depth / n
        for b in range(n):
            row = (f"Top board {b + 1}", board_stock, width, rip, top_t, 0, b * rip, leg_h)
            parts.append(row + ("x", "z"))
        joints += [
            ("Top board*", "Top board*", "joint.glue", ""),
            ("Apron*", "Top board*", top_joint, ""),
        ]
    else:
        parts.append(("Top", top[0], width, depth, top_t, 0, 0, leg_h, "x", "z"))
        joints.append(("Apron*", "Top", top_joint, ""))
    if shelf:
        shelf_stock, shelf_t = shelf
        parts += rails("Stretcher", shelf_height - w)
        y_lo, y_hi = y0 + setback, y1 + s - setback
        parts.append(
            (
                "Shelf",
                shelf_stock,
                x1 - x0 - s,
                y_hi - y_lo,
                shelf_t,
                x0 + s,
                y_lo,
                shelf_height,
                "x",
                "z",
            )
        )
        joints += [
            ("Leg*", "Stretcher*", joint, ""),
            ("Shelf", "Stretcher*", "joint.pocket_screw", ""),
        ]
    return parts, joints


def end_table(**sizes):
    """An end table: table() as it comes (500 x 500 x 600 mm)."""
    return table(**sizes)


_DINING = dict(
    width=1600,
    depth=900,
    height=750,
    overhang=50,
    leg=("lumber.metric.hw.70x70", 70),
    apron=("lumber.metric.hw.20x120", 20, 120),
    top_boards=("lumber.metric.hw.20x145", 20, 145),
)


def dining_table(**sizes):
    """A 1600 x 900 x 750 mm dining table: 70 mm legs, 20 x 120 aprons and a
    top glued up from 20 x 145 boards (table() arguments override)."""
    return table(**{**_DINING, **sizes})


_WORKBENCH = dict(
    width=1500,
    depth=600,
    height=900,
    overhang=30,
    setback=10,
    leg=("lumber.metric.70x70", 70),
    apron=("lumber.metric.45x95", 45, 95),
    top_boards=("lumber.metric.45x145", 45, 145),
    shelf=("sheet.metric.plywood.18", 18),
    shelf_height=250,
    joint="joint.mortise_tenon",
)


def workbench(**sizes):
    """A 1500 x 600 x 900 mm workbench in softwood: 70 mm legs, 45 x 95 aprons
    and stretchers, a top of 45 x 145 boards and a plywood shelf at 150 mm
    (table() arguments override)."""
    return table(**{**_WORKBENCH, **sizes})


def bookcase(
    width=800,
    height=1800,
    depth=300,
    shelves=4,
    kick=60,
    panel=("sheet.metric.plywood.18", 18),
    back=("sheet.metric.plywood.6", 6),
    joint="joint.dado",
):
    """(parts rows, joints rows) of a bookcase: two sides, top, bottom raised
    on a kick board, `shelves` fixed shelves evenly spaced between bottom and
    top, and a back nailed on behind. panel / back: (stock, thickness). The
    shelves, top and bottom go into the sides with `joint`."""
    stock, t = panel
    back_stock, _ = back
    inner = width - 2 * t
    if inner <= 0 or depth <= t:
        raise ValueError("the bookcase is too narrow or shallow for the panels")
    bottom_z, top_z = kick, height - t
    spacing = (top_z - bottom_z - t) / (shelves + 1)
    if spacing - t < MIN_SHELF_OPENING:
        raise ValueError("too many shelves for the height")
    parts = [
        ("Left side", stock, height, depth, "", 0, 0, 0, "z", "x"),
        ("Right side", stock, height, depth, "", width - t, 0, 0, "z", "x"),
        ("Top", stock, inner, depth, "", t, 0, top_z, "x", "z"),
        ("Bottom", stock, inner, depth, "", t, 0, bottom_z, "x", "z"),
        ("Kick board", stock, inner, kick, "", t, 0, 0, "x", "y"),
    ]
    parts += [
        (f"Shelf {n}", stock, inner, depth, "", t, 0, bottom_z + t + n * spacing - t / 2, "x", "z")
        for n in range(1, shelves + 1)
    ]
    parts.append(("Back", back_stock, height, width, "", 0, depth, 0, "z", "y"))  # grain up
    joints = [("*side", name, joint, "") for name in ("Top", "Bottom", "Shelf*")]
    joints.append(("*side", "Kick board", "joint.pocket_screw", ""))
    joints += [(name, "Back", "joint.brad_nail", "") for name in ("*side", "Top", "Bottom")]
    return parts, joints


# ---------------------------------------------------------------- parametric templates

# Template parameters: (property name, kind, template argument). Kinds:
# length / count / bool: a number or flag; "leg": a lumber id -> (id, thickness);
# "board": a lumber id -> (id, thickness, width); "sheet": a sheet id ->
# (id, thickness); "optional_board" / "optional_sheet": the same or "none" -> None;
# "joint" / "top_joint": a joint preset id (end to face / face to face).
TEMPLATES = {
    "table": (
        table,
        [
            ("Width", "length", "width"),
            ("Depth", "length", "depth"),
            ("Height", "length", "height"),
            ("Overhang", "length", "overhang"),
            ("Setback", "length", "setback"),
            ("LegStock", "leg", "leg"),
            ("ApronStock", "board", "apron"),
            ("TopStock", "sheet", "top"),
            ("TopBoards", "optional_board", "top_boards"),
            ("Joint", "joint", "joint"),
            ("TopJoint", "top_joint", "top_joint"),
            ("Shelf", "optional_sheet", "shelf"),
            ("ShelfHeight", "length", "shelf_height"),
        ],
    ),
    "bookcase": (
        bookcase,
        [
            ("Width", "length", "width"),
            ("Height", "length", "height"),
            ("Depth", "length", "depth"),
            ("Shelves", "count", "shelves"),
            ("Kick", "length", "kick"),
            ("PanelStock", "sheet", "panel"),
            ("BackStock", "sheet", "back"),
            ("Joint", "joint", "joint"),
        ],
    ),
}
# Presets: template name and the arguments that differ from its defaults.
PRESETS = {
    "end_table": ("table", {}),
    "dining_table": ("table", {}),
    "workbench": ("table", {}),
    "bookcase": ("bookcase", {}),
}


def preset_arguments(preset):
    """(template name, {argument: value}) of a preset: the template's
    defaults with the preset's changes."""
    import inspect

    name = PRESETS[preset][0]
    function = TEMPLATES[name][0]
    values = {
        k: p.default
        for k, p in inspect.signature(function).parameters.items()
        if p.default is not inspect.Parameter.empty
    }
    changes = {"dining_table": _DINING, "workbench": _WORKBENCH}.get(preset, {})
    return name, {**values, **changes}


def property_values(template, arguments):
    """{property: value} for a template's arguments (ids and numbers)."""
    out = {}
    for prop, kind, arg in TEMPLATES[template][1]:
        value = arguments[arg]
        if kind.startswith("optional_"):
            value = value[0] if value else "none"
        elif kind in ("leg", "board", "sheet"):
            value = value[0]
        out[prop] = value
    return out


def template_arguments(template, values, lumber, sheet):
    """Template arguments from property values. lumber(id) -> (thickness,
    width); sheet(id) -> thickness."""
    out = {}
    for prop, kind, arg in TEMPLATES[template][1]:
        value = values[prop]
        if kind.startswith("optional_"):
            if value == "none":
                out[arg] = None
                continue
            kind = kind[len("optional_") :]
        if kind == "leg":
            value = (value, lumber(value)[0])
        elif kind == "board":
            value = (value, *lumber(value))
        elif kind == "sheet":
            value = (value, sheet(value))
        elif kind == "count":
            value = int(value)
        elif kind == "length":
            value = float(value)
        out[arg] = value
    return out


def _norm(row):
    """A table row as comparable text (numbers rounded like the table)."""
    out = []
    for v in row:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(f"{round(float(v), 6):g}")
        else:
            out.append("" if v is None else str(v))
    return tuple(out)


def merge(old, new, current, key):
    """Rows after regenerating a template: `old` and `new` are the template's
    rows before and after the change, `current` the table as the user left
    it. A row the user did not touch follows the template (or goes, when the
    template no longer makes it); a row the user edited or added stays, an
    edited one marked as an override. key(row) identifies a row. Returns
    [(row, overridden)]."""
    old_by = {key(r): _norm(r) for r in old}
    new_by = {key(r): r for r in new}
    out, seen = [], set()
    for row in current:
        k = key(row)
        seen.add(k)
        if k in old_by and _norm(row) == old_by[k]:
            if k in new_by:
                out.append((new_by[k], False))
        else:
            out.append((row, k in new_by or k in old_by))
    out += [(r, False) for r in new if key(r) not in seen]
    return out

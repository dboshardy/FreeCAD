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


def end_table(
    width=500,
    depth=500,
    height=600,
    overhang=25,
    setback=5,
    leg=("lumber.metric.hw.45x45", 45),
    apron=("lumber.metric.hw.20x95", 20, 95),
    top=("sheet.metric.edge_glued.18", 18),
    joint="joint.mortise_tenon",
    top_joint="joint.figure8",
):
    """(parts rows, joints rows) of an end table: four legs, four aprons
    between them (set back from the legs' outer faces, flush with their tops),
    and a top overhanging the leg frame. leg: (stock, size), apron: (stock,
    thickness, width), top: (stock, thickness). Sizes in mm."""
    leg_stock, s = leg
    apron_stock, t, w = apron
    top_stock, top_t = top
    leg_h = height - top_t
    x0, x1 = overhang, width - overhang - s
    y0, y1 = overhang, depth - overhang - s
    if x1 - x0 <= s or y1 - y0 <= s:
        raise ValueError("the top is too small for the legs and overhang")
    if setback + t > s:
        raise ValueError("the aprons are thicker than the legs allow with this setback")
    z = leg_h - w
    parts = [
        (f"Leg {n}", leg_stock, leg_h, s, s, x, y, 0, "z", "x")
        for n, (x, y) in enumerate(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), start=1)
    ]
    parts += [
        ("Apron 1", apron_stock, x1 - x0 - s, w, t, x0 + s, y0 + setback, z, "x", "y"),
        ("Apron 2", apron_stock, y1 - y0 - s, w, t, x1 + s - setback - t, y0 + s, z, "y", "x"),
        ("Apron 3", apron_stock, x1 - x0 - s, w, t, x0 + s, y1 + s - setback - t, z, "x", "y"),
        ("Apron 4", apron_stock, y1 - y0 - s, w, t, x0 + setback, y0 + s, z, "y", "x"),
        ("Top", top_stock, width, depth, top_t, 0, 0, leg_h, "x", "z"),
    ]
    joints = [("Leg*", "Apron*", joint, ""), ("Apron*", "Top", top_joint, "")]
    return parts, joints

# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: cabinet interior as an editable list of items (design doc §5.4). No FreeCAD imports.
"""A cabinet interior: an ordered list of items, each fully adjustable.

One item per line (or per entry of a string list property):

    <type> <height>[, <key> <value>]...

type     tray | shelf | adjustable shelf
height   underside of the item above the floor
keys     walls     tray wall height              (default: the cabinet's tray height)
         slide     tray slide length             (default: the longest that fits)
         setback   shelf front edge, back from the front (default: the cabinet's setback)
         material  library id of the item's sheet goods (default: the cabinet's)

Examples:
    tray 4 in, walls 8 in
    tray 16 in, slide 12 in
    adjustable shelf 50 in, setback 2 in
    shelf 1500, material sheet.us.plywood.3-4

Lengths take a unit (mm, cm, m, in or ", ft or ') or are in mm; inches may be
written with fractions: 3 1/2 in, 1' 4-1/2".
"""

import re
from dataclasses import dataclass

TYPES = ("tray", "shelf", "adjustable shelf")
KEYS = ("walls", "slide", "setback", "material")
LENGTH_KEYS = ("walls", "slide", "setback")
TYPE_KEYS = {"tray": ("walls", "slide", "material"), "shelf": ("setback", "material"),
             "adjustable shelf": ("setback", "material")}
UNIT_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, '"': 25.4, "ft": 304.8, "'": 304.8}

_NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)"
_TERM = re.compile(
    rf"\s*(?P<onum>\d+)/(?P<oden>\d+)|\s*(?P<whole>{_NUMBER})(?:(?:\s+|-)(?P<num>\d+)/(?P<den>\d+))?"
)
_UNIT = re.compile(r"\s*(mm|cm|m|in|ft|\"|')(?![a-z])")


def parse_length(text):
    """mm from text: 1500, 150 cm, 4 in, 3 1/2", 1' 4-1/2", 1 ft 3 in, 3/4 in.
    A number without a unit is in mm. Raises ValueError."""
    s, pos, total, terms = text.strip().lower(), 0, 0.0, 0
    while pos < len(s):
        m = _TERM.match(s, pos)
        if not m or m.end() == pos:
            raise ValueError(f"not a length: {text!r}")
        if m.group("onum"):
            value = int(m.group("onum")) / int(m.group("oden"))
        else:
            value = float(m.group("whole"))
            if m.group("num"):
                value += int(m.group("num")) / int(m.group("den"))
        pos = m.end()
        u = _UNIT.match(s, pos)
        if u:
            value *= UNIT_MM[u.group(1)]
            pos = u.end()
        elif terms or pos < len(s.rstrip()):
            raise ValueError(f"length {text!r} needs a unit after each number")
        total += value
        terms += 1
        while pos < len(s) and s[pos] in " \t":
            pos += 1
    if not terms:
        raise ValueError(f"not a length: {text!r}")
    return total


@dataclass
class Item:
    kind: str  # one of TYPES
    height: float  # underside above the floor, mm
    walls: float | None = None  # tray wall height
    slide: float | None = None  # tray slide length
    setback: float | None = None  # shelf front edge back from the front
    material: str | None = None  # library id
    line: int = 0  # 1-based line in the list, for messages

    def label(self):
        return f"{self.kind} (line {self.line})"


def parse(lines):
    """Items from text lines (blank lines and lines starting with # are skipped).
    Raises ValueError naming the line."""
    items = []
    for number, raw in enumerate(lines, start=1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        fields = [f.strip() for f in text.split(",")]
        head = fields[0].lower()
        kind = next((t for t in sorted(TYPES, key=len, reverse=True) if head.startswith(t + " ")), None)
        if kind is None:
            raise ValueError(f"line {number}: starts with {head.split()[0]!r}; use one of: {', '.join(TYPES)}")
        try:
            item = Item(kind, parse_length(head[len(kind):]), line=number)
        except ValueError as e:
            raise ValueError(f"line {number}: height: {e}") from None
        for field in fields[1:]:
            key, _, value = field.partition(" ")
            key = key.lower()
            if key not in TYPE_KEYS[kind]:
                allowed = ", ".join(TYPE_KEYS[kind])
                raise ValueError(f"line {number}: {kind} has no {key!r}; use: {allowed}")
            if key in LENGTH_KEYS:
                try:
                    value = parse_length(value)
                except ValueError as e:
                    raise ValueError(f"line {number}: {key}: {e}") from None
            else:
                value = value.strip()
            setattr(item, key, value)
        items.append(item)
    return sorted(items, key=lambda i: i.height)


def format_item(item, length_text):
    """One line for item; length_text(mm) writes a length with its unit."""
    parts = [f"{item.kind} {length_text(item.height)}"]
    for key in KEYS:
        value = getattr(item, key)
        if value is not None:
            parts.append(f"{key} {value if key == 'material' else length_text(value)}")
    return ", ".join(parts)


def extent(item, defaults):
    """(bottom, top) of an item in mm. defaults: dict with 'walls' (tray wall
    height) and 'thickness' (shelf thickness by material id, a callable)."""
    if item.kind == "tray":
        return item.height, item.height + (item.walls if item.walls is not None else defaults["walls"])
    return item.height, item.height + defaults["thickness"](item.material)


def check_fit(items, floor, ceiling, defaults, length_text=lambda mm: f"{mm:.1f} mm"):
    """Raises ValueError when an item is outside [floor, ceiling] or reaches
    into the item above it. length_text(mm) writes lengths in the message."""
    spans = [(extent(i, defaults), i) for i in items]
    for (low, high), item in spans:
        if low < floor - 1e-6 or high > ceiling + 1e-6:
            raise ValueError(f"{item.label()} is outside the cabinet: it must sit between "
                             f"{length_text(floor)} and {length_text(ceiling)} above the floor")
    for ((_, top), a), ((bottom, _), b) in zip(spans, spans[1:]):
        if top > bottom + 1e-6:
            raise ValueError(f"{a.label()} reaches {length_text(top - bottom)} into {b.label()}")


def default_lines(tray_heights, length_text):
    """Starting interior: one tray per height."""
    return [f"tray {length_text(h)}" for h in tray_heights]

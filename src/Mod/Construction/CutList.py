# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: cut list and panel-saw sheet layout (design doc §5.6). No FreeCAD imports.

import math
from collections import Counter
from dataclasses import dataclass

EPS = 1e-6


def rows(parts_by_material):
    """Groups identical parts. parts_by_material: iterable of (material id, Part).
    Returns [(material, name, length, width, thickness, grain, qty)] sorted by
    material, then largest first. Sizes rounded to 0.1 mm."""
    counter = Counter()
    names = {}
    for material, part in parts_by_material:
        length, width, thick = (round(v, 1) for v in part.cut_size())
        key = (material, length, width, thick, part.grain is not None)
        counter[key] += 1
        names.setdefault(key, part.name)
    out = [
        (key[0], names[key], key[1], key[2], key[3], "yes" if key[4] else "no", qty)
        for key, qty in counter.items()
    ]
    out.sort(key=lambda r: (r[0], -r[2] * r[3], r[1]))
    return out


@dataclass
class Placement:
    name: str
    x: float  # from the sheet's left edge (across the sheet)
    y: float  # from the sheet's bottom edge (along the sheet length / grain)
    w: float  # size across the sheet
    h: float  # size along the sheet
    rotated: bool  # True when the part's length runs across the sheet


ORDERS = (
    lambda p: (p[1] * p[2], max(p[1], p[2])),  # area
    lambda p: (max(p[1], p[2]), p[1] * p[2]),  # longest side
    lambda p: (p[1], p[2]),  # length
    lambda p: (p[2], p[1]),  # width
)


def layout_sheets(pieces, sheet_w, sheet_h, kerf=3.2, trim=10.0, grain_locked=True):
    """Guillotine layout for a panel saw: every cut runs edge to edge of the
    piece it splits. pieces: [(name, length, width, has_grain)], one per part.
    The sheet is sheet_w across by sheet_h along its length; grain runs along
    the length. With grain_locked, parts with grain keep their length along it.
    trim: edge strip removed on every side. kerf: saw blade width.
    Returns one list of Placement per sheet: the fewest sheets over several
    part orders and split rules, then the fullest first sheets. Raises
    ValueError for a part that fits on no sheet.

    Free-rectangle guillotine packing, best-area fit, split along the shorter or
    longer leftover axis (J. Jylänki, "A Thousand Ways to Pack the Bin", 2010;
    guillotine cutting after Gilmore & Gomory, 1965). See docs/prior-art/.
    """
    # ponytail: 24 greedy passes, keep the best. Add a search (e.g. tree search
    # over strips) if layouts measurably waste sheets on real jobs.
    results = [
        _pack(
            sorted(pieces, key=order, reverse=True),
            sheet_w,
            sheet_h,
            kerf,
            trim,
            grain_locked,
            split_short,
            fit,
        )
        for order in ORDERS
        for split_short in (True, False)
        for fit in FITS
    ]

    def rank(sheets):
        used = [sum(p.w * p.h for p in placed) for placed in sheets]
        return (len(sheets), [-u for u in used])

    return min(results, key=rank)


# Free-rectangle scores, lower is better (Jylänki 2010): best area, best short
# side, best long side; leftover area breaks ties.
FITS = (
    lambda fw, fh, cw, ch: (fw * fh - cw * ch, min(fw - cw, fh - ch)),
    lambda fw, fh, cw, ch: (min(fw - cw, fh - ch), fw * fh - cw * ch),
    lambda fw, fh, cw, ch: (max(fw - cw, fh - ch), fw * fh - cw * ch),
)


def _pack(ordered, sheet_w, sheet_h, kerf, trim, grain_locked, split_short, fit):
    # Each part claims its size plus one kerf on its right and top; adding one
    # kerf to the usable area lets the last part in a row end at the trim line.
    usable = (sheet_w - 2 * trim + kerf, sheet_h - 2 * trim + kerf)
    if min(usable) <= kerf:
        raise ValueError("sheet too small for the edge trim")
    sheets = []  # [{"free": [(x, y, w, h)], "placed": [Placement]}]

    def orientations(length, width, grain):
        options = [(width, length, False)]  # length along the sheet
        if not (grain and grain_locked) and length != width:
            options.append((length, width, True))
        return [
            (w, h, r)
            for w, h, r in options
            if w + kerf <= usable[0] + EPS and h + kerf <= usable[1] + EPS
        ]

    def best_fit(options):
        best = None
        for si, sheet in enumerate(sheets):
            for fi, (_, _, fw, fh) in enumerate(sheet["free"]):
                for w, h, rotated in options:
                    cw, ch = w + kerf, h + kerf
                    if cw <= fw + EPS and ch <= fh + EPS:
                        score = fit(fw, fh, cw, ch)
                        if best is None or score < best[0]:
                            best = (score, si, fi, w, h, rotated)
        return best

    for name, length, width, grain in ordered:
        options = orientations(length, width, grain)
        if not options:
            raise ValueError(f"{name} ({length:g} x {width:g} mm) does not fit on the sheet")
        found = best_fit(options)
        if found is None:
            sheets.append({"free": [(0.0, 0.0, *usable)], "placed": []})
            found = best_fit(options)
        _, si, fi, w, h, rotated = found
        sheet = sheets[si]
        fx, fy, fw, fh = sheet["free"].pop(fi)
        cw, ch = w + kerf, h + kerf
        if (fw - cw < fh - ch) == split_short:
            # Cut across first: a short piece to the right, the full width above.
            right, top = (fx + cw, fy, fw - cw, ch), (fx, fy + ch, fw, fh - ch)
        else:
            # Cut along first: the full height to the right, a short piece above.
            right, top = (fx + cw, fy, fw - cw, fh), (fx, fy + ch, cw, fh - ch)
        sheet["free"] += [r for r in (right, top) if r[2] > kerf + EPS and r[3] > kerf + EPS]
        sheet["placed"].append(Placement(name, trim + fx, trim + fy, w, h, rotated))
    return [sheet["placed"] for sheet in sheets]


def pieces(cut_rows, material):
    """Expands cut-list rows of one material to one piece per part."""
    return [
        (name, length, width, grain == "yes")
        for m, name, length, width, _, grain, qty in cut_rows
        if m == material
        for _ in range(qty)
    ]


def hinges(door_height, item):
    """Hinges for one door from the item's [[max height mm, count], ...] table;
    taller doors get hinges_per_extra_400mm per started 400 mm above the table."""
    table = sorted(item["hinges_by_door_height"])
    for max_height, count in table:
        if door_height <= max_height:
            return count
    last_height, last_count = table[-1]
    extra = math.ceil((door_height - last_height) / 400) * item.get("hinges_per_extra_400mm", 1)
    return last_count + extra


def hardware(parts, items):
    """[(name, qty)] of hinges, drawer slides and shelf pins for a list of Part.
    items: library id -> item; uses hardware.hinge, hardware.drawer_slide,
    hardware.shelf_pin. Slides are listed per length."""
    hinge = items["hardware.hinge"]
    slide = items["hardware.drawer_slide"]
    pin = items["hardware.shelf_pin"]
    counter = Counter()
    for part in parts:
        if part.role == "door":
            counter[hinge["name"]] += hinges(part.size[2], hinge)
        elif part.role == "drawer_bottom":
            counter[f"{slide['name']}, {part.size[1]:g} mm"] += 1
        elif part.role == "shelf":
            counter[pin["name"]] += pin.get("per_shelf", 4)
    return sorted(counter.items())

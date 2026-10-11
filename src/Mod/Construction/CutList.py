# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: cut list and panel-saw sheet layout (design doc §5.6). No FreeCAD imports.

from collections import Counter
from dataclasses import dataclass

EPS = 1e-6


def _key(material, part):
    length, width, thick = (round(v, 1) for v in part.cut_size())
    return (material, length, width, thick, part.grain is not None, tuple(sorted(part.operations)))


def rows(parts_by_material):
    """Groups identical parts. parts_by_material: iterable of (material id, Part).
    Returns [(material, name, length, width, thickness, grain, qty)] sorted by
    material, then largest first. Sizes rounded to 0.1 mm."""
    counter = Counter()
    names = {}
    for material, part in parts_by_material:
        key = _key(material, part)
        counter[key] += 1
        names.setdefault(key, part.name)
    out = [
        (key[0], names[key], key[1], key[2], key[3], "yes" if key[4] else "no", qty)
        for key, qty in counter.items()
    ]
    # Same order as _row_keys: material, then largest first, then name.
    out.sort(key=lambda r: (r[0], -r[2] * r[3], r[1]))
    return out


def row_numbers(parts_by_material):
    """1-based row of rows() each part falls in, in input order: the part's tag."""
    parts = list(parts_by_material)
    order = {key: i for i, key in enumerate(_row_keys(parts), start=1)}
    return [order[_key(material, part)] for material, part in parts]


def operations(parts_by_material):
    """Shop work per part of each row of rows(), aligned with rows():
    "2 x mortise 75 x 6.7 x 25 deep; ..."."""
    out = []
    for key in _row_keys(list(parts_by_material)):
        counts = Counter(key[5])
        out.append("; ".join(f"{n} x {op}" if n > 1 else op for op, n in counts.items()))
    return out


def _row_keys(parts):
    """_key of each row of rows(parts), in row order."""
    keys = {}
    for material, part in parts:
        keys.setdefault(_key(material, part), part.name)
    return sorted(keys, key=lambda k: (k[0], -k[1] * k[2], keys[k]))


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
    Returns one list of Placement per sheet: pieces the size of the sheet each
    take a whole sheet; the rest the fewest sheets over several part orders and
    split rules, then the fullest first sheets. Raises
    ValueError for a part that fits on no sheet.

    Free-rectangle guillotine packing, best-area fit, split along the shorter or
    longer leftover axis (J. Jylänki, "A Thousand Ways to Pack the Bin", 2010;
    guillotine cutting after Gilmore & Gomory, 1965). See docs/prior-art/.
    """
    # A piece the size of the sheet is a whole sheet: no trim, no cut.
    whole_size = sorted((sheet_w, sheet_h))
    is_whole = [all(abs(a - b) <= 1.0 for a, b in zip(sorted(p[1:3]), whole_size)) for p in pieces]
    whole = [
        [Placement(p[0], 0.0, 0.0, sheet_w, sheet_h, False)] for p, w in zip(pieces, is_whole) if w
    ]
    pieces = [p for p, w in zip(pieces, is_whole) if not w]
    if not pieces:
        return whole
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

    return whole + min(results, key=rank)


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


def hardware(items, anchored_cabinets=0, fasteners=None):
    """[(name, qty)] of joinery fasteners (hardware id -> count; "id@length"
    for hardware sized by length, e.g. drawer slides) and wall anchors.
    anchored_cabinets: cabinets that must be fixed to the wall."""
    counter = Counter()
    if anchored_cabinets:
        anchor = items["hardware.wall_anchor"]
        counter[anchor["name"]] += anchored_cabinets * anchor.get("per_cabinet", 2)
    for key, count in (fasteners or {}).items():
        hardware_id, _, length = key.partition("@")
        name = items.get(hardware_id, {}).get("name", hardware_id)
        counter[f"{name}, {length} mm" if length else name] += count
    return sorted(counter.items())


@dataclass
class Board:
    stock: float  # stock length bought
    cuts: list  # [(name, length)]
    kerf: float

    def used(self):
        """Length the cuts take, with one kerf between neighbouring pieces."""
        return sum(length for _, length in self.cuts) + self.kerf * (len(self.cuts) - 1)

    def offcut(self):
        """Usable length left after the last cut (0 when none is left)."""
        return max(0.0, self.stock - self.used() - self.kerf)


# ponytail: first-fit decreasing, then each board shrunk to the shortest stock
# length that holds its cuts. Exact optimisation (OR-Tools CP-SAT, §3.2) when
# real jobs show measurable waste.
def plan_lengths(pieces, stock_lengths, kerf=3.2):
    """Cuts linear pieces from stock lengths. pieces: [(name, length)].
    Returns [Board], longest stock first. Raises ValueError for a piece longer
    than the longest stock length."""
    stock = sorted(s for s in stock_lengths if s > 0)
    if not stock:
        raise ValueError("no stock lengths given")
    boards = []
    for name, length in sorted(pieces, key=lambda p: p[1], reverse=True):
        if length > stock[-1] + EPS:
            raise ValueError(f"{name} ({length:g} mm) is longer than the longest stock length")
        for board in boards:
            if board.used() + board.kerf + length <= board.stock + EPS:
                board.cuts.append((name, length))
                break
        else:
            boards.append(Board(stock[-1], [(name, length)], kerf))
    for board in boards:
        board.stock = next(s for s in stock if board.used() <= s + EPS)
    return sorted(boards, key=lambda b: -b.stock)

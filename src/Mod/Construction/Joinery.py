# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: joinery for every construction object (design doc §5.3). No FreeCAD imports.
"""Joints between parts that touch.

Parts (Parts.Part) are axis-aligned boxes in one coordinate frame. Two
boxes meet when a face of one lies on a face of the other and the faces
overlap. A rule names which parts meet (fnmatch patterns on part names: the
receiving part, then the inserted part) and how they are joined:

- "housing": the inserted part is lengthened by `depth` into the receiving
  part, which gets a pocket of the inserted part's section. A dado, groove or
  housed end; at the receiver's edge the pocket is a rabbet.
- "tenon": mortise and tenon. The inserted part is lengthened by `depth`; its
  end is cut to a tenon `thickness` thick (0 = a third of the part) centred
  on the part, with `shoulder` cut off each edge of its width. The receiving
  part gets the matching mortise.
- "loose_tenon": the same mortise in both parts, `depth` deep each, for a
  separate (loose) tenon; set `fastener` to count the tenons.
- "half_lap": crossing parts each lose half their depth where they overlap.
- "bridle": crossing (or corner-overlapping) parts: the receiver gets a slot
  of the middle third, the inserted part keeps it as a tenon.
- "fastened": no change to the parts; fasteners only.

Any rule may add fasteners: `fastener` is a hardware id, `spacing` the
largest distance between fasteners along the contact, `edge` the distance of
the first and last from the contact's ends, `per_joint` a fixed count
instead (e.g. 2 nails per stud end, 1 joist hanger). `operation` is the
shop work the fasteners need, written to the cut list of the parts named by
`on` ("receiver", "inserted" or "both"); "{n}" in it becomes the count and
"{s}" / "{es}" a plural ending, e.g. "{n} pocket hole{s}". `count_table`
counts by contact length instead (hinges by door height); `sized` lists the
fastener per contact length (drawer slides by depth); `gap` lets fastened
parts meet across a clearance (a drawer box beside the carcass side).

Joint presets in the library (category "joint") are rules without the part
names: `rule(item, receiver, inserted)` makes one.
"""

import fnmatch
import math
from dataclasses import dataclass, field, fields, replace

from Parts import Part

EPS = 1e-6


@dataclass
class Rule:
    receiver: str  # fnmatch pattern of the receiving part's name
    inserted: str  # fnmatch pattern of the other part's name
    kind: str = "fastened"  # housing, tenon, loose_tenon, half_lap, bridle, fastened
    depth: float = 0.0  # housing depth or tenon length into the receiver
    thickness: float = 0.0  # tenon thickness; 0 = a third of the inserted part
    shoulder: float = 0.0  # tenon: cut off each edge of the inserted part's width
    fastener: str = ""  # hardware id
    spacing: float = 0.0  # mm between fasteners along the contact; 0 = use per_joint
    edge: float = 0.0  # mm from the contact's ends to the first and last fastener
    per_joint: int = 0  # fixed fastener count per joint
    operation: str = ""  # shop work per joint, "{n}" = fastener count
    on: str = "both"  # parts the operation applies to: "receiver", "inserted", "both"
    gap: float = 0.0  # fastened: parts this far apart still meet (slides, shelf pins)
    count_table: list = field(default_factory=list)  # [[max length, count], ...]
    extra_every: float = 400.0  # count_table: one more per started length beyond it
    sized: bool = False  # fasteners listed per contact length (hardware id@length)
    hole: list = field(
        default_factory=list
    )  # [diameter, into receiver (-1 through), into inserted]
    allows_movement: bool = False  # lets solid wood move across its grain (tabletop fasteners)


def rule(item, receiver, inserted, **overrides):
    """Rule from a library joint preset (extra keys such as id and name ignored)."""
    names = {f.name for f in fields(Rule)}
    values = {k: v for k, v in {**item, **overrides}.items() if k in names}
    return Rule(**{**values, "receiver": receiver, "inserted": inserted})


@dataclass
class Result:
    boxes: list  # parts after joinery (inserted parts lengthened)
    pockets: list = field(default_factory=list)  # [(part index, Part)] material removed
    operations: list = field(default_factory=list)  # [(part index, text)] for the cut list
    fasteners: dict = field(default_factory=dict)  # hardware id -> count
    joints: list = field(default_factory=list)  # [(receiver index, inserted index, Rule)]


def contact(a, b, gap=0.0):
    """(axis, sign, overlap box of the two faces) when a face of b lies on a
    face of a, or faces it across at most `gap`, else None. sign is +1 when b
    sits on a's high side."""
    for k in range(3):
        for sign, touching in (
            (1, -EPS < b.lo(k) - a.hi(k) < gap + EPS),
            (-1, -EPS < a.lo(k) - b.hi(k) < gap + EPS),
        ):
            if not touching:
                continue
            lo, hi = [0.0] * 3, [0.0] * 3
            ok = True
            for j in range(3):
                if j == k:
                    lo[j] = hi[j] = a.hi(k) if sign == 1 else a.lo(k)
                    continue
                lo[j], hi[j] = max(a.lo(j), b.lo(j)), min(a.hi(j), b.hi(j))
                if hi[j] - lo[j] < EPS:
                    ok = False
            if ok:
                return k, sign, (tuple(lo), tuple(hi))
    return None


def overlap(a, b):
    """Overlap box (lo, hi) of two boxes that interpenetrate, else None."""
    lo = [max(a.lo(j), b.lo(j)) for j in range(3)]
    hi = [min(a.hi(j), b.hi(j)) for j in range(3)]
    return (lo, hi) if all(h - l > EPS for l, h in zip(lo, hi)) else None


def fastener_count(rule, length):
    if rule.count_table:
        table = sorted(rule.count_table)
        for max_length, count in table:
            if length <= max_length + EPS:
                return count
        last_length, last_count = table[-1]
        return last_count + math.ceil((length - last_length) / rule.extra_every)
    if rule.per_joint:
        return rule.per_joint
    if not rule.spacing:
        return 0
    usable = max(0.0, length - 2 * rule.edge)
    return max(2, math.ceil(usable / rule.spacing - EPS) + 1) if usable > EPS else 1


def apply(boxes, rules):
    """Applies the first matching rule to every pair of touching (or, for
    half laps, crossing) parts. Returns a Result."""
    # ponytail: every pair is tested (O(n^2)); fine for a few hundred parts per
    # object. Sort along an axis and sweep if objects get much bigger.
    out = Result(list(boxes))
    for i, a in enumerate(boxes):
        for j, b in enumerate(boxes):
            if i == j:
                continue
            rule = next(
                (
                    r
                    for r in rules
                    if fnmatch.fnmatchcase(a.name, r.receiver)
                    and fnmatch.fnmatchcase(b.name, r.inserted)
                ),
                None,
            )
            if rule is None:
                continue
            symmetric = fnmatch.fnmatchcase(b.name, rule.receiver) and fnmatch.fnmatchcase(
                a.name, rule.inserted
            )
            if (symmetric or rule.kind in CROSSING) and i > j:
                continue  # one joint per pair
            touch = None
            if rule.kind in CROSSING:
                crossing = overlap(a, b)
                if crossing is None:
                    continue
                _cross(out, i, j, crossing, rule.kind)
                length = max(h - l for l, h in zip(*crossing))
            else:
                touch = contact(a, b, rule.gap)
                if touch is None:
                    continue
                k, sign, (lo, hi) = touch
                if rule.kind == "housing":
                    _housing(out, i, j, k, sign, lo, hi, rule.depth)
                elif rule.kind in ("tenon", "loose_tenon"):
                    _tenon(out, i, j, k, sign, rule, loose=rule.kind == "loose_tenon")
                length = max(h - l for n, (l, h) in enumerate(zip(lo, hi)) if n != k)
            out.joints.append((i, j, rule))
            count = fastener_count(rule, length)
            if count and rule.hole and touch:
                _holes(out, i, j, touch, rule, count)
            if count and rule.fastener:
                key = f"{rule.fastener}@{length:g}" if rule.sized else rule.fastener
                out.fasteners[key] = out.fasteners.get(key, 0) + count
            if rule.operation:
                plural = count != 1
                text = rule.operation.format(n=count, s="s" * plural, es="es" * plural)
                for index, side in ((i, "receiver"), (j, "inserted")):
                    if rule.on in (side, "both"):
                        out.operations.append((index, text))
    for index, text in out.operations:
        part = out.boxes[index]
        out.boxes[index] = replace(part, operations=part.operations + (text,))
    return out


def meets(a, b):
    """How part b meets part a: "end_to_face" (b's end on a), "face_to_face",
    "edge_to_face", "crossing" (they interpenetrate) or None."""
    touch = contact(a, b)
    if touch is None:
        return "crossing" if overlap(a, b) else None
    k = touch[0]
    order = sorted(range(3), key=lambda n: b.size[n])  # thickness, width, length
    return ("face_to_face", "edge_to_face", "end_to_face")[order.index(k)]


def _housing(out, i, j, k, sign, lo, hi, depth):
    """Lengthen part j by depth into part i along axis k; pocket part i."""
    if depth <= 0:
        return
    if depth >= out.boxes[i].size[k] - EPS:
        raise ValueError(f"housing in {out.boxes[i].name} deeper than the part")
    b = out.boxes[j]
    size, pos = list(b.size), list(b.pos)
    size[k] += depth
    if sign == 1:
        pos[k] -= depth  # b grows back into a, which is below it
    out.boxes[j] = replace(b, size=tuple(size), pos=tuple(pos))
    plo, phi = list(lo), list(hi)
    if sign == 1:
        plo[k] = hi[k] - depth
    else:
        phi[k] = lo[k] + depth
    pocket = Part(
        f"{out.boxes[i].name} pocket", "pocket", tuple(h - l for l, h in zip(plo, phi)), tuple(plo)
    )
    out.pockets.append((i, pocket))
    width = sorted(s for n, s in enumerate(pocket.size) if n != k)
    out.operations.append((i, f"housing {round(width[0], 1):g} x {depth:g} deep"))


CROSSING = ("half_lap", "bridle")


def _cross(out, i, j, crossing, kind):
    """Joint where two parts cross (or overlap at a corner), cut along the
    axis neither part runs along (parallel parts: the axis of least overlap).
    half_lap: each loses half the overlap's depth from opposite faces.
    bridle: the receiver loses the middle third (an open mortise or slot), the
    inserted part the outer thirds (its tenon)."""
    lo, hi = crossing
    lengths = {max(range(3), key=lambda n: out.boxes[x].size[n]) for x in (i, j)}
    across = [n for n in range(3) if n not in lengths]
    k = across[0] if len(across) == 1 else min(range(3), key=lambda n: hi[n] - lo[n])
    if kind == "half_lap":
        mid = (lo[k] + hi[k]) / 2
        cuts = [(i, (lo[k], mid), "lap", "half lap"), (j, (mid, hi[k]), "lap", "half lap")]
    else:
        third = (hi[k] - lo[k]) / 3
        a, b = lo[k] + third, hi[k] - third
        cuts = [
            (i, (a, b), "slot", f"bridle slot {third:.3g} wide"),
            (j, (lo[k], a), "cheek", f"bridle tenon {third:.3g} thick"),
            (j, (b, hi[k]), "cheek", None),
        ]
    for index, (start, end), what, text in cuts:
        plo, phi = list(lo), list(hi)
        plo[k], phi[k] = start, end
        size = tuple(h - l for l, h in zip(plo, phi))
        name = f"{out.boxes[index].name} {what}"
        out.pockets.append((index, Part(name, "pocket", size, tuple(plo))))
        if text:
            out.operations.append((index, text))


def _holes(out, i, j, touch, rule, count):
    """Fastener holes across the contact: `count` evenly along its longer
    direction (`edge` from the ends, else evenly spread), centred across it.
    rule.hole = [diameter, depth into the receiver (-1: through), depth into
    the inserted part]. Holes are pockets with role "hole" whose grain is the
    hole's axis."""
    k, sign, (lo, hi) = touch
    d, into_a, into_b = rule.hole
    a, b = out.boxes[i], out.boxes[j]
    along = max((n for n in range(3) if n != k), key=lambda n: hi[n] - lo[n])
    across = next(n for n in range(3) if n not in (k, along))
    span = hi[along] - lo[along]
    edge = rule.edge if rule.edge and 2 * rule.edge < span else span / (2 * count)
    step = (span - 2 * edge) / (count - 1) if count > 1 else 0
    face_a = a.hi(k) if sign == 1 else a.lo(k)
    face_b = b.lo(k) if sign == 1 else b.hi(k)
    depth_a = a.size[k] if into_a < 0 else into_a
    spans_k = [
        (i, (face_a - depth_a, face_a) if sign == 1 else (face_a, face_a + depth_a)),
        (j, (face_b, face_b + into_b) if sign == 1 else (face_b - into_b, face_b)),
    ]
    for n in range(count):
        centre = {along: lo[along] + edge + n * step, across: (lo[across] + hi[across]) / 2}
        for index, (k_lo, k_hi) in spans_k:
            if k_hi - k_lo < EPS:
                continue
            pos, size = [0.0] * 3, [d] * 3
            for m, c in centre.items():
                pos[m] = c - d / 2
            pos[k], size[k] = k_lo, k_hi - k_lo
            name = f"{out.boxes[index].name} hole"
            out.pockets.append((index, Part(name, "hole", tuple(size), tuple(pos), "xyz"[k])))


def _tenon(out, i, j, k, sign, rule, loose=False):
    """Lengthen part j by rule.depth into part i along axis k, cut the
    lengthened end to a tenon, and mortise part i. loose: mortise both parts
    rule.depth deep for a separate tenon instead (the fastener counts it)."""
    a, b = out.boxes[i], out.boxes[j]
    depth = rule.depth
    if depth <= 0:
        raise ValueError(f"tenon on {b.name} needs a length")
    face = a.hi(k) if sign == 1 else a.lo(k)
    end = (face - depth, face) if sign == 1 else (face, face + depth)
    t_axis, w_axis = sorted((n for n in range(3) if n != k), key=lambda n: b.size[n])
    thick = rule.thickness or b.size[t_axis] / 3
    mid = b.lo(t_axis) + b.size[t_axis] / 2
    tenon = {k: end, t_axis: (mid - thick / 2, mid + thick / 2)}
    tenon[w_axis] = (b.lo(w_axis) + rule.shoulder, b.hi(w_axis) - rule.shoulder)
    if any(hi - lo < EPS for lo, hi in tenon.values()):
        raise ValueError(f"tenon on {b.name}: shoulders or thickness leave no tenon")
    if any(tenon[n][0] < a.lo(n) - EPS or tenon[n][1] > a.hi(n) + EPS for n in range(3)):
        raise ValueError(f"mortise for {b.name} breaks out of {a.name}")

    def box(name, role, spans):
        lo = tuple(spans[n][0] for n in range(3))
        return Part(name, role, tuple(spans[n][1] - spans[n][0] for n in range(3)), lo)

    w, t = round(tenon[w_axis][1] - tenon[w_axis][0], 1), round(
        tenon[t_axis][1] - tenon[t_axis][0], 1
    )
    mortise = f"mortise {w:g} x {t:g} x {depth:g} deep"
    if loose:
        if depth >= b.size[k] - EPS:
            raise ValueError(f"loose tenon mortise deeper than {b.name} is long")
        out.pockets.append((i, box(f"{a.name} mortise", "pocket", tenon)))
        other = dict(tenon)
        other[k] = (face, face + depth) if sign == 1 else (face - depth, face)
        out.pockets.append((j, box(f"{b.name} mortise", "pocket", other)))
        out.operations += [(i, mortise), (j, mortise)]
        return
    size, pos = list(b.size), list(b.pos)
    size[k] += depth
    if sign == 1:
        pos[k] -= depth
    out.boxes[j] = replace(b, size=tuple(size), pos=tuple(pos))
    out.pockets.append((i, box(f"{a.name} mortise", "pocket", tenon)))
    # The lengthened end minus the tenon: two cheeks across the full width,
    # then the shoulders beside the tenon.
    t_lo, t_hi = tenon[t_axis]
    w_lo, w_hi = tenon[w_axis]
    waste = [
        {k: end, t_axis: (b.lo(t_axis), t_lo), w_axis: (b.lo(w_axis), b.hi(w_axis))},
        {k: end, t_axis: (t_hi, b.hi(t_axis)), w_axis: (b.lo(w_axis), b.hi(w_axis))},
        {k: end, t_axis: (t_lo, t_hi), w_axis: (b.lo(w_axis), w_lo)},
        {k: end, t_axis: (t_lo, t_hi), w_axis: (w_hi, b.hi(w_axis))},
    ]
    for spans in waste:
        if all(hi - lo > EPS for lo, hi in spans.values()):
            out.pockets.append((j, box(f"{b.name} tenon cheek", "pocket", spans)))
    # Two tenons meeting inside one leg are reported by Checks.build.
    out.operations.append((i, mortise))
    out.operations.append((j, f"tenon {w:g} x {t:g} x {depth:g} long"))

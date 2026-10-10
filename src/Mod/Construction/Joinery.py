# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: joinery for every construction object (design doc §5.3). No FreeCAD imports.
"""Joints between parts that touch.

Parts are axis-aligned boxes in one coordinate frame: (name, size, pos). Two
boxes meet when a face of one lies on a face of the other and the faces
overlap. A rule names which parts meet (fnmatch patterns on part names: the
receiving part, then the inserted part) and how they are joined:

- "housing": the inserted part is lengthened by `depth` into the receiving
  part, which gets a pocket of the inserted part's section. A dado, groove or
  housed end; at the receiver's edge the pocket is a rabbet.
- "half_lap": crossing parts each lose half their depth where they overlap.
- "fastened": no change to the parts; fasteners only.

Any rule may add fasteners: `fastener` is a hardware id, `spacing` the
largest distance between fasteners along the contact, `edge` the distance of
the first and last from the contact's ends, `per_joint` a fixed count
instead (e.g. 2 nails per stud end, 1 joist hanger).
"""

import fnmatch
import math
from dataclasses import dataclass, field, replace

EPS = 1e-6


@dataclass
class Box:
    name: str
    size: tuple  # (dx, dy, dz)
    pos: tuple  # minimum corner

    def lo(self, k):
        return self.pos[k]

    def hi(self, k):
        return self.pos[k] + self.size[k]


@dataclass
class Rule:
    receiver: str  # fnmatch pattern of the receiving part's name
    inserted: str  # fnmatch pattern of the other part's name
    kind: str = "fastened"  # "housing", "half_lap", "fastened"
    depth: float = 0.0  # housing depth into the receiver
    fastener: str = ""  # hardware id
    spacing: float = 0.0  # mm between fasteners along the contact; 0 = use per_joint
    edge: float = 0.0  # mm from the contact's ends to the first and last fastener
    per_joint: int = 0  # fixed fastener count per joint


@dataclass
class Result:
    boxes: list  # parts after joinery (inserted parts lengthened)
    pockets: list = field(default_factory=list)  # [(part index, Box)] material removed
    operations: list = field(default_factory=list)  # [(part index, text)] for the cut list
    fasteners: dict = field(default_factory=dict)  # hardware id -> count


def contact(a, b):
    """(axis, sign, overlap box of the two faces) when a face of b lies on a
    face of a, else None. sign is +1 when b sits on a's high side."""
    for k in range(3):
        for sign, touching in (
            (1, abs(b.lo(k) - a.hi(k)) < EPS),
            (-1, abs(b.hi(k) - a.lo(k)) < EPS),
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
            if (symmetric or rule.kind == "half_lap") and i > j:
                continue  # one joint per pair
            if rule.kind == "half_lap":
                crossing = overlap(a, b)
                if crossing is None:
                    continue
                _half_lap(out, i, j, crossing)
                length = max(h - l for l, h in zip(*crossing))
            else:
                touch = contact(a, b)
                if touch is None:
                    continue
                k, sign, (lo, hi) = touch
                if rule.kind == "housing":
                    _housing(out, i, j, k, sign, lo, hi, rule.depth)
                length = max(h - l for n, (l, h) in enumerate(zip(lo, hi)) if n != k)
            count = fastener_count(rule, length)
            if count and rule.fastener:
                out.fasteners[rule.fastener] = out.fasteners.get(rule.fastener, 0) + count
    return out


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
    pocket = Box(f"{out.boxes[i].name} pocket", tuple(h - l for l, h in zip(plo, phi)), tuple(plo))
    out.pockets.append((i, pocket))
    width = sorted(s for n, s in enumerate(pocket.size) if n != k)
    out.operations.append((i, f"housing {width[0]:g} x {depth:g} deep for {b.name}"))


def _half_lap(out, i, j, crossing):
    """Each crossing part loses half the overlap's depth from opposite faces,
    along the axis neither part runs along (parallel parts: the axis of least
    overlap)."""
    lo, hi = crossing
    lengths = {max(range(3), key=lambda n: out.boxes[x].size[n]) for x in (i, j)}
    across = [n for n in range(3) if n not in lengths]
    k = across[0] if len(across) == 1 else min(range(3), key=lambda n: hi[n] - lo[n])
    mid = (lo[k] + hi[k]) / 2
    for index, (a, b) in ((i, (lo[k], mid)), (j, (mid, hi[k]))):
        plo, phi = list(lo), list(hi)
        plo[k], phi[k] = a, b
        size = tuple(h - l for l, h in zip(plo, phi))
        out.pockets.append((index, Box(f"{out.boxes[index].name} lap", size, tuple(plo))))
        out.operations.append((index, "half lap"))

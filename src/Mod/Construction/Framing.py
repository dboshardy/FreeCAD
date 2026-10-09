# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: wall framing generator (design doc §5.4). No FreeCAD imports.
"""Platform-framed stud wall, from conventional carpentry practice.

Wall coordinates: x along the wall from its start, y across it (0 = one face,
`depth` = the other), z up from the bottom of the bottom plate. Sizes in mm.
Every piece is a member (see Member.py): a section swept from start to end.
"""

import math
import re
from dataclasses import dataclass, field

import Member

OPENING_KINDS = ("door", "window")


@dataclass
class Opening:
    kind: str  # "door" or "window"
    x: float  # left edge of the rough opening, from the wall start
    width: float  # rough opening width
    height: float  # rough opening height
    sill: float = 0.0  # rough opening bottom above the bottom of the wall (windows)


@dataclass
class Piece:
    name: str
    start: tuple
    end: tuple
    roll: float  # see Member.frame
    section: str  # "stud" or "header": which lumber size

    def length(self):
        return Member.frame(self.start, self.end)[0]


@dataclass
class Wall:
    length: float = 3600.0
    height: float = 2440.0  # bottom of bottom plate to top of top plates
    spacing: float = 600.0  # stud centres
    top_plates: int = 2
    stud: tuple = (45.0, 95.0)  # (thickness, depth) of studs and plates
    header: tuple = (45.0, 195.0)  # (thickness, depth) of one header ply
    openings: list = field(default_factory=list)
    max_piece: float = 6000.0  # longest stock length: plates longer are spliced

    # ----------------------------------------------------------------- checks

    def validate(self):
        t, d = self.stud
        for name in ("length", "height", "spacing", "max_piece"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if min(self.stud) <= 0 or min(self.header) <= 0:
            raise ValueError("lumber sizes must be positive")
        if self.top_plates not in (1, 2):
            raise ValueError("top plates must be 1 or 2")
        if self.spacing < 2 * t:
            raise ValueError("stud spacing too small for the stud thickness")
        if self.length < 2 * t:
            raise ValueError("wall shorter than two studs")
        if self.stud_length() <= 0:
            raise ValueError("wall too low for its plates")
        previous_end = t  # right face of the start stud
        for o in sorted(self.openings, key=lambda o: o.x):
            label = f"{o.kind} at {o.x:g}"
            if o.kind not in OPENING_KINDS:
                raise ValueError(f"opening kind must be door or window, not '{o.kind}'")
            if o.width <= 0 or o.height <= 0 or o.sill < 0:
                raise ValueError(f"{label}: sizes must be positive")
            # King and jack studs (2 x t) on both sides must clear the neighbours.
            if o.x - 2 * t < previous_end - 1e-6:
                raise ValueError(f"{label}: too close to the wall start or the previous opening")
            previous_end = o.x + o.width + 2 * t
            if o.kind == "door" and o.sill:
                raise ValueError(f"{label}: doors start at the floor (no sill)")
            if o.kind == "window" and o.sill < 2 * t:
                raise ValueError(f"{label}: sill too low for the bottom plate and rough sill")
            if self.header_top(o) > self.height - self.top_plates * t + 1e-6:
                raise ValueError(f"{label}: opening and header taller than the wall")
        if previous_end > self.length - t + 1e-6:
            raise ValueError("last opening too close to the wall end")

    # ----------------------------------------------------------------- sizes

    def stud_length(self):
        return self.height - (1 + self.top_plates) * self.stud[0]

    def header_top(self, o):
        return o.sill + o.height + self.header[1]

    def header_plies(self):
        """Plies on edge side by side across the wall depth."""
        return max(1, math.floor(self.stud[1] / self.header[0] + 1e-9))

    def layout(self):
        """Stud centres on the layout, measured from the wall start."""
        t = self.stud[0]
        centres, i = [], 1
        while i * self.spacing + t / 2 <= self.length - t:
            centres.append(i * self.spacing)
            i += 1
        return centres

    # ----------------------------------------------------------------- pieces

    def pieces(self):
        self.validate()
        t, d = self.stud
        L, H, mid = self.length, self.height, self.stud[1] / 2
        bottom, top_of_studs = t, t + self.stud_length()
        out = []

        def horizontal(name, x0, x1, z, roll=90.0, y=mid, section="stud"):
            out.append(Piece(name, (x0, y, z), (x1, y, z), roll, section))

        def vertical(name, x, z0, z1):
            if z1 - z0 > 1e-6:
                out.append(Piece(name, (x, mid, z0), (x, mid, z1), 0.0, "stud"))

        # End studs, layout studs outside the openings' framing zones, king studs.
        zones = [(o.x - 2 * t, o.x + o.width + 2 * t) for o in self.openings]
        studs = [t / 2, L - t / 2] + [
            c
            for c in self.layout()
            if c + t / 2 <= L - t + 1e-6
            and not any(z0 < c + t / 2 and c - t / 2 < z1 for z0, z1 in zones)
        ]
        kings = [x for o in self.openings for x in (o.x - 1.5 * t, o.x + o.width + 1.5 * t)]
        jacks = [x for o in self.openings for x in (o.x - t / 2, o.x + o.width + t / 2)]
        for x in sorted(studs):
            vertical("Stud", x, bottom, top_of_studs)

        # Plates, spliced over stud centres when longer than the stock. The
        # bottom plate is cut out at doors; the upper top plate's joints stay at
        # least one stud bay from the lower one's.
        cuts = sorted((o.x, o.x + o.width) for o in self.openings if o.kind == "door")
        x = 0.0
        for x0, x1 in cuts + [(L, L)]:
            if x0 - x > 1e-6:
                for a, b in self._splice(x, x0, studs + kings + jacks):
                    horizontal("Bottom plate", a, b, t / 2)
            x = x1
        joints = []
        for k in reversed(range(self.top_plates)):  # the plate on the studs first
            segments = self._splice(0.0, L, studs + kings, avoid=joints, gap=self.spacing)
            for a, b in segments:
                horizontal("Top plate", a, b, H - t / 2 - k * t)
            joints = [b for _, b in segments[:-1]]

        for o in self.openings:
            x0, x1 = o.x, o.x + o.width
            rough_bottom, rough_top = o.sill, o.sill + o.height
            header_top = self.header_top(o)
            for jack_x, king_x in ((x0 - t / 2, x0 - 1.5 * t), (x1 + t / 2, x1 + 1.5 * t)):
                vertical("King stud", king_x, bottom, top_of_studs)
                vertical("Jack stud", jack_x, bottom, rough_top)
            # Header plies on edge (roll 0), bearing on the jacks.
            plies = self.header_plies()
            hz = rough_top + self.header[1] / 2
            for p in range(plies):
                y = (p + 0.5) * self.header[0] + (d - plies * self.header[0]) / 2
                horizontal("Header", x0 - t, x1 + t, hz, roll=0.0, y=y, section="header")
            # Cripples on the layout above the header (and below a window sill).
            inside = [c for c in self.layout() if x0 + t / 2 <= c <= x1 - t / 2]
            for c in inside:
                vertical("Cripple", c, header_top, top_of_studs)
            if o.kind == "window":
                horizontal("Sill", x0, x1, rough_bottom - t / 2)
                for c in inside:
                    vertical("Cripple", c, bottom, rough_bottom - t)
        return out

    def _splice(self, x0, x1, joints, avoid=(), gap=0.0):
        """[(a, b)] covering x0..x1, each at most max_piece long, breaking only at
        positions in joints (stud centres) at least gap away from all of avoid."""
        out, start = [], x0
        while x1 - start > self.max_piece + 1e-6:
            ok = [
                c
                for c in joints
                if start + 1e-6 < c <= start + self.max_piece + 1e-6
                and c < x1 - 1e-6
                and all(abs(c - a) >= gap - 1e-6 for a in avoid)
            ]
            if not ok:
                raise ValueError(
                    f"plate from {start:g} mm cannot be spliced over a stud within "
                    f"{self.max_piece:g} mm; use longer stock or closer studs"
                )
            out.append((start, max(ok)))
            start = max(ok)
        out.append((start, x1))
        return out


def parse_openings(text):
    """'door 900x2100 @ 600, window 1200x1000 @ 2400 sill 900' -> [Opening].
    Raises ValueError with a usage hint."""
    pattern = re.compile(
        r"^(door|window)\s+([\d.]+)\s*[x×]\s*([\d.]+)\s*@\s*([\d.]+)(?:\s+sill\s+([\d.]+))?$",
        re.IGNORECASE,
    )
    out = []
    for entry in text.replace(";", ",").split(","):
        entry = entry.strip()
        if not entry:
            continue
        m = pattern.match(entry)
        if not m:
            raise ValueError(
                f"'{entry}': write e.g. 'door 900x2100 @ 600' or "
                "'window 1200x1000 @ 2400 sill 900' (mm; @ = left edge from the wall start)"
            )
        kind, width, height, x, sill = m.groups()
        out.append(Opening(kind.lower(), float(x), float(width), float(height), float(sill or 0)))
    return out

# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: framing generators (design doc §5.4). No FreeCAD imports.
"""Platform framing from conventional carpentry practice: stud walls, floor
platforms and gable roofs. Sizes in mm.

Wall coordinates: x along the wall from its start, y across it (0 = one face,
`depth` = the other), z up from the bottom of the bottom plate. Floor: x along
the rim joists, y along the joists, z up from the bottom of the joists. Roof: x
along the ridge, y across the building from the outer face of one wall, z up
from the top of the wall plates.

Straight pieces are members (see Member.py): a section swept from start to end.
Rafters are profiles (plumb cuts, birdsmouth) extruded by their thickness.
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
        return layout_centres(self.length, self.spacing, self.stud[0])

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
                for a, b in splice(x, x0, studs + kings + jacks, self.max_piece):
                    horizontal("Bottom plate", a, b, t / 2)
            x = x1
        joints = []
        for k in reversed(range(self.top_plates)):  # the plate on the studs first
            segments = splice(0.0, L, studs + kings, self.max_piece, joints, self.spacing)
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


def layout_centres(length, spacing, t):
    """Centres on the layout from the start (spacing, 2 x spacing, ...) that
    clear an end member of thickness t at `length`."""
    centres, i = [], 1
    while i * spacing + t / 2 <= length - t:
        centres.append(i * spacing)
        i += 1
    return centres


def splice(x0, x1, joints, max_piece, avoid=(), gap=0.0):
    """[(a, b)] covering x0..x1, each at most max_piece long, breaking only at
    positions in joints (supporting member centres) at least gap away from all
    of avoid."""
    out, start = [], x0
    while x1 - start > max_piece + 1e-6:
        ok = [
            c
            for c in joints
            if start + 1e-6 < c <= start + max_piece + 1e-6
            and c < x1 - 1e-6
            and all(abs(c - a) >= gap - 1e-6 for a in avoid)
        ]
        if not ok:
            raise ValueError(
                f"piece from {start:g} mm cannot be spliced over a support within "
                f"{max_piece:g} mm; use longer stock or closer spacing"
            )
        out.append((start, max(ok)))
        start = max(ok)
    out.append((start, x1))
    return out


def end_and_layout(length, spacing, t):
    """Member centres: both ends plus the layout between them."""
    return [t / 2] + layout_centres(length, spacing, t) + [length - t / 2]


@dataclass
class Floor:
    """Joists spanning y between two rim joists running along x."""

    length: float = 3600.0
    width: float = 3000.0
    spacing: float = 400.0
    joist: tuple = (45.0, 195.0)
    max_piece: float = 6000.0

    def validate(self):
        t, d = self.joist
        for name in ("length", "width", "spacing", "max_piece"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if min(self.joist) <= 0:
            raise ValueError("lumber sizes must be positive")
        if self.spacing < 2 * t:
            raise ValueError("joist spacing too small for the joist thickness")
        if self.length < 2 * t or self.width < 3 * t:
            raise ValueError("floor too small for its joists")
        if self.width - 2 * t > self.max_piece + 1e-6:
            raise ValueError("joists longer than the longest stock length (joists are not spliced)")

    def joist_centres(self):
        return end_and_layout(self.length, self.spacing, self.joist[0])

    def pieces(self):
        self.validate()
        t, d = self.joist
        L, W = self.length, self.width
        out = []
        for y in (t / 2, W - t / 2):
            for a, b in splice(0.0, L, self.joist_centres(), self.max_piece):
                out.append(Piece("Rim joist", (a, y, d / 2), (b, y, d / 2), 0.0, "joist"))
        for x in self.joist_centres():
            out.append(Piece("Joist", (x, t, d / 2), (x, W - t, d / 2), 0.0, "joist"))
        return out


@dataclass
class ProfilePiece:
    """A board cut to an outline in the roof cross-section (y, z), extruded along
    x by its section thickness, centred on x."""

    name: str
    x: float
    profile: list  # [(y, z)] closed outline
    angle: float  # degrees: direction of the board's length in the (y, z) plane
    section: str  # which lumber size
    extrude: float = 0.0  # extrusion along x; 0 = the section thickness

    def cut_length(self):
        """Stock length: the outline's extent along the board."""
        a = math.radians(self.angle)
        along = [y * math.cos(a) + z * math.sin(a) for y, z in self.profile]
        return max(along) - min(along)


@dataclass
class GableRoof:
    """Common rafters on a ridge board, with ceiling joists as rafter ties."""

    length: float = 3600.0  # along the ridge: outside of the end walls
    span: float = 3000.0  # outer face to outer face of the side walls
    pitch: float = 26.565  # degrees (6 in 12)
    overhang: float = 300.0  # horizontal, beyond the wall face
    spacing: float = 600.0
    rafter: tuple = (45.0, 145.0)
    ridge: tuple = (45.0, 195.0)
    seat: float = 95.0  # birdsmouth seat: the top plate width
    ties: bool = True
    tie: tuple = (45.0, 145.0)
    gable_studs: bool = True  # studs in the gable triangles over the end walls
    gable_stud: tuple = (45.0, 95.0)  # (thickness, depth): depth across the end wall
    max_piece: float = 6000.0

    def slope(self):
        return math.tan(math.radians(self.pitch))

    def plumb_depth(self):
        return self.rafter[1] / math.cos(math.radians(self.pitch))

    def heel(self):
        """Vertical depth of the birdsmouth plumb cut."""
        return self.seat * self.slope()

    def ridge_face(self):
        return self.span / 2 - self.ridge[0] / 2

    def bottom(self, y):
        """Underside of the rafter on the near side at y."""
        return (y - self.seat) * self.slope()

    def ridge_top(self):
        return self.bottom(self.ridge_face()) + self.plumb_depth()

    def validate(self):
        for name in ("length", "span", "spacing", "seat", "max_piece"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.overhang < 0:
            raise ValueError("overhang must not be negative")
        if not 5 <= self.pitch <= 60:
            raise ValueError("pitch must be between 5 and 60 degrees")
        if min(self.rafter + self.ridge + self.tie) <= 0:
            raise ValueError("lumber sizes must be positive")
        t = self.rafter[0]
        if self.spacing < t + (self.tie[0] if self.ties else 0):
            raise ValueError("rafter spacing too small for the rafters and ties")
        if self.heel() >= self.plumb_depth():
            raise ValueError("birdsmouth cuts through the rafter: seat too wide for the pitch")
        if self.ridge_face() <= self.seat:
            raise ValueError("span too small for the wall plates")
        if self.gable_studs:
            if min(self.gable_stud) <= 0 or self.gable_stud[1] > self.seat + 1e-6:
                raise ValueError("gable studs must be positive and no deeper than the end wall")
            if self.ties and self.seat + self.tie[0] > self.spacing - self.rafter[0] / 2:
                raise ValueError("rafter spacing too small for the end ceiling joists")
        if self.ties and self.span > self.max_piece + 1e-6:
            raise ValueError("ceiling joists longer than the longest stock (splices need design)")
        longest = max(r.cut_length() for r in self._boards() if r.name == "Rafter")
        if longest > self.max_piece + 1e-6:
            raise ValueError(f"rafters ({longest:.0f} mm) longer than the longest stock length")

    def rafter_centres(self):
        return end_and_layout(self.length, self.spacing, self.rafter[0])

    def _boards(self):
        dp, yr, tail = self.plumb_depth(), self.ridge_face(), -self.overhang
        b = self.bottom
        near = [
            (tail, b(tail)),
            (0.0, b(0.0)),
            (0.0, 0.0),
            (self.seat, 0.0),
            (yr, b(yr)),
            (yr, b(yr) + dp),
            (tail, b(tail) + dp),
        ]
        far = [(self.span - y, z) for y, z in reversed(near)]
        centres = self.rafter_centres()
        out = [
            ProfilePiece("Rafter", x, outline, self.pitch, "rafter")
            for x in centres
            for outline in (near, far)
        ]
        if self.ties:
            tie = self._tie_outline()
            offset = (self.rafter[0] + self.tie[0]) / 2
            for i, x in enumerate(centres):
                tx = x + offset if x < self.length / 2 else x - offset
                if self.gable_studs and i in (0, len(centres) - 1):
                    # End joists go inside the end walls, clear of the gable studs.
                    inside = self.seat + self.tie[0] / 2
                    tx = inside if i == 0 else self.length - inside
                out.append(ProfilePiece("Ceiling joist", tx, tie, 0.0, "tie"))
        if self.gable_studs:
            for x in (self.seat / 2, self.length - self.seat / 2):
                for outline in self._gable_stud_outlines():
                    out.append(
                        ProfilePiece("Gable stud", x, outline, 90.0, "gable_stud", self.seat)
                    )
        return out

    def under_roof(self, y):
        """Highest a gable stud may reach at y: under both rafter lines and the
        ridge board."""
        half_ridge = self.ridge[0] / 2
        top = min(self.bottom(y), self.bottom(self.span - y))
        if abs(y - self.span / 2) <= half_ridge + 1e-9:
            top = min(top, self.ridge_top() - self.ridge[1])
        return top

    def _gable_stud_outlines(self):
        """Outlines (y, z) of the gable studs: on the end wall's top plate, on the
        rafter layout between the front and back walls, tops cut to the roof."""
        t = self.gable_stud[0]
        mid, half_ridge = self.span / 2, self.ridge[0] / 2
        out = []
        for c in layout_centres(self.span, self.spacing, t):
            y0, y1 = c - t / 2, c + t / 2
            if y0 < self.seat - 1e-6 or y1 > self.span - self.seat + 1e-6:
                continue  # over the front or back wall
            kinks = [y for y in (mid - half_ridge, mid, mid + half_ridge) if y0 < y < y1]
            top = [(y, self.under_roof(y)) for y in [y1] + sorted(kinks, reverse=True) + [y0]]
            # Under the ridge band the limit is flat; just outside it, the rafter line.
            if min(z for _, z in top) < 30.0:
                continue  # too short to be worth a stud
            out.append([(y0, 0.0), (y1, 0.0)] + top)
        return out

    def _tie_outline(self):
        """Ceiling joist on the wall plates from outer face to outer face, its top
        corners cut to the roof slope so they stay under the rafter tops."""
        d, span = self.tie[1], self.span
        top_at_wall = self.bottom(0.0) + self.plumb_depth()
        if d <= top_at_wall:
            return [(0.0, 0.0), (span, 0.0), (span, d), (0.0, d)]
        clip = (d - top_at_wall) / self.slope()  # where the slope reaches the tie top
        return [
            (0.0, 0.0),
            (span, 0.0),
            (span, top_at_wall),
            (span - clip, d),
            (clip, d),
            (0.0, top_at_wall),
        ]

    def boards(self):
        """Rafters, ceiling joists and gable studs (profile pieces)."""
        self.validate()
        return self._boards()

    def pieces(self):
        """Ridge board (members), spliced over rafter pairs when longer than stock."""
        self.validate()
        z = self.ridge_top() - self.ridge[1] / 2
        y = self.span / 2
        return [
            Piece("Ridge board", (a, y, z), (b, y, z), 0.0, "ridge")
            for a, b in splice(0.0, self.length, self.rafter_centres(), self.max_piece)
        ]


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

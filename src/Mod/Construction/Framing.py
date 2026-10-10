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
    # Depth of a wall butting against this wall's start / end face (0 = none):
    # a corner stud just past it backs the inside corner.
    corners: tuple = (0.0, 0.0)

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
        if min(self.corners) < 0:
            raise ValueError("corner wall depths must not be negative")
        if sum(self.corners) + 4 * t > self.length:
            raise ValueError("wall too short for its corner studs")
        previous_end = self._corner_x()[0] + t / 2 if self.corners[0] else t
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
        end_limit = self._corner_x()[1] - t / 2 if self.corners[1] else self.length - t
        if previous_end > end_limit + 1e-6:
            raise ValueError("last opening too close to the wall end")

    # ----------------------------------------------------------------- sizes

    def stud_length(self):
        return self.height - (1 + self.top_plates) * self.stud[0]

    def _corner_x(self):
        """Centres of the corner studs at the start and end (where corners apply)."""
        t = self.stud[0]
        return self.corners[0] + t / 2, self.length - self.corners[1] - t / 2

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
        corner_studs = [x for x, c in zip(self._corner_x(), self.corners) if c]
        zones += [(x - t, x + t) for x in corner_studs]  # no layout stud against them
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
        for x in corner_studs:
            vertical("Corner stud", x, bottom, top_of_studs)
        studs += corner_studs  # plates may be spliced over them

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


OPEN_SIDES = ("both", "left", "right", "none")


@dataclass
class Stair:
    """Straight stair on cut stringers. Coordinates: x across the stair, y along
    the run from the face of the first riser, z up from the lower floor.

    Risers are all equal: total_rise split into the fewest risers no higher than
    max_riser. The tread run is set by the tread boards (no ripping):
    boards x depth + gaps - nosing. Treads sit on the stringer cuts; stringers
    are dropped by the tread thickness so every riser is equal, and their top
    ends bear against the upper floor at y = run.
    """

    total_rise: float = 2600.0  # finished floor to finished floor
    width: float = 900.0  # outside of the stringers
    max_riser: float = 190.0  # from the rule set
    tread_boards: int = 2
    tread_gap: float = 6.0
    nosing: float = 25.0
    tread: tuple = (45.0, 145.0)  # (thickness, depth) of a tread board, laid flat
    stringer: tuple = (45.0, 220.0)
    max_stringer_spacing: float = 450.0
    max_piece: float = 6000.0
    # Handrails and guards. Every open side gets newel posts, a handrail and
    # balusters (a guard); with no open side, a handrail on the left wall.
    open_sides: str = "both"
    handrail_height: float = 900.0  # top of the rail above the nosing line
    rail: tuple = (45.0, 70.0)
    post: tuple = (70.0, 70.0)
    baluster: tuple = (45.0, 45.0)
    max_baluster_gap: float = 100.0  # clear gap between balusters and posts

    def risers(self):
        return math.ceil(self.total_rise / self.max_riser - 1e-9)

    def riser(self):
        return self.total_rise / self.risers()

    def run(self):
        """Horizontal depth of one tread, riser face to riser face."""
        boards = self.tread_boards * self.tread[1] + (self.tread_boards - 1) * self.tread_gap
        return boards - self.nosing

    def total_run(self):
        return (self.risers() - 1) * self.run()

    def angle(self):
        return math.degrees(math.atan2(self.riser(), self.run()))

    def throat(self):
        """Stringer depth left under the cuts, square to the stringer."""
        return self.stringer[1] - self.riser() * math.cos(math.radians(self.angle()))

    def validate(self):
        for name in ("total_rise", "width", "max_riser", "max_stringer_spacing", "max_piece"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.tread_boards < 1 or self.tread_gap < 0 or self.nosing < 0:
            raise ValueError("tread boards, gap and nosing must be sensible")
        if min(self.tread + self.stringer) <= 0:
            raise ValueError("lumber sizes must be positive")
        if self.risers() < 2:
            raise ValueError("a stair needs at least two risers")
        if self.run() <= 0:
            raise ValueError("nosing deeper than the tread boards")
        if self.throat() <= 0:
            raise ValueError("stringer too shallow for the riser and run: cuts go through it")
        if self.width < 2 * self.stringer[0]:
            raise ValueError("stair narrower than two stringers")
        longest = max(b.cut_length() for b in self._stringers())
        if longest > self.max_piece + 1e-6:
            raise ValueError(f"stringers ({longest:.0f} mm) longer than the longest stock length")
        if self.open_sides not in OPEN_SIDES:
            raise ValueError(f"open sides must be one of {', '.join(OPEN_SIDES)}")
        if min(self.rail + self.post + self.baluster) <= 0 or self.max_baluster_gap <= 0:
            raise ValueError("handrail and guard sizes must be positive")
        if self.handrail_height <= self.rail[1]:
            raise ValueError("handrail height below the rail's own depth")
        if self.width < 2 * self.post[0] + self.stringer[0]:
            raise ValueError("stair too narrow for newel posts on both sides")

    def stringer_centres(self):
        t = self.stringer[0]
        count = max(2, math.ceil((self.width - t) / self.max_stringer_spacing - 1e-9) + 1)
        step = (self.width - t) / (count - 1)
        return [t / 2 + i * step for i in range(count)]

    def outline(self):
        """Stringer outline (y, z): sawtooth on top, a straight edge below at the
        stringer depth from the line through the cut corners."""
        n, r, t, tt = self.risers(), self.riser(), self.run(), self.tread[0]
        a = math.radians(self.angle())
        depth = self.stringer[1] / math.cos(a)  # vertical depth below the nosing line

        def under(y):
            return r / t * y + r - tt - depth

        foot = (depth - r + tt) * t / r  # where the underside meets the floor
        top_y = (n - 1) * t
        points = [(0.0, 0.0), (max(foot, 0.0), 0.0), (top_y, under(top_y))]
        for i in range(n - 1, 0, -1):
            points.append((i * t, i * r - tt))  # back of tread i, against riser i + 1
            points.append(((i - 1) * t, i * r - tt))  # front of tread i
        return points

    def _stringers(self):
        outline = self.outline()
        return [
            ProfilePiece("Stringer", x, outline, self.angle(), "stringer")
            for x in self.stringer_centres()
        ]

    def boards(self):
        self.validate()
        return self._stringers()

    def pieces(self):
        """Tread boards (members along x, laid flat), handrails and guards."""
        self.validate()
        r, t, tt, bd = self.riser(), self.run(), self.tread[0], self.tread[1]
        out = []
        for i in range(1, self.risers()):
            front = (i - 1) * t - self.nosing
            for j in range(self.tread_boards):
                y = front + j * (bd + self.tread_gap) + bd / 2
                z = i * r - tt / 2
                out.append(Piece("Tread", (0.0, y, z), (self.width, y, z), 90.0, "tread"))
        for x, guarded in self.rail_lines():
            out += self._railing(x, guarded)
        return out

    def rail_lines(self):
        """[(x of the rail centre line, has a guard)] per side with a handrail."""
        left, right = self.post[0] / 2, self.width - self.post[0] / 2
        sides = {"both": [left, right], "left": [left], "right": [right], "none": []}
        lines = [(x, True) for x in sides[self.open_sides]]
        return lines or [(self.rail[0] / 2, False)]  # wall rail on the left

    def nosing_line(self, y):
        """Height of the line through the tread nosings at y."""
        r, t = self.riser(), self.run()
        return r + (y + self.nosing) * r / t

    def _rail_centre(self, y):
        half = self.rail[1] / 2 / math.cos(math.radians(self.angle()))  # vertical half-depth
        return self.nosing_line(y) + self.handrail_height - half

    def _railing(self, x, guarded):
        n, t = self.risers(), self.run()
        a = math.radians(self.angle())
        half_rail = self.rail[1] / 2 / math.cos(a)
        y0, y1 = -self.nosing, (n - 1) * t  # first nosing, top riser face
        out = [
            Piece(
                "Handrail",
                (x, y0, self._rail_centre(y0)),
                (x, y1, self._rail_centre(y1)),
                0.0,
                "rail",
            )
        ]
        if not guarded:
            return out
        p = self.post[1]
        for name, y, z0, z_rail in (
            ("Newel post", y0 - p / 2, 0.0, self._rail_centre(y0)),
            ("Newel post", y1 + p / 2, self.total_rise, self._rail_centre(y1)),
        ):
            out.append(Piece(name, (x, y, z0), (x, y, z_rail + half_rail + 50.0), 0.0, "post"))
        # Balusters: the same number on every tread at the same positions, so
        # they repeat in as many lengths as there are per tread. The pitch keeps
        # clear gaps no wider than max_baluster_gap.
        bt = self.baluster[1]
        per_tread = math.ceil(t / (bt + self.max_baluster_gap) - 1e-9)
        pitch = t / per_tread
        for m in range(per_tread * (n - 1)):
            y = y0 + (m + 0.5) * pitch
            tread = m // per_tread + 1
            bottom = tread * self.riser()
            top = self._rail_centre(y - bt / 2) - half_rail  # under the rail's lowest point
            out.append(Piece("Baluster", (x, y, bottom), (x, y, top), 0.0, "baluster"))
        return out


@dataclass
class Deck:
    """Deck against a house: ledger on the house side, joists on centres to a
    rim joist, carried by a dropped beam on posts, decking boards across the
    joists. Coordinates: x along the house, y out from the house face, z up
    from grade. Footings and guards are not generated (see Checks.deck)."""

    length: float = 3600.0  # along the house
    projection: float = 3000.0  # out from the house face, to the outside of the rim
    height: float = 600.0  # top of the decking above grade
    spacing: float = 400.0
    joist: tuple = (45.0, 195.0)
    beam: tuple = (45.0, 195.0)  # one ply, on edge
    beam_plies: int = 2
    cantilever: float = 400.0  # joists past the beam's outer face
    post: tuple = (95.0, 95.0)
    max_post_spacing: float = 1800.0
    decking: tuple = (28.0, 120.0)  # (thickness, width) of a board, laid flat
    decking_gap: float = 5.0
    max_piece: float = 6000.0

    def joist_top(self):
        return self.height - self.decking[0]

    def beam_bottom(self):
        return self.joist_top() - self.joist[1] - self.beam[1]

    def beam_y(self):
        """Centre of the beam, under the joists."""
        plies = self.beam_plies * self.beam[0]
        return self.projection - self.cantilever - plies / 2

    def joist_centres(self):
        return end_and_layout(self.length, self.spacing, self.joist[0])

    def post_centres(self):
        t = self.post[0]
        bays = max(1, math.ceil((self.length - t) / self.max_post_spacing - 1e-9))
        return [t / 2 + i * (self.length - t) / bays for i in range(bays + 1)]

    def validate(self):
        names = ("length", "projection", "height", "spacing", "max_post_spacing", "max_piece")
        for name in names:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if min(self.joist + self.beam + self.post + self.decking) <= 0:
            raise ValueError("lumber sizes must be positive")
        if self.beam_plies < 1 or self.cantilever < 0 or self.decking_gap < 0:
            raise ValueError("beam plies, cantilever and decking gap must be sensible")
        if self.spacing < 2 * self.joist[0]:
            raise ValueError("joist spacing too small for the joist thickness")
        if self.beam_bottom() <= 0:
            raise ValueError("deck too low for its joists and beam (use a ground-level deck)")
        inner = self.joist[0] + self.beam_plies * self.beam[0] / 2
        if not inner <= self.beam_y() <= self.projection - self.joist[0]:
            raise ValueError("cantilever too long for the projection")
        if self.projection - 2 * self.joist[0] > self.max_piece + 1e-6:
            raise ValueError("joists longer than the longest stock length")

    def pieces(self):
        self.validate()
        t, d = self.joist
        L, P = self.length, self.projection
        top = self.joist_top()
        zj = top - d / 2
        centres = self.joist_centres()
        out = []
        for name, y in (("Ledger", t / 2), ("Rim joist", P - t / 2)):
            for a, b in splice(0.0, L, centres, self.max_piece):
                out.append(Piece(name, (a, y, zj), (b, y, zj), 0.0, "joist"))
        for x in centres:
            out.append(Piece("Joist", (x, t, zj), (x, P - t, zj), 0.0, "joist"))

        # Beam plies on edge under the joists, spliced over posts.
        bt, bd = self.beam
        zb = self.beam_bottom() + bd / 2
        posts = self.post_centres()
        first = self.beam_y() - self.beam_plies * bt / 2
        for k in range(self.beam_plies):
            y = first + (k + 0.5) * bt
            for a, b in splice(0.0, L, posts, self.max_piece):
                out.append(Piece("Beam", (a, y, zb), (b, y, zb), 0.0, "beam"))
        for x in posts:
            out.append(
                Piece(
                    "Post",
                    (x, self.beam_y(), 0.0),
                    (x, self.beam_y(), self.beam_bottom()),
                    0.0,
                    "post",
                )
            )

        # Decking across the joists from the house, joints over joists and
        # staggered between neighbouring rows. The nearest whole number of rows:
        # the outer board ends within half a board of the rim face.
        dt, dw = self.decking
        rows = max(1, round((P + self.decking_gap) / (dw + self.decking_gap)))
        joints = []
        for r in range(rows):
            y = r * (dw + self.decking_gap) + dw / 2
            segments = splice(0.0, L, centres, self.max_piece, joints, self.spacing)
            for a, b in segments:
                out.append(
                    Piece("Decking", (a, y, top + dt / 2), (b, y, top + dt / 2), 90.0, "decking")
                )
            joints = [b for _, b in segments[:-1]]
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

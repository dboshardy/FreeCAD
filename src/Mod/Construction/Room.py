# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: a measured room: walls, openings and appliance gaps, from which wall
# framing and cabinet runs are laid out (design doc Phase 5.2). No FreeCAD imports.
"""A room as measured: walls along the inside faces, each a length and the
turn at its end (left or right, square corners), with doors and windows and
appliance gaps on them.

Coordinates: the first wall starts at (0, 0) and runs along +x; z up from
the floor. Wall i runs from corner i to corner i + 1. The room may be closed
(the last wall ends at the start) or open (an L or U of walls).

From it:
- framing(): one Framing.Wall per wall with its openings, placed on the
  outside of the measured line; at an outside corner a wall runs through and
  the next butts against it (with a corner stud backing the inside corner).
- runs(walls, ...): cabinet entries along the chosen walls: base runs stop
  at doors and appliance gaps; wall runs also at windows and full-height
  appliances; where two chosen walls meet, the first run ends in a blind
  corner cabinet and the second starts past the first run's depth. Leftover
  space becomes fillers.
"""

import math
from dataclasses import dataclass, field

import Cabinet
import Framing

TURNS = ("left", "right")
GAP_KINDS = ("range", "dishwasher", "fridge", "other")
FULL_HEIGHT = ("fridge",)  # gaps that also stop the wall cabinets
SWAP = {"blind_left": "blind_right", "blind_right": "blind_left"}


@dataclass
class Room:
    walls: list = field(default_factory=lambda: [(3600.0, "left"), (2400.0, "left")])
    height: float = 2440.0
    openings: list = field(default_factory=list)  # [(wall, kind, width, height, at, sill)]
    gaps: list = field(default_factory=list)  # [(wall, kind, at, width)]

    def validate(self):
        if not self.walls:
            raise ValueError("a room needs at least one wall")
        for i, (length, turn) in enumerate(self.walls):
            if length <= 0:
                raise ValueError(f"wall {i + 1}: length must be positive")
            if turn not in TURNS:
                raise ValueError(f"wall {i + 1}: turn must be left or right")
        for wall, kind, width, height, at, sill in self.openings:
            self._on_wall(wall, at, width, f"{kind}")
        for wall, kind, at, width in self.gaps:
            if kind not in GAP_KINDS:
                raise ValueError(f"gap kind must be one of {', '.join(GAP_KINDS)}")
            self._on_wall(wall, at, width, kind)

    def _on_wall(self, wall, at, width, what):
        if not 1 <= wall <= len(self.walls):
            raise ValueError(f"{what} on wall {wall}: there are {len(self.walls)} walls")
        if at < 0 or width <= 0 or at + width > self.walls[wall - 1][0] + 1e-6:
            raise ValueError(f"{what} on wall {wall} does not fit on the wall")

    # ----------------------------------------------------------- geometry

    def corners(self):
        """[(x, y)] of the wall starts, then the last wall's end."""
        points, x, y, d = [(0.0, 0.0)], 0.0, 0.0, 0
        for length, turn in self.walls:
            dx, dy = ((1, 0), (0, 1), (-1, 0), (0, -1))[d]
            x, y = x + dx * length, y + dy * length
            points.append((x, y))
            d = (d + (1 if turn == "left" else -1)) % 4
        return points

    def direction(self, i):
        """Unit direction of wall i (0-based)."""
        d = sum(1 if t == "left" else -1 for _, t in self.walls[:i]) % 4
        return ((1, 0), (0, 1), (-1, 0), (0, -1))[d]

    def closed(self):
        x, y = self.corners()[-1]
        return abs(x) < 1e-6 and abs(y) < 1e-6

    def inside_is_left(self):
        """True when the room's inside is on the left of the walls' direction
        (mostly left turns; for an open room, its turns decide)."""
        lefts = sum(1 for _, t in self.walls if t == "left")
        return lefts * 2 >= len(self.walls)

    def outward(self, i):
        """Unit normal of wall i pointing out of the room."""
        dx, dy = self.direction(i)
        return (dy, -dx) if self.inside_is_left() else (-dy, dx)

    def corner_kind(self, i):
        """Corner at the end of wall i: "outside" (the walls' outer faces meet
        beyond the measured corner: a convex room corner), "inside", or None
        at an open end."""
        if i == len(self.walls) - 1 and not self.closed():
            return None
        toward_inside = (self.walls[i][1] == "left") == self.inside_is_left()
        return "outside" if toward_inside else "inside"

    def corner_before(self, i):
        """Corner kind at the start of wall i."""
        if i == 0:
            return self.corner_kind(len(self.walls) - 1) if self.closed() else None
        return self.corner_kind(i - 1)

    # ------------------------------------------------------------ framing

    def framing(self, depth, **wall_options):
        """[(name, Framing.Wall, origin (x, y), local x, local y)] for every
        wall: place the wall's frame with its local x and y along these
        directions (z up). depth: the wall framing's depth (stud depth). The
        wall's x runs along the wall from its start, its body lies outside
        the measured line. At an outside corner the wall runs on through the
        corner by `depth` and the next wall butts against it; at an inside
        corner it stops `depth` short."""
        self.validate()
        out = []
        for i, (length, _) in enumerate(self.walls):
            start = self.corners()[i]
            end_kind, start_kind = self.corner_kind(i), self.corner_before(i)
            extend = depth if end_kind == "outside" else (-depth if end_kind == "inside" else 0)
            # The wall butting at our start (an outside corner before us) backs onto
            # its end face: a corner stud here backs that inside corner.
            corners = (depth if start_kind == "outside" else 0.0, 0.0)
            if end_kind == "inside":
                corners = (corners[0], depth)
            openings = [
                Framing.Opening(kind, at, width, height, sill)
                for wall, kind, width, height, at, sill in self.openings
                if wall == i + 1
            ]
            wall = Framing.Wall(
                length=length + extend,
                height=self.height,
                openings=openings,
                corners=corners,
                **wall_options,
            )
            (dx, dy), (nx, ny) = self.direction(i), self.outward(i)
            if dx * ny - dy * nx > 0:  # local y can point outwards: right-handed
                origin, local_y = start, (nx, ny)
            else:  # point local y inwards and start from the outer face
                origin, local_y = (start[0] + nx * depth, start[1] + ny * depth), (-nx, -ny)
            out.append((f"Wall {i + 1}", wall, origin, (dx, dy), local_y))
        return out

    # ------------------------------------------------------------ cabinets

    def runs(self, walls, depth, upper=False, corner_width=1000.0):
        """Cabinet runs along the walls numbered in `walls` (1-based, in
        order): [(wall, entries [(width, style)], origin (x, y), local x)]:
        a run's local x runs along the wall from origin, its local y (the
        cabinets' backs) towards the wall, so the entries are in that order.
        Place the run with its y = 0 (the carcass front) the carcass depth
        in front of the wall. depth: cabinet depth with its fronts, which a
        run meeting another at a corner starts past. upper: wall cabinets
        (they also stop at windows and full-height appliances). A run ending
        at a corner where the next chosen wall starts ends in a blind corner
        cabinet of corner_width."""
        self.validate()
        out = []
        chosen = set(walls)
        for w in walls:
            i = w - 1
            length = self.walls[i][0]
            # Into the corner at the end when the next chosen wall continues there.
            n = (i + 1) % len(self.walls)
            corner_end = (
                (n + 1) in chosen and self.corner_kind(i) == "outside" and (n != 0 or self.closed())
            )
            p = (i - 1) % len(self.walls)
            corner_start = (
                (p + 1) in chosen
                and self.corner_before(i) == "outside"
                and (i != 0 or self.closed())
            )
            start = depth if corner_start else 0.0
            blocked = sorted(self._blocked(w, upper))
            entries, x = [], start
            end = length
            if corner_end:
                end = length - corner_width
            for a, b, kind in blocked + [(end, end, None)]:
                a, b = max(a, x), min(max(b, x), end)
                if a > x + 1e-6:
                    entries += _fill(a - x)
                if kind is not None and b > a + 1e-6:
                    entries.append((b - a, "gap"))
                x = max(x, b)
            if corner_end:
                entries.append((corner_width, "blind_right"))
            if corner_start and start > 0:
                entries.insert(0, (start, "gap"))  # under the meeting run's corner
            (dx, dy), (nx, ny) = self.direction(i), self.outward(i)
            local_x = (ny, -nx)  # with y = outward and z up, right-handed
            origin = self.corners()[i]
            if local_x != (dx, dy):  # the run goes from the wall's end backwards
                x0, y0 = origin
                origin = (x0 + dx * length, y0 + dy * length)
                entries = [(width, SWAP.get(style, style)) for width, style in reversed(entries)]
            out.append((w, entries, origin, local_x))
        return out

    def _blocked(self, wall, upper):
        """[(start, end, kind)] along a wall where cabinets may not go."""
        out = [
            (at, at + width, kind)
            for w, kind, width, h, at, s in self.openings
            if w == wall and (kind == "door" or upper)
        ]
        out += [
            (at, at + width, kind)
            for w, kind, at, width in self.gaps
            if w == wall and (not upper or kind in FULL_HEIGHT)
        ]
        return out


def _fill(length):
    """Run entries filling a length: standard widths, the rest a filler."""
    widths = Cabinet.fill_widths(length) if length >= min(Cabinet.STANDARD_WIDTHS) else []
    entries = [(w, None) for w in widths]
    rest = length - sum(widths)
    if rest > 0.5:
        entries.append((rest, "filler"))
    return entries


def plan(points):
    """Walls (length, turn) from a closed or open polygon of square corners
    [(x, y)], e.g. a sketch's vertices in order. Raises ValueError for a
    corner that is not square."""
    walls = []
    for k in range(len(points) - 1):
        (x0, y0), (x1, y1) = points[k], points[k + 1]
        length = math.hypot(x1 - x0, y1 - y0)
        turn = "left"
        if k + 2 < len(points) or points[0] == points[-1]:
            x2, y2 = points[k + 2] if k + 2 < len(points) else points[1]
            cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
            dot = (x1 - x0) * (x2 - x1) + (y1 - y0) * (y2 - y1)
            if abs(dot) > 1e-3 * length * math.hypot(x2 - x1, y2 - y1):
                raise ValueError(f"corner {k + 2} is not square: rooms take square corners")
            turn = "left" if cross > 0 else "right"
        walls.append((length, turn))
    return walls

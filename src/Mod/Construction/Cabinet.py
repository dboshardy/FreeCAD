# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: frameless base cabinet generator (design doc §5.4). No FreeCAD imports.
"""Frameless (32 mm system) base cabinet, butt-jointed carcass on a plinth.

Axes: x = width (left to right), y = depth (front face of the carcass at
y = 0, back towards +y), z = up from the floor. Sizes in millimetres.
Doors are full overlay and sit in front of the carcass (y < 0).
"""

from dataclasses import dataclass


@dataclass
class Part:
    name: str
    role: str  # "carcass", "back", "door", "plinth"
    size: tuple  # (dx, dy, dz)
    pos: tuple  # (x, y, z) of the minimum corner
    grain: str | None = None  # axis the grain runs along: "x", "y", "z" or None

    def cut_size(self):
        """(length, width, thickness): length along the grain, or the longest side."""
        dims = dict(zip("xyz", self.size))
        thick_axis = min(dims, key=dims.get)
        faces = [a for a in "xyz" if a != thick_axis]
        if self.grain in faces:
            length_axis = self.grain
        else:
            length_axis = max(faces, key=dims.get)
        width_axis = next(a for a in faces if a != length_axis)
        return dims[length_axis], dims[width_axis], dims[thick_axis]


@dataclass
class BaseCabinet:
    width: float = 600.0
    height: float = 870.0  # floor to top of carcass, plinth included
    depth: float = 580.0  # carcass + back, doors excluded
    thickness: float = 18.0  # carcass and door panels
    back_thickness: float = 6.0
    plinth_height: float = 100.0
    plinth_setback: float = 50.0  # front kick board behind the carcass front
    stretcher_width: float = 100.0
    shelves: int = 1
    shelf_setback: float = 20.0  # from the front edge
    shelf_clearance: float = 1.0  # per side, for adjustable shelves
    doors: int = 0  # 0 = automatic: one up to 600 mm wide, else two
    door_gap: float = 3.0  # between doors; half of it at the outer edges

    def validate(self):
        """Raises ValueError for sizes that cannot be built."""
        for name in ("width", "height", "depth", "thickness", "back_thickness", "stretcher_width"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in (
            "plinth_height",
            "plinth_setback",
            "shelf_setback",
            "shelf_clearance",
            "door_gap",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")
        if self.shelves < 0 or self.doors < 0:
            raise ValueError("shelves and doors must not be negative")
        if self.width <= 2 * self.thickness + 2 * self.shelf_clearance:
            raise ValueError("width too small for the panel thickness")
        if self.height - self.plinth_height <= 2 * self.thickness * (self.shelves + 1):
            raise ValueError("height too small for plinth, top, bottom and shelves")
        if self.depth - self.back_thickness <= max(2 * self.stretcher_width, self.shelf_setback):
            raise ValueError("depth too small for stretchers and shelves")
        if self.plinth_setback + self.thickness > self.depth - self.back_thickness - self.thickness:
            raise ValueError("plinth setback too large for the depth")
        if self.door_width() <= 0 or self.height - self.plinth_height <= self.door_gap:
            raise ValueError("door gap too large for the cabinet")

    def door_count(self):
        return self.doors or (1 if self.width <= 600 else 2)

    def door_width(self):
        n = self.door_count()
        return (self.width - self.door_gap * n) / n

    def parts(self):
        self.validate()
        t, tb, k = self.thickness, self.back_thickness, self.plinth_height
        w, h = self.width, self.height
        box_h = h - k  # carcass height
        inner_w = w - 2 * t
        carcass_d = self.depth - tb
        out = [
            Part("Left side", "carcass", (t, carcass_d, box_h), (0, 0, k), "z"),
            Part("Right side", "carcass", (t, carcass_d, box_h), (w - t, 0, k), "z"),
            Part("Bottom", "carcass", (inner_w, carcass_d, t), (t, 0, k), "x"),
            Part(
                "Front stretcher", "carcass", (inner_w, self.stretcher_width, t), (t, 0, h - t), "x"
            ),
            Part(
                "Back stretcher",
                "carcass",
                (inner_w, self.stretcher_width, t),
                (t, carcass_d - self.stretcher_width, h - t),
                "x",
            ),
            Part("Back", "back", (w, tb, box_h), (0, carcass_d, k), "z"),
        ]
        # Shelves evenly spaced in the opening between bottom and stretchers.
        opening = box_h - 2 * t
        for i in range(self.shelves):
            z = k + t + (i + 1) * opening / (self.shelves + 1) - t / 2
            out.append(
                Part(
                    f"Shelf {i + 1}",
                    "carcass",
                    (inner_w - 2 * self.shelf_clearance, carcass_d - self.shelf_setback, t),
                    (t + self.shelf_clearance, self.shelf_setback, z),
                    "x",
                )
            )
        # Plinth: front kick board and rear rail under the carcass.
        if k > 0:
            out.append(Part("Kick board", "plinth", (w, t, k), (0, self.plinth_setback, 0), "x"))
            out.append(Part("Plinth rail", "plinth", (w, t, k), (0, carcass_d - t, 0), "x"))
        n, dw, gap = self.door_count(), self.door_width(), self.door_gap
        for i in range(n):
            x = gap / 2 + i * (dw + gap)
            label = "Door" if n == 1 else f"Door {i + 1}"
            out.append(Part(label, "door", (dw, t, box_h - gap), (x, -t, k + gap / 2), "z"))
        return out

# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: gable shed template (design doc §5.4 templates, Phase 5 exit criteria). No FreeCAD imports.
"""Gable shed: floor platform, four stud walls (door centred in the front
wall), gable roof with the ridge along the front and gable studs over the side
walls, sheathing on floor, walls, gable ends and roof.

World coordinates: x along the front wall, y from the front wall's outer face
to the back, z up from the bottom of the floor joists (on a slab: from the
top of the slab). The front and back walls run the full length; the side
walls (gable ends) fit between them.

A garage is a shed on a slab with a wide door (GARAGE).
"""

import re
from dataclasses import dataclass

import Framing
import Sheathing


WALLS = ("front", "back", "left", "right")
ROOFS = ("gable", "shed")
FOUNDATIONS = ("floor", "slab")


@dataclass
class Component:
    name: str
    model: object  # Framing.Floor / Wall / GableRoof / ShedRoof
    origin: tuple  # where the model's origin sits
    rotation: float  # degrees about z
    sheathing_extend: tuple = (0.0, 0.0)  # walls: sheathing past the ends


@dataclass
class Shed:
    length: float = 3600.0  # front and back walls, outside
    width: float = 3000.0  # side walls, outside
    wall_height: float = 2440.0
    door_width: float = 900.0
    door_height: float = 2100.0
    pitch: float = 26.565
    overhang: float = 300.0
    stud_spacing: float = 600.0
    joist_spacing: float = 400.0
    rafter_spacing: float = 600.0
    stud: tuple = (45.0, 95.0)
    header: tuple = (45.0, 195.0)
    joist: tuple = (45.0, 195.0)
    rafter: tuple = (45.0, 145.0)
    ridge: tuple = (45.0, 195.0)
    tie: tuple = (45.0, 145.0)
    floor_sheet: float = 18.0  # thickness: walls stand on it
    wall_sheet: float = 12.0  # thickness: side wall sheathing wraps the corners
    max_piece: float = 6000.0
    # Doors and windows: [(wall, Framing.Opening)] with wall front / back / left /
    # right and positions from the wall framing's left end seen from outside.
    # None: one door of door_width x door_height centred in the front wall.
    openings: tuple = None
    roof: str = "gable"  # or "shed": mono-pitch, low at the front, the back wall taller
    # "floor": a framed floor platform; "slab": walls on a concrete slab (top at
    # z = 0) with a thickened edge, slab = (thickness, edge width, edge depth).
    foundation: str = "floor"
    slab: tuple = (100.0, 300.0, 450.0)

    def slab_model(self):
        """The Framing.Slab under a shed on a slab, else None."""
        if self.foundation != "slab":
            return None
        return Framing.Slab(self.length, self.width, *self.slab)

    def validate(self):
        d = self.stud[1]
        if self.foundation not in FOUNDATIONS:
            raise ValueError(f"foundation must be one of {', '.join(FOUNDATIONS)}")
        if self.width <= 2 * d + 2 * self.stud[0]:
            raise ValueError("shed too narrow for its walls")
        if self.door_width >= self.length - 2 * d:
            raise ValueError("door wider than the front wall")
        if self.roof not in ROOFS:
            raise ValueError(f"roof must be one of {', '.join(ROOFS)}")
        for wall, _ in self.openings or ():
            if wall not in WALLS:
                raise ValueError(f"opening on '{wall}': walls are {', '.join(WALLS)}")

    def wall_openings(self, wall):
        if self.openings is None:
            if wall != "front":
                return []
            x = (self.length - self.door_width) / 2
            return [Framing.Opening("door", x, self.door_width, self.door_height)]
        return [o for w, o in self.openings if w == wall]

    def shed_roof(self):
        return Framing.ShedRoof(
            length=self.length,
            span=self.width,
            pitch=self.pitch,
            overhang=self.overhang,
            spacing=self.rafter_spacing,
            rafter=self.rafter,
            seat=self.stud[1],
            max_piece=self.max_piece,
            gable_studs=True,
            gable_stud=self.stud,
        )

    def components(self):
        self.validate()
        d = self.stud[1]
        L, W, H = self.length, self.width, self.wall_height
        on_slab = self.foundation == "slab"
        z_walls = 0.0 if on_slab else self.joist[1] + self.floor_sheet
        rise = self.shed_roof().rise() if self.roof == "shed" else 0.0

        def wall(length, openings=(), corners=(0.0, 0.0), height=H):
            return Framing.Wall(
                length=length,
                height=height,
                spacing=self.stud_spacing,
                stud=self.stud,
                header=self.header,
                openings=list(openings),
                max_piece=self.max_piece,
                corners=corners,
            )

        side = W - 2 * d
        wrap = d + self.wall_sheet  # side sheathing covers the front/back wall ends
        floor = Framing.Floor(
            length=L,
            width=W,
            spacing=self.joist_spacing,
            joist=self.joist,
            max_piece=self.max_piece,
        )
        floors = [] if on_slab else [Component("Floor", floor, (0.0, 0.0, 0.0), 0.0)]
        return floors + [
            # Front and back walls run through; the side walls butt against them,
            # so each end gets a corner stud backing the inside corner.
            Component(
                "Front wall", wall(L, self.wall_openings("front"), (d, d)), (0.0, 0.0, z_walls), 0.0
            ),
            Component(
                "Back wall",
                wall(L, self.wall_openings("back"), (d, d), H + rise),
                (L, W, z_walls),
                180.0,
            ),
            Component(
                "Left wall",
                wall(side, self.wall_openings("left")),
                (0.0, W - d, z_walls),
                -90.0,
                (wrap, wrap),
            ),
            Component(
                "Right wall",
                wall(side, self.wall_openings("right")),
                (L, d, z_walls),
                90.0,
                (wrap, wrap),
            ),
            Component(
                "Roof",
                (
                    self.shed_roof()
                    if self.roof == "shed"
                    else Framing.GableRoof(
                        length=L,
                        span=W,
                        pitch=self.pitch,
                        overhang=self.overhang,
                        spacing=self.rafter_spacing,
                        rafter=self.rafter,
                        ridge=self.ridge,
                        seat=d,
                        tie=self.tie,
                        gable_stud=self.stud,
                        max_piece=self.max_piece,
                    )
                ),
                (0.0, 0.0, z_walls + H),
                0.0,
            ),
        ]

    def sections(self):
        """Framing section name -> (thickness, depth)."""
        return {
            "stud": self.stud,
            "header": self.header,
            "joist": self.joist,
            "rafter": self.rafter,
            "ridge": self.ridge,
            "tie": self.tie,
            "gable_stud": self.stud,
        }


# A single garage: 3.6 m wide at the door, 6 m deep, a 2400 x 2100 door, on a
# slab. The door header carries the rafters: choose it for your loads.
GARAGE = {
    "length": 3600.0,
    "width": 6000.0,
    "door_width": 2400.0,
    "door_height": 2100.0,
    "foundation": "slab",
}


def sheathing_surfaces(component):
    return Sheathing.surfaces(component.model, component.sheathing_extend)


def parse_openings(text):
    """'front: door 900x2100 @ 1350; right: window 600x600 @ 1000 sill 1200'
    -> [(wall, Framing.Opening)]."""
    out = []
    for entry in filter(None, (e.strip() for e in text.split(";"))):
        m = re.match(r"^(\w+)\s*:\s*(.+)$", entry)
        if not m or m.group(1).lower() not in WALLS:
            raise ValueError(
                f"'{entry}': start with the wall ({', '.join(WALLS)}), e.g. "
                "'front: door 900x2100 @ 1350'"
            )
        out += [(m.group(1).lower(), o) for o in Framing.parse_openings(m.group(2))]
    return out


def format_openings(openings):
    """Inverse of parse_openings."""
    return "; ".join(f"{w}: {Framing.format_openings([o])}" for w, o in openings)

# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: gable shed template (design doc §5.4 templates, Phase 5 exit criteria). No FreeCAD imports.
"""Gable shed: floor platform, four stud walls (door centred in the front
wall), gable roof with the ridge along the front and gable studs over the side
walls, sheathing on floor, walls, gable ends and roof.

World coordinates: x along the front wall, y from the front wall's outer face
to the back, z up from the bottom of the floor joists. The front and back walls
run the full length; the side walls (gable ends) fit between them.
"""

from dataclasses import dataclass

import Framing
import Sheathing


@dataclass
class Component:
    name: str
    model: object  # Framing.Floor / Wall / GableRoof
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

    def validate(self):
        d = self.stud[1]
        if self.width <= 2 * d + 2 * self.stud[0]:
            raise ValueError("shed too narrow for its walls")
        if self.door_width >= self.length - 2 * d:
            raise ValueError("door wider than the front wall")

    def components(self):
        self.validate()
        d = self.stud[1]
        L, W, H = self.length, self.width, self.wall_height
        z_walls = self.joist[1] + self.floor_sheet
        door = Framing.Opening("door", (L - self.door_width) / 2, self.door_width, self.door_height)

        def wall(length, openings=(), corners=(0.0, 0.0)):
            return Framing.Wall(
                length=length,
                height=H,
                spacing=self.stud_spacing,
                stud=self.stud,
                header=self.header,
                openings=list(openings),
                max_piece=self.max_piece,
                corners=corners,
            )

        side = W - 2 * d
        wrap = d + self.wall_sheet  # side sheathing covers the front/back wall ends
        return [
            Component(
                "Floor",
                Framing.Floor(
                    length=L,
                    width=W,
                    spacing=self.joist_spacing,
                    joist=self.joist,
                    max_piece=self.max_piece,
                ),
                (0.0, 0.0, 0.0),
                0.0,
            ),
            # Front and back walls run through; the side walls butt against them,
            # so each end gets a corner stud backing the inside corner.
            Component("Front wall", wall(L, [door], (d, d)), (0.0, 0.0, z_walls), 0.0),
            Component("Back wall", wall(L, (), (d, d)), (L, W, z_walls), 180.0),
            Component("Left wall", wall(side), (0.0, W - d, z_walls), -90.0, (wrap, wrap)),
            Component("Right wall", wall(side), (L, d, z_walls), 90.0, (wrap, wrap)),
            Component(
                "Roof",
                Framing.GableRoof(
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


def sheathing_surfaces(component):
    return Sheathing.surfaces(component.model, component.sheathing_extend)

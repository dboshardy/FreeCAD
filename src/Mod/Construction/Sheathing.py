# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: sheathing layers (design doc §5.4). No FreeCAD imports.
"""Sheet goods covering a framed surface with staggered seams.

A surface is a rectangle in a plane: origin, unit axes u and v, size U x V,
normal n = u x v pointing away from the framing (panels sit on the n side).
Panels are laid in rows; the sheet's long side runs along u ("u") or v ("v").
"""

import math
from dataclasses import dataclass, field

import Framing


@dataclass
class Surface:
    name: str
    origin: tuple
    u: tuple
    v: tuple
    size: tuple  # (U, V)
    long_along: str = "u"  # sheet length along u or v
    openings: list = field(default_factory=list)  # [(u0, v0, du, dv)] holes

    def normal(self):
        u, v = self.u, self.v
        return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def cover(size, sheet, long_along="u", stagger=True):
    """Panels [(u0, v0, du, dv)] covering size = (U, V) with sheets of
    sheet = (long, short) mm. Rows run along the long side; with stagger, every
    other row starts half a sheet over so seams do not line up (only when a
    row is longer than one sheet)."""
    U, V = size
    long, short = sheet
    if min(U, V, long, short) <= 0:
        raise ValueError("surface and sheet sizes must be positive")
    if long_along not in ("u", "v"):
        raise ValueError("long side must run along u or v")
    along, across = (U, V) if long_along == "u" else (V, U)
    panels = []
    for row in range(math.ceil(across / short - 1e-9)):
        a0 = row * short
        da = min(short, across - a0)
        # Staggering only helps when a row needs more than one sheet.
        offset = long / 2 if stagger and row % 2 and along > long + 1e-6 else 0.0
        s = -offset
        while s < along - 1e-6:
            s0, s1 = max(s, 0.0), min(s + long, along)
            if s1 - s0 >= 1.0:  # no slivers
                panels.append((s0, a0, s1 - s0, da) if long_along == "u" else (a0, s0, da, s1 - s0))
            s += long
    return panels


def surfaces(model, extend=(0.0, 0.0)):
    """Surfaces to sheathe on a Framing model, in the model's coordinates.
    extend: (start, end) mm a wall's sheathing reaches past its ends, e.g. to
    wrap a corner."""
    if isinstance(model, Framing.Floor):
        top = model.joist[1]
        return [Surface("Subfloor", (0, 0, top), (1, 0, 0), (0, 1, 0), (model.length, model.width))]
    if isinstance(model, Framing.Wall):
        a, b = extend
        holes = [(o.x + a, o.sill, o.width, o.height) for o in model.openings]
        # Outer face at y = 0; panels on the -y side; sheets upright.
        return [
            Surface(
                "Wall sheathing",
                (-a, 0, 0),
                (1, 0, 0),
                (0, 0, 1),
                (model.length + a + b, model.height),
                long_along="v",
                openings=holes,
            )
        ]
    if isinstance(model, Framing.GableRoof):
        a = math.radians(model.pitch)
        c, s = math.cos(a), math.sin(a)
        oh, half = model.overhang, model.span / 2
        top = model.bottom(-oh) + model.plumb_depth()  # rafter top at the tail
        slope = (half + oh) / c
        near = Surface("Roof sheathing", (0, -oh, top), (1, 0, 0), (0, c, s), (model.length, slope))
        far = Surface(
            "Roof sheathing",
            (model.length, model.span + oh, top),
            (-1, 0, 0),
            (0, -c, s),
            (model.length, slope),
        )
        return [near, far]
    raise ValueError("sheathing needs a floor, wall or gable roof")

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
    clip: list = None  # convex outline [(u, v)], counter-clockwise; None = the rectangle

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
        s = 0.0 - offset  # not -offset: that gives -0.0 for an unstaggered row
        while s < along - 1e-6:
            s0, s1 = max(s, 0.0), min(s + long, along)
            if s1 - s0 >= 1.0:  # no slivers
                panels.append((s0, a0, s1 - s0, da) if long_along == "u" else (a0, s0, da, s1 - s0))
            s += long
    return panels


def clip_polygon(polygon, convex):
    """Part of polygon inside the convex, counter-clockwise outline
    (Sutherland-Hodgman). Both are [(u, v)]."""
    out = list(polygon)
    for (ax, ay), (bx, by) in zip(convex, convex[1:] + convex[:1]):

        def inside(p):
            return (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) >= -1e-9

        def cross(p, q):
            # Where p-q crosses the line a-b.
            den = (p[0] - q[0]) * (ay - by) - (p[1] - q[1]) * (ax - bx)
            t = ((p[0] - ax) * (ay - by) - (p[1] - ay) * (ax - bx)) / den
            return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))

        points, out = out, []
        for p, q in zip(points, points[1:] + points[:1]):
            if inside(q):
                if not inside(p):
                    out.append(cross(p, q))
                out.append(q)
            elif inside(p):
                out.append(cross(p, q))
        if not out:
            return []
    return out


def area(polygon):
    return (
        abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, polygon[1:] + polygon[:1]))) / 2
    )


def cover_surface(surface, sheet, stagger=True):
    """cover() of a surface; with a clip outline, each panel is cut to it and
    reported as the bounding rectangle of what remains (what is cut from a sheet)."""
    panels = cover(surface.size, sheet, surface.long_along, stagger)
    if not surface.clip:
        return panels
    out = []
    for u, v, du, dv in panels:
        piece = clip_polygon([(u, v), (u + du, v), (u + du, v + dv), (u, v + dv)], surface.clip)
        if piece and area(piece) >= 100.0:  # drop slivers under 1 cm2
            us, vs = [p[0] for p in piece], [p[1] for p in piece]
            out.append((min(us), min(vs), max(us) - min(us), max(vs) - min(vs)))
    return out


def surfaces(model, extend=(0.0, 0.0)):
    """Surfaces to sheathe on a Framing model, in the model's coordinates.
    extend: (start, end) mm a wall's sheathing reaches past its ends, e.g. to
    wrap a corner."""
    if isinstance(model, Framing.Floor):
        top = model.joist[1]
        holes = [(x, y, w, l) for x, y, w, l in model.openings]
        size = (model.length, model.width)
        return [Surface("Subfloor", (0, 0, top), (1, 0, 0), (0, 1, 0), size, openings=holes)]
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
        out = [near, far]
        if model.gable_studs:
            # Gable ends: outer faces of the end walls, up to the rafter tops.
            span = model.span
            eave = model.bottom(0.0) + model.plumb_depth()
            peak = model.bottom(span / 2) + model.plumb_depth()
            outline = [(0.0, 0.0), (span, 0.0), (span, eave), (span / 2, peak), (0.0, eave)]
            for x, u in ((0.0, (0, -1, 0)), (model.length, (0, 1, 0))):
                origin = (x, span if u[1] < 0 else 0.0, 0.0)
                out.append(
                    Surface(
                        "Gable sheathing", origin, u, (0, 0, 1), (span, peak), "v", clip=outline
                    )
                )
        return out
    if isinstance(model, Framing.ShedRoof):
        a = math.radians(model.pitch)
        c, s = math.cos(a), math.sin(a)
        oh = model.overhang
        top = model.bottom(-oh) + model.plumb_depth()
        slope = (model.span + 2 * oh) / c
        return [
            Surface("Roof sheathing", (0, -oh, top), (1, 0, 0), (0, c, s), (model.length, slope))
        ]
    raise ValueError("sheathing needs a floor, wall, gable roof or shed roof")

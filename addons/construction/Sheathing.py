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
    # u of the framing members under the surface (stud, joist or rafter
    # centres): joints between sheets along u fall on them.
    supports: tuple = ()

    def normal(self):
        u, v = self.u, self.v
        return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def _on_support(start, reach, supports):
    """The furthest support past start within reach of it (a joint there is
    backed by framing); start + reach when none is."""
    backed = [c for c in supports if start + 1.0 < c <= start + reach + 1e-6]
    return max(backed) if backed else start + reach


def cover(size, sheet, long_along="u", stagger=True, supports=()):
    """Panels [(u0, v0, du, dv)] covering size = (U, V) with sheets of
    sheet = (long, short) mm. Rows run along the long side; with stagger, every
    other row starts half a sheet over so seams do not line up (only when a
    row is longer than one sheet). supports: u of the framing under the
    surface; joints between sheets along u are cut back to fall on them."""
    U, V = size
    long, short = sheet
    if min(U, V, long, short) <= 0:
        raise ValueError("surface and sheet sizes must be positive")
    if long_along not in ("u", "v"):
        raise ValueError("long side must run along u or v")
    along, across = (U, V) if long_along == "u" else (V, U)
    along_supports = supports if long_along == "u" else ()
    across_supports = supports if long_along == "v" else ()
    rows, a0 = [], 0  # an int when the sizes are: keeps the printed panels tidy
    while a0 < across - 1e-6:  # rows across, their joints on framing when given
        a1 = across if a0 + short >= across - 1e-6 else _on_support(a0, short, across_supports)
        rows.append((a0, a1 - a0))
        a0 = a1
    panels = []
    for row, (a0, da) in enumerate(rows):
        # Staggering only helps when a row needs more than one sheet.
        offset = long / 2 if stagger and row % 2 and along > long + 1e-6 else 0.0
        s = 0.0
        first = True
        while s < along - 1e-6:
            reach = long - offset if first else long
            s1 = along if s + reach >= along - 1e-6 else _on_support(s, reach, along_supports)
            if s1 - s >= 1.0:  # no slivers
                panels.append((s, a0, s1 - s, da) if long_along == "u" else (a0, s, da, s1 - s))
            s, first = s1, False
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
    panels = cover(surface.size, sheet, surface.long_along, stagger, surface.supports)
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
        joists = tuple(x for _, x, _, _ in model._joist_runs())
        return [
            Surface(
                "Subfloor", (0, 0, top), (1, 0, 0), (0, 1, 0), size, openings=holes, supports=joists
            )
        ]
    if isinstance(model, Framing.Wall):
        a, b = extend
        holes = [(o.x + a, o.sill, o.width, o.height) for o in model.openings]
        studs = tuple(p.start[0] + a for p in model.pieces() if abs(p.start[0] - p.end[0]) < 1e-6)
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
                supports=studs,
            )
        ]
    if isinstance(model, Framing.GableRoof):
        a = math.radians(model.pitch)
        c, s = math.cos(a), math.sin(a)
        oh, half = model.overhang, model.span / 2
        top = model.bottom(-oh) + model.plumb_depth()  # rafter top at the tail
        slope = (half + oh) / c
        rafters = tuple(model.rafter_centres())
        near = Surface(
            "Roof sheathing",
            (0, -oh, top),
            (1, 0, 0),
            (0, c, s),
            (model.length, slope),
            supports=rafters,
        )
        far = Surface(
            "Roof sheathing",
            (model.length, model.span + oh, top),
            (-1, 0, 0),
            (0, -c, s),
            (model.length, slope),
            supports=tuple(model.length - x for x in model.rafter_centres()),
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
        rafters = tuple(model.rafter_centres())
        out = [
            Surface(
                "Roof sheathing",
                (0, -oh, top),
                (1, 0, 0),
                (0, c, s),
                (model.length, slope),
                supports=rafters,
            )
        ]
        if model.gable_studs:
            # End walls up to the rafter tops: a trapezoid, low at the front.
            span, dp = model.span, model.plumb_depth()
            low, high = model.bottom(0.0) + dp, model.bottom(span) + dp
            outline = [(0.0, 0.0), (span, 0.0), (span, high), (0.0, low)]
            for x, u in ((0.0, (0, -1, 0)), (model.length, (0, 1, 0))):
                origin = (x, span if u[1] < 0 else 0.0, 0.0)
                clip = outline if u[1] > 0 else [(span - a, b) for a, b in reversed(outline)]
                out.append(
                    Surface("Gable sheathing", origin, u, (0, 0, 1), (span, high), "v", clip=clip)
                )
        return out
    raise ValueError("sheathing needs a floor, wall, gable roof or shed roof")

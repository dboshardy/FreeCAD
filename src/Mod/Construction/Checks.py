# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: advisory construction checks (design doc §5.5, §2, §12 R14). No FreeCAD imports.
"""Advisory checks of generated construction against a user-editable rule set.

These checks do not show compliance with any building code. Rule values come
from the user's rule set (an example ships, see Resources/libraries/generic/
rules.json); structural checks use beam mechanics with design values and
loads the user supplies, and report "not checked" without them.
"""

import math

OK, WARNING, NOT_CHECKED, REQUIRED = "ok", "warning", "not checked", "required"
DISCLAIMER = (
    "Advisory only. Not a building code compliance check. Verify against the code "
    "adopted where you build and have the design reviewed by your building official "
    "or a qualified professional."
)


def wall(wall, rules, header_values=None, header_load=0.0):
    """Checks a Framing.Wall. header_values: {"Fb_MPa", "E_MPa"} of the header
    lumber or None; header_load: uniform load on each header in kN/m (= N/mm).
    Returns [(check, status, detail)]."""
    out = []
    t, d = wall.stud

    limit = rules.get("stud_spacing_max_mm")
    if limit:
        status = OK if wall.spacing <= limit + 1e-6 else WARNING
        out.append(("Stud spacing", status, f"{wall.spacing:g} mm, rule max {limit:g} mm"))

    limit = rules.get("stud_slenderness_max")
    if limit:
        # Strong axis only: sheathing is assumed to brace the weak axis.
        ratio = wall.stud_length() / d
        status = OK if ratio <= limit + 1e-9 else WARNING
        out.append(
            (
                "Stud slenderness",
                status,
                f"length/depth {ratio:.1f}, rule max {limit:g} "
                "(weak axis assumed braced by sheathing)",
            )
        )

    limit = rules.get("header_deflection_limit")
    for o in wall.openings:
        name = f"Header over {o.kind} at {o.x:g}"
        if not (header_values and header_load > 0 and limit):
            out.append(
                (
                    name,
                    NOT_CHECKED,
                    "enter the header lumber design values (Fb, E) and the header load",
                )
            )
            continue
        out.append(
            (
                name,
                *header(
                    o.width + t, wall.header, wall.header_plies(), header_values, header_load, limit
                ),
            )
        )
    return out


def header(span, ply, plies, values, load, deflection_limit):
    """Header of `plies` boards side by side: see beam()."""
    return beam(span, ply[0] * plies, ply[1], values, load, deflection_limit)


def beam(span, b, h, values, load, deflection_limit):
    """Simply supported rectangular beam under a uniform load. span: mm; b, h:
    width and depth mm; values: {"Fb_MPa", "E_MPa"}; load: N/mm.
    Returns (status, detail): bending stress and deflection against limits."""
    moment = load * span**2 / 8  # N mm
    stress = moment / (b * h**2 / 6)  # MPa
    deflection = 5 * load * span**4 / (384 * values["E_MPa"] * b * h**3 / 12)  # mm
    allowed = span / deflection_limit
    ok = stress <= values["Fb_MPa"] and deflection <= allowed
    detail = (
        f"bending {stress:.1f} of {values['Fb_MPa']:g} MPa; "
        f"deflection {deflection:.1f} of {allowed:.1f} mm (span/{deflection_limit:g})"
    )
    return (OK if ok else WARNING), detail


def _area_load(name, span, section, spacing, values, load_kpa, limit, how):
    """Beam check of a joist or rafter carrying load_kpa over its spacing."""
    if not (values and load_kpa > 0 and limit):
        return (name, NOT_CHECKED, "enter the lumber design values (Fb, E) and the load")
    load = load_kpa * 1e-3 * spacing  # kPa = 1e-3 N/mm2, times spacing -> N/mm
    status, detail = beam(span, section[0], section[1], values, load, limit)
    return (name, status, f"{detail}; span {span:.0f} mm {how}, {load_kpa:g} kPa")


def floor(floor, rules, values=None, load_kpa=0.0):
    """Checks a Framing.Floor: joists simply supported between the rims (the
    conservative case when no intermediate support is modelled)."""
    t = floor.joist[0]
    return [
        _area_load(
            "Joists",
            floor.width - t,
            floor.joist,
            floor.spacing,
            values,
            load_kpa,
            rules.get("floor_joist_deflection_limit"),
            "rim to rim",
        )
    ]


def roof(roof, rules, values=None, load_kpa=0.0):
    """Checks a Framing.GableRoof. load_kpa is on the horizontal projection."""
    out = []
    span = roof.ridge_face() - roof.seat / 2  # bearing centre to ridge, horizontal
    out.append(
        _area_load(
            "Rafters",
            span,
            roof.rafter,
            roof.spacing,
            values,
            load_kpa,
            rules.get("rafter_deflection_limit"),
            "horizontal projection",
        )
    )
    fraction = rules.get("birdsmouth_max_fraction")
    if fraction:
        # Notch depth measured square to the rafter.
        notch = roof.seat * math.sin(math.radians(roof.pitch))
        status = OK if notch <= fraction * roof.rafter[1] + 1e-6 else WARNING
        out.append(
            (
                "Birdsmouth",
                status,
                f"notch {notch:.0f} mm of rafter depth {roof.rafter[1]:g} mm, "
                f"rule max {fraction:g}",
            )
        )
    status = OK if roof.ridge[1] >= roof.plumb_depth() - 1e-6 else WARNING
    out.append(
        (
            "Ridge board depth",
            status,
            f"{roof.ridge[1]:g} mm against the rafter plumb cut " f"{roof.plumb_depth():.0f} mm",
        )
    )
    if roof.ties:
        out.append(
            ("Rafter ties", OK, "ceiling joists at every rafter pair resist the outward thrust")
        )
    else:
        out.append(
            (
                "Rafter ties",
                WARNING,
                "no ceiling joists or rafter ties: a ridge board does not "
                "hold the rafters; use a structural ridge beam designed for the roof, or add ties",
            )
        )
    return out


def cabinet(cabinet, rules):
    """Checks a Cabinet.Cabinet. Returns [(check, status, detail)]."""
    if cabinet.kind in rules.get("anchor_cabinet_kinds", ()):
        reason = "it hangs on the wall" if cabinet.kind == "wall" else "it can tip over"
        return [
            (
                "Wall anchoring",
                REQUIRED,
                f"fix this {cabinet.kind} cabinet to the wall framing: {reason}; "
                "anchors are in the hardware list",
            )
        ]
    return []

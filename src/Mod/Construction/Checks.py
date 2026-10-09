# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: advisory construction checks (design doc §5.5, §2, §12 R14). No FreeCAD imports.
"""Advisory checks of generated construction against a user-editable rule set.

These checks do not show compliance with any building code. Rule values come
from the user's rule set (an example ships, see Resources/libraries/generic/
rules.json); structural checks use beam mechanics with design values and
loads the user supplies, and report "not checked" without them.
"""

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
    """Simply supported header under a uniform load. span: bearing centres in mm;
    ply: (thickness, depth) mm; values: {"Fb_MPa", "E_MPa"}; load: N/mm.
    Returns (status, detail): bending stress and deflection against limits."""
    b, h = ply[0] * plies, ply[1]
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

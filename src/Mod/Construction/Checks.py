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


def stair(stair, rules):
    """Checks a Framing.Stair. Returns [(check, status, detail)]."""
    out = []
    r, t = stair.riser(), stair.run()

    def limit(name, value, rule_key, low_is_bad, unit="mm"):
        rule = rules.get(rule_key)
        if rule is None:
            return
        ok = value >= rule - 1e-6 if low_is_bad else value <= rule + 1e-6
        word = "min" if low_is_bad else "max"
        out.append(
            (name, OK if ok else WARNING, f"{value:.0f} {unit}, rule {word} {rule:g} {unit}")
        )

    limit("Riser height", r, "stair_riser_max_mm", low_is_bad=False)
    limit("Tread run", t, "stair_tread_min_mm", low_is_bad=True)
    low, high = rules.get("stair_comfort_min_mm"), rules.get("stair_comfort_max_mm")
    if low and high:
        step = 2 * r + t
        ok = low - 1e-6 <= step <= high + 1e-6
        out.append(
            (
                "Comfort (2 x riser + tread)",
                OK if ok else WARNING,
                f"{step:.0f} mm, rule {low:g} to {high:g} mm",
            )
        )
    out.append(("Equal risers", OK, f"{stair.risers()} risers of {r:.1f} mm"))
    limit("Stringer throat", stair.throat(), "stair_throat_min_mm", low_is_bad=True)
    risers = rules.get("handrail_min_risers")
    if risers is not None and stair.risers() >= risers:
        low, high = rules.get("handrail_height_min_mm"), rules.get("handrail_height_max_mm")
        h = stair.handrail_height
        ok = (low is None or h >= low - 1e-6) and (high is None or h <= high + 1e-6)
        out.append(
            (
                "Handrail",
                OK if ok else WARNING,
                f"{h:.0f} mm above the nosings, rule {low:g} to {high:g} mm "
                f"({stair.risers()} risers, rule: from {risers})",
            )
        )
    rise = rules.get("guard_min_rise_mm")
    open_sides = stair.open_sides != "none"
    if rise is not None and stair.total_rise > rise and open_sides:
        height_min = rules.get("guard_height_min_mm")
        gap_max = rules.get("guard_opening_max_mm")
        ok_height = height_min is None or stair.handrail_height >= height_min - 1e-6
        ok_gap = gap_max is None or stair.max_baluster_gap <= gap_max + 1e-6
        out.append(
            (
                "Guards",
                OK if ok_height and ok_gap else WARNING,
                f"height {stair.handrail_height:.0f} mm (rule min {height_min:g}), baluster gap "
                f"up to {stair.max_baluster_gap:.0f} mm (rule max {gap_max:g}) on the open sides",
            )
        )
    out.append(("Headroom", NOT_CHECKED, "depends on the floor opening above the stair"))
    return out


def deck(deck, rules, joist_values=None, beam_values=None, load_kpa=0.0):
    """Checks a Framing.Deck. load_kpa: live + dead load on the deck surface."""
    t = deck.joist[0]
    joist_span = deck.beam_y() - t  # ledger face to beam centre
    out = [
        _area_load(
            "Joists",
            joist_span,
            deck.joist,
            deck.spacing,
            joist_values,
            load_kpa,
            rules.get("floor_joist_deflection_limit"),
            "ledger to beam",
        )
    ]
    # Beam: simply supported between posts, carrying half the joist span plus
    # the cantilever (its tributary width).
    posts = deck.post_centres()
    span = max(b - a for a, b in zip(posts, posts[1:]))
    tributary = joist_span / 2 + deck.cantilever + deck.beam_plies * deck.beam[0] / 2
    section = (deck.beam[0] * deck.beam_plies, deck.beam[1])
    out.append(
        _area_load(
            "Beam",
            span,
            section,
            tributary,
            beam_values,
            load_kpa,
            rules.get("header_deflection_limit"),
            "post to post",
        )
    )
    out.append(
        (
            "Ledger attachment",
            REQUIRED,
            "bolt or through-bolt the ledger to the house framing "
            "to a design for your site, with flashing; fasteners are not generated",
        )
    )
    out.append(
        (
            "Footings",
            REQUIRED,
            f"{len(posts)} posts need footings sized for your soil and "
            "frost depth; not generated",
        )
    )
    rise = rules.get("guard_min_rise_mm")
    if rise is not None and deck.height > rise:
        out.append(
            (
                "Guards",
                REQUIRED,
                f"deck {deck.height:.0f} mm above grade (rule: above "
                f"{rise:g} mm); not generated, add them",
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

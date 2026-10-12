# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: advisory construction checks (design doc §5.5, §2, §12 R14). No FreeCAD imports.
"""Advisory checks of generated construction against a user-editable rule set.

These checks do not show compliance with any building code. Rule values come
from the user's rule set (an example ships, see Resources/libraries/generic/
rules.json); structural checks use beam mechanics with design values and
loads the user supplies, and report "not checked" without them.
"""

import math

import Joinery

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


# Uniform load w on span L: (largest moment / (w L^2), largest deflection /
# (w L^4 / EI), deflection limit measured on this multiple of the span).
SUPPORTS = {
    "simple": (1 / 8, 5 / 384, 1),
    "cantilever": (1 / 2, 1 / 8, 2),  # limit taken on twice the overhang
    "two_spans": (1 / 8, 1 / 185, 1),  # continuous over a middle support
}


def beam(span, b, h, values, load, deflection_limit, support="simple"):
    """Rectangular beam under a uniform load, simply supported, cantilevered
    or continuous over two equal spans (SUPPORTS). span: mm (each span); b, h:
    width and depth mm; values: {"Fb_MPa", "E_MPa"}; load: N/mm.
    Returns (status, detail): bending stress and deflection against limits."""
    m, d, limit_span = SUPPORTS[support]
    moment = m * load * span**2  # N mm
    stress = moment / (b * h**2 / 6)  # MPa
    deflection = d * load * span**4 / (values["E_MPa"] * b * h**3 / 12)  # mm
    allowed = limit_span * span / deflection_limit
    ok = stress <= values["Fb_MPa"] and deflection <= allowed
    detail = (
        f"bending {stress:.1f} of {values['Fb_MPa']:g} MPa; "
        f"deflection {deflection:.1f} of {allowed:.1f} mm (span/{deflection_limit:g})"
    )
    return (OK if ok else WARNING), detail


def _area_load(name, span, section, spacing, values, load_kpa, limit, how, support="simple"):
    """Beam check of a joist or rafter carrying load_kpa over its spacing."""
    if not (values and load_kpa > 0 and limit):
        return (name, NOT_CHECKED, "enter the lumber design values (Fb, E) and the load")
    load = load_kpa * 1e-3 * spacing  # kPa = 1e-3 N/mm2, times spacing -> N/mm
    status, detail = beam(span, section[0], section[1], values, load, limit, support)
    return (name, status, f"{detail}; span {span:.0f} mm {how}, {load_kpa:g} kPa")


def floor(floor, rules, values=None, load_kpa=0.0, beam_values=None):
    """Checks a Framing.Floor: joists simply supported over their longest span
    (rim or beam to the next; conservative where they are butt-joined over
    beams), each beam between its posts carrying half the spans either side.
    A beam without posts bears on a foundation: not checked here."""
    limit = rules.get("floor_joist_deflection_limit")
    supports = floor.supports()
    how = "rim to rim" if not floor.beams else "longest span between supports"
    out = [
        _area_load(
            "Joists", max(floor.spans()), floor.joist, floor.spacing, values, load_kpa, limit, how
        )
    ]
    for n, y in enumerate(supports[1:-1], start=1):
        name = f"Beam at {y:g}"
        if floor.post_height <= 0:
            out.append((name, NOT_CHECKED, "bears on a foundation: check the foundation"))
            continue
        posts = floor.post_centres()
        span = max(b - a for a, b in zip(posts, posts[1:]))
        tributary = (supports[n + 1] - supports[n - 1]) / 2
        section = (floor.beam[0] * floor.beam_plies, floor.beam[1])
        out.append(
            _area_load(name, span, section, tributary, beam_values, load_kpa, limit, "post to post")
        )
    if floor.post_height > 0 and floor.beams:
        count = len(floor.beams) * len(floor.post_centres())
        out.append(
            (
                "Footings",
                REQUIRED,
                f"{count} posts need footings sized for your soil and frost depth",
            )
        )
    return out


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


def shed_roof(roof, rules, values=None, load_kpa=0.0, framed=False):
    """Checks a Framing.ShedRoof: rafters simply supported between the walls'
    bearing centres (horizontal projection), birdsmouth depth."""
    out = [
        _area_load(
            "Rafters",
            roof.span - roof.seat,
            roof.rafter,
            roof.spacing,
            values,
            load_kpa,
            rules.get("rafter_deflection_limit"),
            "horizontal projection",
        )
    ]
    fraction = rules.get("birdsmouth_max_fraction")
    if fraction:
        notch = roof.seat * math.sin(math.radians(roof.pitch))
        status = OK if notch <= fraction * roof.rafter[1] + 1e-6 else WARNING
        out.append(
            (
                "Birdsmouth",
                status,
                f"notch {notch:.0f} mm of rafter depth {roof.rafter[1]:g} mm, rule max {fraction:g}",
            )
        )
    if framed:
        out.append(("High wall", OK, f"framed {roof.rise():.0f} mm taller than the low wall"))
    else:
        out.append(
            (
                "High wall",
                REQUIRED,
                f"frame the high wall {roof.rise():.0f} mm taller than the low wall; the rafters "
                "bear on both walls and need no ties",
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


def landing_stair(model, rules):
    """Checks a Framing.LandingStair: the stair checks for its equal risers,
    then the landing's depth (at least the stair width and the rule set's
    landing_min_depth_mm) and its guards."""
    out = stair(model.stair, rules)
    need = max(model.stair.width, rules.get("landing_min_depth_mm", 0))
    depth = model.depth()
    out.append(
        (
            "Landing depth",
            OK if depth >= need - 1e-6 else WARNING,
            f"{depth:.0f} mm, at least the stair width {model.stair.width:g} mm"
            + (
                f" and the rule's {rules['landing_min_depth_mm']:g} mm"
                if "landing_min_depth_mm" in rules
                else ""
            ),
        )
    )
    rise = rules.get("guard_min_rise_mm")
    if rise is not None and model.landing_top() > rise:
        sides = model.stair.open_sides
        status = REQUIRED if sides != "none" else OK
        detail = (
            f"landing {model.landing_top():.0f} mm up: guards generated on the open sides ({sides})"
            if sides != "none"
            else "landing between walls"
        )
        out.append(("Landing guards", status, detail))
    return out


def deck(deck, rules, joist_values=None, beam_values=None, load_kpa=0.0):
    """Checks a Framing.Deck. load_kpa: live + dead load on the deck surface."""
    joist_span = deck.joist_span()
    out = [
        _area_load(
            "Joists",
            joist_span,
            deck.joist,
            deck.spacing,
            joist_values,
            load_kpa,
            rules.get("floor_joist_deflection_limit"),
            "ledger to beam" if deck.attached else "beam to beam",
        )
    ]
    if deck.cantilever > 0:
        out.append(
            _area_load(
                "Joist cantilever",
                deck.cantilever + deck.beam_plies * deck.beam[0] / 2,
                deck.joist,
                deck.spacing,
                joist_values,
                load_kpa,
                rules.get("floor_joist_deflection_limit"),
                "past the beam's centre",
                "cantilever",
            )
        )
    # Beam: simply supported between posts, carrying half the joist span plus
    # the cantilever (its tributary width; the same for both beams of a
    # freestanding deck, which is symmetric).
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
    if deck.attached:
        out.append(
            (
                "Ledger attachment",
                REQUIRED,
                "bolt or through-bolt the ledger to the house framing "
                "to a design for your site, with flashing; fasteners are not generated",
            )
        )
    side, depth = deck.footing
    out.append(
        (
            "Footings",
            REQUIRED,
            f"{deck.posts()} posts need footings sized for your soil and frost depth "
            f"(counted at {side:g} x {side:g} x {depth:g} mm: {deck.concrete_m3():.2f} m³ of "
            "concrete in the cut list); not drawn",
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


def build(parts, result, rules, items):
    """Checks a woodworking build. parts: [(stock id, Part)] after joinery;
    result: its Joinery.Result; items: the library. Returns [(check, status,
    detail)]."""
    out = []
    boxes = [p for _, p in parts]
    if build_anchored(boxes, rules):
        height = _height(boxes)
        out.append(
            (
                "Wall anchoring",
                REQUIRED,
                f"fix to the wall: {height:g} mm tall furniture can tip over (rule: over "
                f"{rules['anchor_furniture_height_mm']:g} mm); anchors are in the hardware list",
            )
        )
    limit = rules.get("mortise_wall_min_mm")
    for i, pocket in result.pockets:
        if limit is None or not pocket.name.endswith("mortise"):
            continue
        a = boxes[i]
        walls = sorted(
            w for n in range(3) for w in (pocket.lo(n) - a.lo(n), a.hi(n) - pocket.hi(n))
        )
        thinnest = walls[1]  # walls[0] is the open face the tenon enters by
        status = OK if thinnest >= limit - 1e-6 else WARNING
        out.append((f"Mortise wall, {a.name}", status, f"{thinnest:.1f} mm, rule min {limit:g} mm"))
    limit = rules.get("hole_wall_min_mm")
    thin = set()
    for i, hole in result.pockets if limit is not None else ():
        if hole.role != "hole" or i in thin:
            continue
        a, k = boxes[i], "xyz".index(hole.grain)
        walls = [
            w for n in range(3) if n != k for w in (hole.lo(n) - a.lo(n), a.hi(n) - hole.hi(n))
        ]
        breaks = hole.lo(k) < a.lo(k) - 1e-6 or hole.hi(k) > a.hi(k) + 1e-6
        if min(walls) < limit - 1e-6 or breaks:
            thin.add(i)
            detail = (
                f"a hole leaves {min(walls):.1f} mm (rule min {limit:g} mm)"
                if not breaks
                else "a hole is deeper than the part"
            )
            out.append((f"Hole wall, {a.name}", WARNING, detail + ": change the joint or stock"))
    by_part = {}
    for i, pocket in result.pockets:
        by_part.setdefault(i, []).append(pocket)
    for i, pockets in sorted(by_part.items()):
        for n, a in enumerate(pockets):
            if any(Joinery.overlap(a, b) for b in pockets[n + 1 :]):
                out.append(
                    (
                        f"Joints meet inside {boxes[i].name}",
                        WARNING,
                        "two cuts overlap: shorten or miter the tenons, or offset them",
                    )
                )
                break
    limit = rules.get("wood_movement_width_mm")
    moving = set()
    glued = _glue_ups(boxes, result.joints)
    for i, j, rule in result.joints if limit else ():
        glue = rule.kind == "fastened" and rule.operation == "glue" and not rule.fastener
        fixed = rule.kind == "fastened" and (rule.fastener or glue)
        if not fixed or rule.allows_movement or (glue and boxes[i].grain == boxes[j].grain):
            continue  # glued with the grain (an edge-to-edge glue-up) moves as one
        for index in (i, j):
            stock, part = parts[index]
            item = items.get(stock, {})
            solid = (
                item.get("category") == "dimensional_lumber" or item.get("material") == "solid wood"
            )
            width = _across_grain(part, [boxes[n] for n in glued[index]])
            if solid and width > limit and index not in moving:
                moving |= glued[index]  # once per glue-up, however many joints fix it
                n = len(glued[index])
                name = part.name + (f" (glue-up of {n})" if n > 1 else "")
                out.append(
                    (
                        f"Wood movement, {name}",
                        WARNING,
                        f"solid wood {width:g} mm wide fixed rigidly across its grain can split "
                        f"(rule: over {limit:g} mm); use tabletop fasteners or slotted holes",
                    )
                )
    return out


def build_anchored(boxes, rules):
    """True when a build (its Parts) must be fixed to the wall: taller than
    the rule set's anchor_furniture_height_mm and more than
    anchor_furniture_slenderness times its narrower footprint side (a
    bookcase, not a table)."""
    limit = rules.get("anchor_furniture_height_mm")
    if not (limit and boxes):
        return False
    height = _height(boxes)
    footprint = min(max(b.hi(n) for b in boxes) - min(b.lo(n) for b in boxes) for n in (0, 1))
    slender = height / footprint > rules.get("anchor_furniture_slenderness", 0) + 1e-9
    return height > limit + 1e-6 and slender


def _glue_ups(boxes, joints):
    """Part index -> indices of the parts glued edge to edge to it with the
    grain (itself included): glue-ups that move as one board."""
    group = {i: {i} for i in range(len(boxes))}
    for i, j, rule in joints:
        glue = rule.kind == "fastened" and rule.operation == "glue" and not rule.fastener
        edge_to_edge = (
            Joinery.meets(boxes[i], boxes[j])
            == Joinery.meets(boxes[j], boxes[i])
            == ("edge_to_face")
        )
        if glue and edge_to_edge and boxes[i].grain == boxes[j].grain and group[i] is not group[j]:
            merged = group[i] | group[j]
            for n in merged:
                group[n] = merged
    return group


def _across_grain(part, glued):
    """Width across the grain of a part and the parts glued up with it."""
    thick = min(range(3), key=lambda n: part.size[n])
    grain = "xyz".index(part.grain) if part.grain else max(range(3), key=lambda n: part.size[n])
    w = next(n for n in range(3) if n not in (thick, grain))
    return max(b.hi(w) for b in glued) - min(b.lo(w) for b in glued)


def _height(boxes):
    return max(b.hi(2) for b in boxes) - min(b.lo(2) for b in boxes)

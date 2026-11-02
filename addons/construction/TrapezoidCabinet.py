# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: trapezoidal cabinet (design doc §5.4): one slanted front, shaker or slab
# door, an interior of trays and shelves. Part of the Construction cut list like
# the other cabinets.
"""A parametric trapezoidal cabinet.

Create it with the Trapezoid Cabinet command, or in the Python console:
    import TrapezoidCabinet
    TrapezoidCabinet.make()
Change its properties in the Property view (Data tab); type inch values with a
unit, e.g. 23 in or 1' 11".

Everything is a property: the outside sizes, the door (style, hinge side, frame
and groove sizes), the materials, the clearances, and the Interior: a list
with one line per tray or shelf, each with its own height above the floor and
its own wall height, slide length, setback or material (see Interior.py).

The cabinet takes part in the Cut List, Export Cut List (CSV), part labels and
checks like the other cabinets: parts by material (sheet goods from the
library), sheet layout, hinges, slides, shelf pins, screws and wall anchors.
Non-rectangular parts are listed at their rectangular blank size with the final
shape under Operations.

Plan view: the back edge and the two sides are square to each other; the front
is the slanted fourth edge. Trays run on side-mount slides with their fronts
parallel to the door.

Axes: x = left to right, y = front to back, z = up. The back-left corner
(outside) is on the object's origin: the back face is on y = 0 and the cabinet
is at y < 0. Move it with the Placement property.
"""

import math

import FreeCAD as App
import Part

import Checks
import ConstructionObjects as CO
import CutList
import Interior
import Library
import Parts as CParts

V = App.Vector
IN = 25.4

MATERIALS = {
    # property: (default library id, tip); thicknesses come from the library
    "CarcassMaterial": ("sheet.us.plywood.3-4", "Sides, bottom, top, door (or door frame); default for shelves"),
    "BackMaterial": ("sheet.us.mdf.1-4", "Back panel and shaker door panel (also the groove width)"),
    "TrayMaterial": ("sheet.us.plywood.1-2", "Default for tray walls and bottoms"),
}

PROPERTIES = [
    # (type, name, group, tooltip, default)
    ("App::PropertyLength", "BackWidth", "Carcass", "Back edge, outside", 23 * IN),
    ("App::PropertyLength", "LeftDepth", "Carcass", "Left side, outside, back face to front corner", 16 * IN),
    ("App::PropertyLength", "RightDepth", "Carcass", "Right side, outside, back face to front corner", 30 * IN),
    ("App::PropertyLength", "Height", "Carcass", "Floor to top of the carcass", 81.5 * IN),
    ("App::PropertyEnumeration", "DoorStyle", "Door", "shaker: stiles, rails and a grooved panel; slab: one panel", None),
    ("App::PropertyEnumeration", "HingeSide", "Door", "Side the door is hinged on", None),
    ("App::PropertyLength", "DoorGap", "Door", "Total gap around the door, half each side", 0.125 * IN),
    ("App::PropertyLength", "FrameWidth", "Door", "Shaker stile and rail width", 2.25 * IN),
    ("App::PropertyLength", "GrooveDepth", "Door", "Panel groove depth; also the rail stub tenon length", 0.375 * IN),
    ("App::PropertyLength", "PanelPlay", "Door", "Panel shorter than the groove bottom, per edge", 0.0625 * IN),
    ("App::PropertyAngle", "DoorOpenAngle", "Door", "Show the door opened by this angle, for checking clearance", 0.0),
    ("App::PropertyStringList", "Interior", "Interior",
     "One line per tray or shelf, any order, e.g. 'tray 4 in, walls 8 in', 'adjustable shelf 50 in', "
     "'shelf 60 in, setback 2 in'. Height = underside above the floor. Tray keys: walls, slide, "
     "material; shelf keys: setback, material", None),
    ("App::PropertyLength", "TrayHeight", "Interior", "Tray wall height when a line gives no 'walls'", 4 * IN),
    ("App::PropertyLength", "ShelfSetback", "Interior", "Shelf front edge back from the front when a line gives no 'setback'", 1 * IN),
    ("App::PropertyLength", "ShelfPinClearance", "Interior", "Adjustable shelves: gap at each end", 1.0),
    ("App::PropertyLength", "SlideClearance", "Interior", "Per side, from the slide maker's data", 0.5 * IN),
    ("App::PropertyLength", "SlideStep", "Interior", "Slides are sold in steps of this length", 2 * IN),
    ("App::PropertyLength", "RearClearance", "Interior", "Behind the trays, in front of the back panel", 0.5 * IN),
    ("App::PropertyLength", "DoorClearance", "Interior", "Door's inside face to the tray fronts (hinge arms)", 1 * IN),
    ("App::PropertyPercent", "TrayExtension", "Interior", "Show the trays pulled out this far, for checking", 0),
    ("App::PropertyLength", "SlideLength", "Result", "Longest slide that fits (a line's 'slide' may be shorter)", 0.0),
    ("App::PropertyStringList", "Parts", "Result", "Every part with its size", []),
]
DEFAULT_TRAYS = (4 * IN, 16 * IN, 28 * IN, 40 * IN)
# Properties of earlier versions: thicknesses now come from the materials, and the
# trays and shelves from Interior (migrated in setProperties).
OBSOLETE = ("Thickness", "BackThickness", "TrayWall", "TrayBottomThickness", "GrooveWidth",
            "TrayCount", "FirstTrayHeight", "TraySpacing", "BottomTrayHeight", "Shelves")


def _box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def _prism(points, z0, z1):
    pts = [V(x, y, z0) for x, y in points]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(V(0, 0, z1 - z0))


def _length(units, mm, denominator=16):
    """Text of a length in the cut list's units: 584.2 mm, or 23", 23/32"."""
    if units == "mm":
        return f"{mm:.1f} mm"
    return CutList.format_length(mm, "in", denominator)


def hinge_count(door_height):
    """Hinges for a door height, from the library's concealed-hinge table."""
    joint = CO.library_item("joint.concealed_hinge")
    table, extra = sorted(joint["count_table"]), joint.get("extra_every", 400.0)
    for max_len, count in table:
        if door_height <= max_len:
            return count
    last_len, last_count = table[-1]
    return last_count + math.ceil((door_height - last_len) / extra)


def fastener_count(joint_id, length):
    """Fasteners of a library joint along a contact of this length (as Joinery counts them)."""
    rule = CO.library_item(joint_id)
    if not rule.get("spacing"):
        return rule.get("per_joint", 1)
    usable = max(0.0, length - 2 * rule.get("edge", 0.0))
    return max(2, math.ceil(usable / rule["spacing"] - 1e-6) + 1) if usable > 1e-6 else 1


def migrated_interior(obj):
    """Interior lines for an object saved before Interior existed."""
    def old(name, default):
        return getattr(obj, name) if name in obj.PropertiesList else default

    def value(q):
        return q.Value if hasattr(q, "Value") else float(q)

    count = old("TrayCount", len(DEFAULT_TRAYS))
    first = value(old("FirstTrayHeight", DEFAULT_TRAYS[0]))
    spacing = value(old("TraySpacing", DEFAULT_TRAYS[1] - DEFAULT_TRAYS[0]))
    bottom_walls = value(old("BottomTrayHeight", 0.0))
    lines = []
    for i in range(count):
        line = f"tray {first / IN + i * spacing / IN:g} in"
        if i == 0 and bottom_walls > 0:
            line += f", walls {bottom_walls / IN:g} in"
        lines.append(line)
    shelves = old("Shelves", 0)
    if shelves:
        t = CO.sheet_thickness(obj.CarcassMaterial)
        walls = value(old("TrayHeight", 4 * IN))
        low = (first + (count - 1) * spacing + walls) if count else 0.0
        height = obj.Height.Value
        for i in range(shelves):
            z = low + t + (i + 1) * (height - 2 * t - low) / (shelves + 1) - t / 2
            lines.append(f"shelf {z / IN:.3f} in")
    return lines


class TrapezoidCabinet(CO.CabinetFeature):  # the cut list collects CabinetFeatures
    IFC_TYPE = "Furniture"

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        """Adds missing properties; migrates documents saved with an earlier version."""
        added = set()
        for kind, name, group, tip, default in PROPERTIES:
            if name in obj.PropertiesList:
                continue
            added.add(name)
            obj.addProperty(kind, name, group, tip)
            if default is not None:
                setattr(obj, name, default)
        if not obj.getEnumerationsOfProperty("DoorStyle"):
            obj.DoorStyle = ["shaker", "slab"]
        if not obj.getEnumerationsOfProperty("HingeSide"):
            obj.HingeSide = ["left", "right"]
        for prop, (default, tip) in MATERIALS.items():
            CO.add_library_choice(obj, prop, Library.SHEET_GOODS, default, "Materials", tip)
        CO.add_ifc_type(obj, self)
        if "Interior" in added:  # new object, or saved before Interior existed
            obj.Interior = migrated_interior(obj)
        for name in OBSOLETE:
            if name in obj.PropertiesList:
                obj.removeProperty(name)
        obj.setEditorMode("SlideLength", 1)  # read-only
        obj.setEditorMode("Parts", 1)

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

    def dumps(self):
        return None

    def loads(self, state):
        return None

    # ---- interface the cut list, part labels, drawings and checks use

    def parts(self, obj):
        """[(material id, Part)]: blank sizes, final shapes under operations."""
        out = []
        for e in model(obj)["entries"]:
            bb = e["shape"].BoundBox
            part = CParts.Part(e["name"], e["role"], e["size"], (bb.XMin, bb.YMin, bb.ZMin),
                               e["grain"], e["ops"])
            out.append((e["material"], part))
        return out

    def solids(self, obj):
        """Solids in the order of parts()."""
        return [e["shape"] for e in model(obj)["entries"]]

    def fasteners(self, obj, schedule):
        return model(obj)["fasteners"]

    def kind(self, obj):
        return "tall" if obj.Height.Value > 1200 else "base"

    def anchored(self, obj, rules):
        return 1 if self.kind(obj) in rules.get("anchor_cabinet_kinds", ()) else 0

    def checks(self, obj, rules):
        out = []
        if self.anchored(obj, rules):
            out.append(("Wall anchoring", Checks.REQUIRED,
                        "fix this tall cabinet to the wall framing: it can tip over; "
                        "anchors are in the hardware list"))
        geo = geometry(obj)
        out.append(("Hinges", Checks.WARNING,
                    f"the hinge side meets the door at {geo['hinge_angle']:.1f} deg: "
                    "use angled hinges or mounting plates for that angle"))
        return out

    def cabinets(self, obj):
        return []

    def execute(self, obj):
        m = model(obj)
        placement = obj.Placement
        obj.Shape = Part.makeCompound([e["shape"] for e in m["entries"]])
        obj.Placement = placement
        obj.SlideLength = m["geo"]["slide"]
        obj.Parts = [f"{e['name']} [{e['material']}]: {e['text']}" for e in m["entries"]] + m["notes"]


def geometry(obj):
    """Derived sizes shared by the shapes, the cut list and the hardware."""
    W, DL, DR, H = obj.BackWidth.Value, obj.LeftDepth.Value, obj.RightDepth.Value, obj.Height.Value
    T, TB = CO.sheet_thickness(obj.CarcassMaterial), CO.sheet_thickness(obj.BackMaterial)
    if min(W, DL, DR, H) <= 0 or W <= 2 * T:
        raise ValueError("sizes must be positive and BackWidth more than 2 x the carcass thickness")
    y_fl, y_fr, y_bi = -DL, -DR, -TB
    dx, dy = W, y_fr - y_fl
    front_len = math.hypot(dx, dy)
    theta = math.degrees(math.atan2(dy, dx))
    slope = dy / dx

    def front_y(x, inset=0.0):
        """y of the front line at x, moved towards the back by `inset`."""
        return y_fl + slope * x + inset * front_len / dx

    x_l = T + obj.SlideClearance.Value
    x_r = W - T - obj.SlideClearance.Value
    y_back = y_bi - obj.RearClearance.Value
    room = y_back - front_y(x_l, obj.DoorClearance.Value)  # tray depth available at the left
    step = obj.SlideStep.Value
    slide = math.floor(room / step + 1e-9) * step if step > 0 else room
    gap = obj.DoorGap.Value
    return {
        "W": W, "DL": DL, "DR": DR, "H": H, "T": T, "TB": TB, "y_fl": y_fl, "y_fr": y_fr, "y_bi": y_bi,
        "dx": dx, "front_len": front_len, "theta": theta, "slope": slope, "front_y": front_y,
        "x_l": x_l, "x_r": x_r, "y_back": y_back, "room": room, "slide": max(slide, 0.0),
        "door_w": front_len - gap, "door_h": H - gap, "gap": gap,
        "hinge_angle": 90 - theta if obj.HingeSide == "left" else 90 + theta,
    }


def model(obj):
    """dict(entries, fasteners, notes, geo). entries: every part as
    dict(name, role, material id, size, grain, ops, text, shape); size is the
    rectangular blank (dx, dy, dz) with the grain along `grain`."""
    g = geometry(obj)
    units = CO.cut_list_units(obj.Document)

    def L(mm, denominator=16):
        return _length(units, mm, denominator)

    W, H, T, TB = g["W"], g["H"], g["T"], g["TB"]
    y_fl, y_fr, y_bi, front_y, slope = g["y_fl"], g["y_fr"], g["y_bi"], g["front_y"], g["slope"]
    front_len, dx, theta = g["front_len"], g["dx"], g["theta"]
    big = 10 * max(W, g["DL"], g["DR"], H)
    carcass_m, back_m = obj.CarcassMaterial, obj.BackMaterial
    entries, fasteners, notes = [], {}, []

    def add(name, role, material, size, grain, ops, text, shape):
        entries.append(dict(name=name, role=role, material=material, size=size, grain=grain,
                            ops=tuple(ops), text=text, shape=shape))

    def fasten(hardware_id, count):
        fasteners[hardware_id] = fasteners.get(hardware_id, 0) + count

    def taper_text(left, right):
        return f"taper {L(left)} deep at left to {L(right)} at right"

    # ---- carcass: the plan inside the back, extruded, cut to each part's slab
    carcass = _prism([(0, y_fl), (W, y_fr), (W, y_bi), (0, y_bi)], 0, H)

    def slab(x0, x1, z0, z1):
        return carcass.common(_box(x0, x1, -big, big, z0, z1))

    bevel = f"bevel front edge {abs(theta):.1f} deg"
    for name, x0, depth in (("Left side", 0, g["DL"] - TB), ("Right side", W - T, g["DR"] - TB)):
        add(name, "carcass", carcass_m, (T, depth, H), "z", [bevel],
            f"{L(depth)} x {L(H)} x {L(T, 32)}, {bevel}", slab(x0, x0 + T, 0, H))
    d_left, d_right = y_bi - front_y(T), y_bi - front_y(W - T)
    taper = taper_text(d_left, d_right)
    flat_text = f"{L(W - 2 * T)} x {L(d_right)} blank, {taper}, {L(T, 32)} thick"
    add("Bottom", "carcass", carcass_m, (W - 2 * T, d_right, T), "x", [taper], flat_text, slab(T, W - T, 0, T))
    add("Top", "carcass", carcass_m, (W - 2 * T, d_right, T), "x", [taper], flat_text,
        slab(T, W - T, H - T, H))
    add("Back", "back", back_m, (W, TB, H), "z", [], f"{L(W)} x {L(H)} x {L(TB, 32)}",
        _box(0, W, y_bi, 0, 0, H))

    # ---- interior: trays and shelves, each with its own sizes
    items = Interior.parse(obj.Interior)
    walls_default = obj.TrayHeight.Value

    def item_material(item):
        default = obj.TrayMaterial if item.kind == "tray" else carcass_m
        material = item.material or default
        try:
            CO.library_item(material)
        except ValueError as e:
            raise ValueError(f"{item.label()}: {e}") from None
        return material

    Interior.check_fit(items, T, H - T, {"walls": walls_default,
                                         "thickness": lambda m: CO.sheet_thickness(m or carcass_m)}, L)
    x_l, x_r, y_back = g["x_l"], g["x_r"], g["y_back"]
    pull_share = obj.TrayExtension / 100.0
    numbers = {"tray": 0, "shelf": 0}
    for item in items:
        material = item_material(item)
        t = CO.sheet_thickness(material)
        z0 = item.height
        if item.kind == "tray":
            numbers["tray"] += 1
            label = f"Tray {numbers['tray']}"
            slide = g["slide"] if item.slide is None else item.slide
            if slide > g["room"] + 1e-6:
                raise ValueError(f"{item.label()}: slide {L(slide)} does not fit; "
                                 f"at most {L(g['room'])} (SlideLength {L(g['slide'])})")
            if slide <= 2 * t or x_r - x_l <= 2 * t:
                raise ValueError(f"{item.label()}: no room for a tray")
            th = walls_default if item.walls is None else item.walls
            z1 = z0 + th
            y_tfl = y_back - slide
            y_tfr = y_tfl + slope * (x_r - x_l)
            plan = [(x_l, y_tfl), (x_r, y_tfr), (x_r, y_back), (x_l, y_back)]
            xm0, xm1, split = x_l + t, x_r - t, y_back - t
            inset = t * front_len / dx  # front wall thickness measured along y
            inner = [(xm0, y_tfl + inset + slope * t), (xm1, y_tfr + inset - slope * t), (xm1, split), (xm0, split)]
            ring = _prism(plan, z0, z1).cut(_prism(inner, z0, z1))
            front_wall = (xm1 - xm0) * front_len / dx
            ends = f"ends cut {abs(theta):.1f} deg"
            walls = [
                ("left wall", (t, slide, th), "y", [], _box(x_l, xm0, -big, big, z0, z1)),
                ("right wall", (t, y_back - y_tfr, th), "y", [], _box(xm1, x_r, -big, big, z0, z1)),
                ("back wall", (xm1 - xm0, t, th), "x", [], _box(xm0, xm1, split, big, z0, z1)),
                ("front wall", (front_wall, t, th), "x", [ends], _box(xm0, xm1, -big, split, z0, z1)),
            ]
            pull = V(0, -pull_share * slide, 0)
            for name, size, grain, ops, cutter in walls:
                shape = ring.common(cutter)
                shape.translate(pull)
                length = size["xyz".index(grain)]  # along the grain
                text = f"{L(length)} x {L(th)} x {L(t, 32)}" + (f", {ops[0]}" if ops else "")
                add(f"{label} {name}", "drawer_box", material, size, grain, ops, text, shape)
            bl, br = split - inner[0][1], split - inner[1][1]
            tray_taper = taper_text(bl, br)
            bottom = _prism(inner, z0, z0 + t)
            bottom.translate(pull)
            add(f"{label} bottom", "drawer_bottom", material, (xm1 - xm0, br, t), "y", [tray_taper],
                f"{L(xm1 - xm0)} x {L(br)} blank, {tray_taper}, {L(t, 32)} thick", bottom)
            fasten(f"hardware.drawer_slide@{round(slide, 1):g}", 1)
        else:
            numbers["shelf"] += 1
            label = f"Shelf {numbers['shelf']}"
            adjustable = item.kind == "adjustable shelf"
            setback = obj.ShelfSetback.Value if item.setback is None else item.setback
            clear = obj.ShelfPinClearance.Value if adjustable else 0.0
            sx0, sx1 = T + clear, W - T - clear
            yl, yr = front_y(sx0, setback), front_y(sx1, setback)
            if y_bi - yl <= 0:
                raise ValueError(f"{item.label()}: setback {L(setback)} leaves no shelf at the left")
            shape = _prism([(sx0, yl), (sx1, yr), (sx1, y_bi), (sx0, y_bi)], z0, z0 + t)
            left_d, right_d = y_bi - yl, y_bi - yr
            shelf_taper = taper_text(left_d, right_d)
            ops = [shelf_taper]
            if adjustable:
                ops.append("rests on 4 shelf pins")
                fasten("hardware.shelf_pin", 4)
            else:
                screws = fastener_count("joint.confirmat", left_d) + fastener_count("joint.confirmat", right_d)
                ops.append(f"{screws} confirmat holes")
                fasten("hardware.confirmat_7x50", screws)
            add(label, "shelf", material, (sx1 - sx0, right_d, t), "x", ops,
                f"{L(sx1 - sx0)} x {L(right_d)} blank, {shelf_taper}, {L(t, 32)} thick"
                + (", adjustable" if adjustable else ", fixed"), shape)
    if numbers["tray"]:
        notes.append(f"Slides: {numbers['tray']} pairs (longest that fits: {L(g['slide'])})")

    # ---- door, built flat (x = width, y = thickness, z = height), then placed
    dw, dh, gap = g["door_w"], g["door_h"], g["gap"]
    hinge_op = f"hinge side meets the cabinet at {g['hinge_angle']:.1f} deg"
    door = []
    if obj.DoorStyle == "slab":
        door.append(("Door", "door", carcass_m, (dw, T, dh), "z", [hinge_op],
                     f"{L(dw)} x {L(dh)} x {L(T, 32)}", _box(0, dw, 0, T, 0, dh)))
    else:
        s, gd, play = obj.FrameWidth.Value, obj.GrooveDepth.Value, obj.PanelPlay.Value
        gw = TB  # the groove takes the panel
        if dw <= 2 * s or dh <= 2 * s or gd >= s or gw >= T:
            raise ValueError("shaker frame does not fit the door")
        y0, y1 = (T - gw) / 2, (T + gw) / 2  # groove, centred in the thickness

        def groove(x0, x1, z0, z1):
            return _box(x0, x1, y0, y1, z0, z1)

        def rail(z0, z1, gz0, gz1):
            body = _box(s, dw - s, 0, T, z0, z1)
            tenons = groove(s - gd, s, z0, z1).fuse(groove(dw - s, dw - s + gd, z0, z1))
            return body.fuse(tenons).cut(groove(s - gd, dw - s + gd, gz0, gz1))

        p = gd - play
        groove_op = f"groove {L(gw, 32)} x {L(gd)} deep"
        rail_len = dw - 2 * s + 2 * gd
        tenon_op = f"stub tenons {L(gd)} long each end"
        pw, ph = dw - 2 * s + 2 * p, dh - 2 * s + 2 * p
        stile_text = f"{L(s)} x {L(dh)} x {L(T, 32)}, {groove_op}"
        rail_text = f"{L(rail_len)} x {L(s)} x {L(T, 32)}, {groove_op}, {tenon_op}"
        door += [
            ("Door stile left", "door_frame", carcass_m, (s, T, dh), "z",
             [groove_op] + ([hinge_op] if obj.HingeSide == "left" else []), stile_text,
             _box(0, s, 0, T, 0, dh).cut(groove(s - gd, s, 0, dh))),
            ("Door stile right", "door_frame", carcass_m, (s, T, dh), "z",
             [groove_op] + ([hinge_op] if obj.HingeSide == "right" else []), stile_text,
             _box(dw - s, dw, 0, T, 0, dh).cut(groove(dw - s, dw - s + gd, 0, dh))),
            ("Door rail", "door_frame", carcass_m, (rail_len, T, s), "x", [groove_op, tenon_op],
             rail_text, rail(0, s, s - gd, s)),
            ("Door rail", "door_frame", carcass_m, (rail_len, T, s), "x", [groove_op, tenon_op],
             rail_text, rail(dh - s, dh, dh - s, dh - s + gd)),
            ("Door panel", "door_panel", back_m, (pw, gw, ph), "z", [],
             f"{L(pw)} x {L(ph)} x {L(gw, 32)}", groove(s - p, dw - s + p, s - p, dh - s + p)),
        ]
    d = V(dx / front_len, (y_fr - y_fl) / front_len, 0)  # along the front, left to right
    n = V((y_fr - y_fl) / front_len, -dx / front_len, 0)  # outward normal of the front
    left_corner = V(0, y_fl, 0)
    origin = left_corner + n * T + d * (gap / 2) + V(0, 0, gap / 2)
    if obj.HingeSide == "left":
        hinge, swing = left_corner + n * T + d * (gap / 2), -1
    else:
        hinge, swing = left_corner + n * T + d * (front_len - gap / 2), 1
    opened = obj.DoorOpenAngle.Value
    for name, role, material, size, grain, ops, text, shape in door:
        shape.rotate(V(0, 0, 0), V(0, 0, 1), theta)  # flat x -> along the front, flat y -> inward
        shape.translate(origin)
        if opened:
            shape.rotate(hinge, V(0, 0, 1), swing * opened)  # opens outward
        add(name, role, material, size, grain, ops, text, shape)
    hinges = hinge_count(dh)
    fasten("hardware.hinge", hinges)
    notes.append(f"Hinges: {hinges}, hinged {obj.HingeSide}; hinge side meets the door at "
                 f"{g['hinge_angle']:.1f} deg (use angled hinges)")
    return {"entries": entries, "fasteners": fasteners, "notes": notes, "geo": g}


def make(name="TrapezoidCabinet", doc=None):
    doc = doc or App.ActiveDocument or App.newDocument("Cabinet")
    obj = doc.addObject("Part::FeaturePython", name)
    TrapezoidCabinet(obj)
    if App.GuiUp:
        obj.ViewObject.Proxy = 0  # default Part view provider
    doc.recompute()
    return obj

# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: trapezoidal cabinet (design doc §5.4): one slanted front, shaker or slab
# door, pull-out trays. Part of the Construction cut list like the other cabinets.
"""A parametric trapezoidal cabinet.

Create it with the Trapezoid Cabinet command, or in the Python console:
    import TrapezoidCabinet
    TrapezoidCabinet.make()
Change its properties in the Property view (Data tab); type inch values with a
unit, e.g. 23 in or 1' 11".

The cabinet takes part in the Cut List, Export Cut List (CSV), part labels and
checks like the other cabinets: parts by material (sheet goods from the
library), sheet layout, hinges, slides and wall anchors. Non-rectangular parts
are listed at their rectangular blank size with the final shape under
Operations.

Plan view: the back edge and the two sides are square to each other; the front
is the slanted fourth edge. One full-overlay door (shaker or slab) on the front.
Pull-out trays on side-mount slides, their fronts parallel to the door.

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
import Library
import Parts as CParts

V = App.Vector
IN = 25.4

MATERIALS = {
    # property: (default library id, tip); thicknesses come from the library
    "CarcassMaterial": ("sheet.us.plywood.3-4", "Sides, bottom, top, shelves, door (or door frame)"),
    "BackMaterial": ("sheet.us.mdf.1-4", "Back panel and shaker door panel (also the groove width)"),
    "TrayMaterial": ("sheet.us.plywood.1-2", "Tray walls and bottoms"),
}

PROPERTIES = [
    # (type, name, group, tooltip, default)
    ("App::PropertyLength", "BackWidth", "Carcass", "Back edge, outside", 23 * IN),
    ("App::PropertyLength", "LeftDepth", "Carcass", "Left side, outside, back face to front corner", 16 * IN),
    ("App::PropertyLength", "RightDepth", "Carcass", "Right side, outside, back face to front corner", 30 * IN),
    ("App::PropertyLength", "Height", "Carcass", "Floor to top of the carcass", 81.5 * IN),
    ("App::PropertyInteger", "Shelves", "Carcass", "Fixed shelves, evenly spaced above the top tray", 0),
    ("App::PropertyEnumeration", "DoorStyle", "Door", "shaker: stiles, rails and a grooved panel; slab: one panel", None),
    ("App::PropertyEnumeration", "HingeSide", "Door", "Side the door is hinged on", None),
    ("App::PropertyLength", "DoorGap", "Door", "Total gap around the door, half each side", 0.125 * IN),
    ("App::PropertyLength", "FrameWidth", "Door", "Shaker stile and rail width", 2.25 * IN),
    ("App::PropertyLength", "GrooveDepth", "Door", "Panel groove depth; also the rail stub tenon length", 0.375 * IN),
    ("App::PropertyLength", "PanelPlay", "Door", "Panel shorter than the groove bottom, per edge", 0.0625 * IN),
    ("App::PropertyAngle", "DoorOpenAngle", "Door", "Show the door opened by this angle, for checking clearance", 0.0),
    ("App::PropertyInteger", "TrayCount", "Trays", "Number of pull-out trays", 4),
    ("App::PropertyLength", "FirstTrayHeight", "Trays", "Underside of the lowest tray above the floor", 4 * IN),
    ("App::PropertyLength", "TraySpacing", "Trays", "Underside to underside of neighbouring trays", 12 * IN),
    ("App::PropertyLength", "TrayHeight", "Trays", "Tray wall height", 4 * IN),
    ("App::PropertyLength", "SlideClearance", "Trays", "Per side, from the slide maker's data", 0.5 * IN),
    ("App::PropertyLength", "SlideStep", "Trays", "Slides are sold in steps of this length", 2 * IN),
    ("App::PropertyLength", "RearClearance", "Trays", "Behind the trays, in front of the back panel", 0.5 * IN),
    ("App::PropertyLength", "DoorClearance", "Trays", "Door's inside face to the tray fronts (hinge arms)", 1 * IN),
    ("App::PropertyPercent", "TrayExtension", "Trays", "Show the trays pulled out this far, for checking", 0),
    ("App::PropertyLength", "SlideLength", "Result", "Full-extension slide length for the trays", 0.0),
    ("App::PropertyStringList", "Parts", "Result", "Cut sizes, inches", []),
]
# Properties of earlier versions (a macro copy); thicknesses now come from the materials.
OBSOLETE = ("Thickness", "BackThickness", "TrayWall", "TrayBottomThickness", "GrooveWidth")


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


def thickness(obj, prop):
    return CO.sheet_thickness(getattr(obj, prop))


def hinge_count(door_height):
    """Hinges for a door height, from the library's concealed-hinge table."""
    joint = CO.library_item("joint.concealed_hinge")
    table, extra = sorted(joint["count_table"]), joint.get("extra_every", 400.0)
    for max_len, count in table:
        if door_height <= max_len:
            return count
    last_len, last_count = table[-1]
    return last_count + math.ceil((door_height - last_len) / extra)


class TrapezoidCabinet(CO.CabinetFeature):  # the cut list collects CabinetFeatures
    IFC_TYPE = "Furniture"

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        """Adds missing properties (also on documents saved with an earlier version)."""
        for name in OBSOLETE:
            if name in obj.PropertiesList:
                obj.removeProperty(name)
        for kind, name, group, tip, default in PROPERTIES:
            if name in obj.PropertiesList:
                continue
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
        for e in build(obj):
            bb = e["shape"].BoundBox
            part = CParts.Part(e["name"], e["role"], e["size"], (bb.XMin, bb.YMin, bb.ZMin),
                               e["grain"], e["ops"])
            out.append((getattr(obj, e["material"]), part))
        return out

    def solids(self, obj):
        """Solids in the order of parts()."""
        return [e["shape"] for e in build(obj)]

    def fasteners(self, obj, schedule):
        geo = geometry(obj)
        out = {"hardware.hinge": hinge_count(geo["door_h"])}
        if geo["trays"]:
            out[f"hardware.drawer_slide@{round(geo['slide'], 1):g}"] = geo["trays"]
        return out

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
        entries = build(obj)
        placement = obj.Placement
        obj.Shape = Part.makeCompound([e["shape"] for e in entries])
        obj.Placement = placement
        geo = geometry(obj)
        obj.SlideLength = geo["slide"]
        lines = [f"{e['name']} [{getattr(obj, e['material'])}]: {e['text']}" for e in entries]
        if geo["trays"]:
            slide = _length(CO.cut_list_units(obj.Document), geo["slide"])
            lines.append(f"Slides: {geo['trays']} pairs, {slide} full extension")
        lines.append(f"Hinges: {hinge_count(geo['door_h'])}, hinged {obj.HingeSide}; hinge side meets "
                     f"the door at {geo['hinge_angle']:.1f} deg (use angled hinges)")
        obj.Parts = lines


def geometry(obj):
    """Derived sizes shared by the shapes, the cut list and the hardware."""
    W, DL, DR, H = obj.BackWidth.Value, obj.LeftDepth.Value, obj.RightDepth.Value, obj.Height.Value
    T, TB = thickness(obj, "CarcassMaterial"), thickness(obj, "BackMaterial")
    if min(W, DL, DR, H) <= 0 or W <= 2 * T:
        raise ValueError("sizes must be positive and BackWidth more than 2 x the carcass thickness")
    y_fl, y_fr, y_bi = -DL, -DR, -TB
    dx, dy = W, y_fr - y_fl
    front_len = math.hypot(dx, dy)
    theta = math.degrees(math.atan2(dy, dx))
    slope = dy / dx

    def front_y(x, inset=0.0):
        return y_fl + slope * x + inset * front_len / dx

    x_l = T + obj.SlideClearance.Value
    x_r = W - T - obj.SlideClearance.Value
    y_back = y_bi - obj.RearClearance.Value
    room = y_back - front_y(x_l, obj.DoorClearance.Value)
    step = obj.SlideStep.Value
    slide = math.floor(room / step + 1e-9) * step if step > 0 else room
    gap = obj.DoorGap.Value
    return {
        "W": W, "DL": DL, "DR": DR, "H": H, "T": T, "TB": TB, "y_fl": y_fl, "y_fr": y_fr, "y_bi": y_bi,
        "dx": dx, "front_len": front_len, "theta": theta, "slope": slope, "front_y": front_y,
        "x_l": x_l, "x_r": x_r, "y_back": y_back, "slide": max(slide, 0.0),
        "trays": max(obj.TrayCount, 0), "door_w": front_len - gap, "door_h": H - gap, "gap": gap,
        "hinge_angle": 90 - theta if obj.HingeSide == "left" else 90 + theta,
    }


def build(obj):
    """Every part: dict(name, role, material, size, grain, ops, text, shape).
    size is the rectangular blank (dx, dy, dz) with the grain along `grain`."""
    g = geometry(obj)
    units = CO.cut_list_units(obj.Document)

    def _inch(mm, denominator=16):
        return _length(units, mm, denominator)

    W, H, T, TB = g["W"], g["H"], g["T"], g["TB"]
    y_fl, y_fr, y_bi, front_y, slope = g["y_fl"], g["y_fr"], g["y_bi"], g["front_y"], g["slope"]
    front_len, dx, theta = g["front_len"], g["dx"], g["theta"]
    big = 10 * max(W, g["DL"], g["DR"], H)
    entries = []

    def add(name, role, material, size, grain, ops, text, shape):
        entries.append(dict(name=name, role=role, material=material, size=size, grain=grain,
                            ops=tuple(ops), text=text, shape=shape))

    # ---- carcass: the plan inside the back, extruded, cut to each part's slab
    carcass = _prism([(0, y_fl), (W, y_fr), (W, y_bi), (0, y_bi)], 0, H)

    def slab(x0, x1, z0, z1):
        return carcass.common(_box(x0, x1, -big, big, z0, z1))

    bevel = f"bevel front edge {abs(theta):.1f} deg"
    for name, x0, depth in (("Left side", 0, g["DL"] - TB), ("Right side", W - T, g["DR"] - TB)):
        add(name, "carcass", "CarcassMaterial", (T, depth, H), "z", [bevel],
            f"{_inch(depth)} x {_inch(H)} x {_inch(T, 32)}, {bevel}", slab(x0, x0 + T, 0, H))
    d_left, d_right = y_bi - front_y(T), y_bi - front_y(W - T)
    taper = f"taper {_inch(d_left)} deep at left to {_inch(d_right)} at right"
    flat = ((W - 2 * T, d_right, T), "x", [taper],
            f"{_inch(W - 2 * T)} x {_inch(d_right)} blank, {taper}, {_inch(T, 32)} thick")
    add("Bottom", "carcass", "CarcassMaterial", *flat, slab(T, W - T, 0, T))
    add("Top", "carcass", "CarcassMaterial", *flat, slab(T, W - T, H - T, H))
    add("Back", "back", "BackMaterial", (W, TB, H), "z", [],
        f"{_inch(W)} x {_inch(H)} x {_inch(TB, 32)}", _box(0, W, y_bi, 0, 0, H))

    # ---- pull-out trays: slides along y on the side panels, as long as the
    # left (shallower) side allows; the tray front is parallel to the door.
    n_trays, th = g["trays"], obj.TrayHeight.Value
    tw = tbt = thickness(obj, "TrayMaterial")
    x_l, x_r, y_back, slide = g["x_l"], g["x_r"], g["y_back"], g["slide"]
    top_of_trays = T
    if n_trays:
        if slide <= 2 * tw or x_r - x_l <= 2 * tw:
            raise ValueError("no room for trays: cabinet too shallow or narrow")
        y_tfl = y_back - slide
        y_tfr = y_tfl + slope * (x_r - x_l)
        plan = [(x_l, y_tfl), (x_r, y_tfr), (x_r, y_back), (x_l, y_back)]
        xm0, xm1, split = x_l + tw, x_r - tw, y_back - tw
        inset = tw * front_len / dx  # front wall thickness measured along y
        inner = [(xm0, y_tfl + inset + slope * tw), (xm1, y_tfr + inset - slope * tw), (xm1, split), (xm0, split)]
        pull = -obj.TrayExtension / 100.0 * slide
        heights = [obj.FirstTrayHeight.Value + i * obj.TraySpacing.Value for i in range(n_trays)]
        if heights[0] < T or heights[-1] + th > H - T:
            raise ValueError("trays do not fit between the bottom and the top")
        top_of_trays = heights[-1] + th
        front_wall = (xm1 - xm0) * front_len / dx
        bl, br = split - inner[0][1], split - inner[1][1]
        tray_taper = f"taper {_inch(bl)} deep at left to {_inch(br)} at right"
        ends = f"ends cut {abs(theta):.1f} deg"
        for i, z0 in enumerate(heights):
            z1 = z0 + th
            ring = _prism(plan, z0, z1).cut(_prism(inner, z0, z1))
            walls = [
                ("left wall", (tw, slide, th), "y", [], _box(x_l, xm0, -big, big, z0, z1)),
                ("right wall", (tw, y_back - y_tfr, th), "y", [], _box(xm1, x_r, -big, big, z0, z1)),
                ("back wall", (xm1 - xm0, tw, th), "x", [], _box(xm0, xm1, split, big, z0, z1)),
                ("front wall", (front_wall, tw, th), "x", [ends], _box(xm0, xm1, -big, split, z0, z1)),
            ]
            for name, size, grain, ops, cutter in walls:
                shape = ring.common(cutter)
                shape.translate(V(0, pull, 0))
                length = max(size)
                text = f"{_inch(length)} x {_inch(th)} x {_inch(tw, 32)}" + (f", {ops[0]}" if ops else "")
                add(f"Tray {i + 1} {name}", "drawer_box", "TrayMaterial", size, grain, ops, text, shape)
            bottom = _prism(inner, z0, z0 + tbt)
            bottom.translate(V(0, pull, 0))
            add(f"Tray {i + 1} bottom", "drawer_bottom", "TrayMaterial", (xm1 - xm0, br, tbt), "y",
                [tray_taper], f"{_inch(xm1 - xm0)} x {_inch(br)} blank, {tray_taper}, {_inch(tbt, 32)} thick",
                bottom)

    for i in range(max(obj.Shelves, 0)):
        z = top_of_trays + T + (i + 1) * (H - 2 * T - top_of_trays) / (obj.Shelves + 1) - T / 2
        add(f"Shelf {i + 1}", "shelf", "CarcassMaterial", *flat, slab(T, W - T, z, z + T))

    # ---- door, built flat (x = width, y = thickness, z = height), then placed
    dw, dh, gap = g["door_w"], g["door_h"], g["gap"]
    hinge_op = f"hinge side meets the cabinet at {g['hinge_angle']:.1f} deg"
    door = []
    if obj.DoorStyle == "slab":
        door.append(("Door", "door", "CarcassMaterial", (dw, T, dh), "z", [hinge_op],
                     f"{_inch(dw)} x {_inch(dh)} x {_inch(T, 32)}", _box(0, dw, 0, T, 0, dh)))
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
        groove_op = f"groove {_inch(gw, 32)} x {_inch(gd)} deep"
        rail_len = dw - 2 * s + 2 * gd
        tenon_op = f"stub tenons {_inch(gd)} long each end"
        pw, ph = dw - 2 * s + 2 * p, dh - 2 * s + 2 * p
        stile_text = f"{_inch(s)} x {_inch(dh)} x {_inch(T, 32)}, {groove_op}"
        rail_text = f"{_inch(rail_len)} x {_inch(s)} x {_inch(T, 32)}, {groove_op}, {tenon_op}"
        door += [
            ("Door stile left", "door_frame", "CarcassMaterial", (s, T, dh), "z",
             [groove_op] + ([hinge_op] if obj.HingeSide == "left" else []), stile_text,
             _box(0, s, 0, T, 0, dh).cut(groove(s - gd, s, 0, dh))),
            ("Door stile right", "door_frame", "CarcassMaterial", (s, T, dh), "z",
             [groove_op] + ([hinge_op] if obj.HingeSide == "right" else []), stile_text,
             _box(dw - s, dw, 0, T, 0, dh).cut(groove(dw - s, dw - s + gd, 0, dh))),
            ("Door rail", "door_frame", "CarcassMaterial", (rail_len, T, s), "x", [groove_op, tenon_op],
             rail_text, rail(0, s, s - gd, s)),
            ("Door rail", "door_frame", "CarcassMaterial", (rail_len, T, s), "x", [groove_op, tenon_op],
             rail_text, rail(dh - s, dh, dh - s, dh - s + gd)),
            ("Door panel", "door_panel", "BackMaterial", (pw, gw, ph), "z", [],
             f"{_inch(pw)} x {_inch(ph)} x {_inch(gw, 32)}", groove(s - p, dw - s + p, s - p, dh - s + p)),
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
    return entries


def make(name="TrapezoidCabinet", doc=None):
    doc = doc or App.ActiveDocument or App.newDocument("Cabinet")
    obj = doc.addObject("Part::FeaturePython", name)
    TrapezoidCabinet(obj)
    if App.GuiUp:
        obj.ViewObject.Proxy = 0  # default Part view provider
    doc.recompute()
    return obj

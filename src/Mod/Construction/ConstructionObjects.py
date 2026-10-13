# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: parametric construction objects (design doc §5.4, §5.6).

import json
import math
import os
from dataclasses import replace

import ArchStructure
import FreeCAD
import Part

import Build
import Cabinet
import Checks
import CutList
import Framing
import Joinery
import Library
import Member
import Parts
import Room
import Sheathing
import Shed

DEFAULT_MATERIALS = {
    "CarcassMaterial": "sheet.metric.plywood.18",
    "BackMaterial": "sheet.metric.plywood.6",
    "DrawerMaterial": "sheet.metric.plywood.12",
}
MATERIAL_TIPS = {
    "CarcassMaterial": "Sides, bottom, top, shelves, fronts, plinth, fillers",
    "BackMaterial": "Back panel, drawer bottoms and shaker door panels",
    "DrawerMaterial": "Drawer box sides, fronts and backs",
}
# Cabinet part role -> material property; anything else uses CarcassMaterial.
ROLE_MATERIAL = {
    "back": "BackMaterial",
    "drawer_bottom": "BackMaterial",
    "door_panel": "BackMaterial",
    "drawer_box": "DrawerMaterial",
}

_items = None


def items():
    """Shipped library plus user overrides, loaded once per session."""
    global _items
    if _items is None:
        _items = Library.load([Library.LIBRARY_DIR, Library.user_dir()])
    return _items


# (property, Cabinet field, type, group, tooltip). Thicknesses come from the materials.
LENGTH = "App::PropertyLength"
INTEGER = "App::PropertyInteger"
ENUM = "App::PropertyEnumeration"
PROPERTIES = [
    ("Kind", "kind", ENUM, "Cabinet", "base: stretchers; wall / tall: full top; sink: no back"),
    ("Width", "width", LENGTH, "Size", "Outside width of the carcass"),
    ("Height", "height", LENGTH, "Size", "Base to top of the carcass, plinth included"),
    ("Depth", "depth", LENGTH, "Size", "Carcass and back, fronts excluded"),
    ("PlinthHeight", "plinth_height", LENGTH, "Plinth", "0 for no plinth"),
    ("PlinthSetback", "plinth_setback", LENGTH, "Plinth", "Kick board behind the carcass front"),
    ("StretcherWidth", "stretcher_width", LENGTH, "Carcass", "Top stretchers (base cabinets)"),
    ("Shelves", "shelves", INTEGER, "Interior", "Adjustable shelves behind the doors"),
    ("ShelfSetback", "shelf_setback", LENGTH, "Interior", "Shelf front behind the carcass front"),
    ("ShelfClearance", "shelf_clearance", LENGTH, "Interior", "Gap at each shelf end"),
    ("Fronts", "fronts", ENUM, "Fronts", "Doors, a drawer bank, or one drawer over doors"),
    ("Doors", "doors", INTEGER, "Fronts", "0 = one door up to 600 mm wide, else two"),
    ("FrontGap", "door_gap", LENGTH, "Fronts", "Gap between fronts; half of it at outer edges"),
    ("DoorStyle", "door_style", ENUM, "Fronts", "slab, or shaker: frame and a thin panel"),
    ("FrameWidth", "frame_width", LENGTH, "Fronts", "Shaker door stiles and rails"),
    ("Drawers", "drawers", INTEGER, "Drawers", "Drawers in a drawer bank"),
    ("DrawerFrontHeight", "drawer_front_height", LENGTH, "Drawers", "Top drawer over doors"),
    ("SlideClearance", "drawer_side_clearance", LENGTH, "Drawers", "Per side; see slide data"),
    (
        "DrawerHeightClearance",
        "drawer_height_clearance",
        LENGTH,
        "Drawers",
        "Drawer opening height minus box height",
    ),
    ("DrawerRearClearance", "drawer_rear_clearance", LENGTH, "Drawers", "Behind the drawer box"),
    (
        "BlindWidth",
        "blind_width",
        LENGTH,
        "Corner",
        "Front width hidden by the meeting run; 0 = none",
    ),
    ("BlindSide", "blind_side", ENUM, "Corner", "Side of the blind panel"),
    (
        "EdgeBanding",
        "edge_banding",
        "App::PropertyBool",
        "Materials",
        "Band the fronts all round and the front edges of the carcass and shelves",
    ),
]
CHOICES = {
    "Kind": Cabinet.KINDS,
    "Fronts": Cabinet.FRONTS,
    "DoorStyle": Cabinet.DOOR_STYLES,
    "FillerSide": Cabinet.FILLER_SIDES,
    "BlindSide": Cabinet.BLIND_SIDES,
    "RoofType": Shed.ROOFS,
    "Foundation": Shed.FOUNDATIONS,
    "Guards": ("auto", "yes", "no"),
}


def add_property(obj, kind, prop, group, tip, value):
    """Adds prop when missing (new object or older file) and sets its default."""
    if prop in obj.PropertiesList:
        return
    obj.addProperty(kind, prop, group, tip)
    if kind == ENUM:
        setattr(obj, prop, list(CHOICES[prop]))
    setattr(obj, prop, value)


def add_ifc_type(obj, feature):
    """IfcType, read by the BIM workbench's IFC export (exportIFC.getIfcTypeFromObj)."""
    add_property(
        obj, "App::PropertyString", "IfcType", "IFC", "IFC class on export", feature.IFC_TYPE
    )


AREA = "area_material"
REGION_KEY = "CADApp.Construction.Region"
REGIONS = ("all", "metric", "US")


def document_region(doc):
    """The document's library region ("all", "metric", "US"), set with
    Construction_Region; new documents follow preference Mod/Construction/Region."""
    region = doc.Meta.get(REGION_KEY) if doc else None
    return region or FreeCAD.ParamGet(PARAMS).GetString("Region", "all")


def set_document_region(doc, region):
    """Stores the region in the document and narrows every construction
    object's library choices to it (generic items stay)."""
    meta = doc.Meta
    meta[REGION_KEY] = region
    doc.Meta = meta
    for obj in construction_objects(doc):
        obj.Proxy.onDocumentRestored(obj)


def sheathing_area(parts):
    """m² of sheathing parts (their cut rectangles)."""
    return sum(p.cut_size()[0] * p.cut_size()[1] for p in parts) / 1e6


def add_library_choice(obj, prop, category, default, group, tip, where=None):
    """Enumeration of library item ids of one category (and passing `where`)
    in the document's region (generic items always). A value whose item is
    gone (user library changed) or is of another region stays selectable;
    a missing item fails in execute()."""
    region = document_region(obj.Document)
    ids = [
        i["id"]
        for i in Library.of_category(items(), category)
        if (not where or where(i)) and (region == "all" or i.get("region") in (region, "generic"))
    ]
    if prop in obj.PropertiesList:
        current = getattr(obj, prop)
    else:
        obj.addProperty(ENUM, prop, group, tip)
        current = default
    setattr(obj, prop, ids if current in ids else ids + [current])
    setattr(obj, prop, current)


def library_item(material_id):
    item = items().get(material_id)
    if item is None:
        raise ValueError(f"material '{material_id}' not found in the construction library")
    return item


def member_part(name, start, end, section, cuts=(0.0, 0.0)):
    """Cut-list Part of a member: grain along its length, long point to long
    point when its ends are cut at an angle."""
    length = Member.frame(start, end)[0]
    length += sum(Member.end_extension(section[1], a) for a in cuts)
    operations = tuple(f"end cut {a:g}°" for a in cuts if a)
    return Parts.Part(name, "member", (*section, length), (0, 0, 0), "z", operations)


def lumber_section(material_id):
    """(thickness, depth) in mm."""
    item = library_item(material_id)
    return Library.mm(item, "w"), Library.mm(item, "h")


def member_box(start, end, roll, section, cuts=(0.0, 0.0)):
    """Solid of a member (see Member.py), placed in the object's coordinates.
    cuts: (start, end) angles in degrees from square, turning the end cut in
    the plane of the member's depth (a miter or plumb cut); the cut passes
    through the end point on the centre line."""
    length, x, y, z = Member.frame(start, end, roll)
    w, h = section
    e0, e1 = (Member.end_extension(h, a) for a in cuts)
    V = FreeCAD.Vector
    box = Part.makeBox(w, h, length + e0 + e1, V(-w / 2, -h / 2, -e0))
    big = 4 * (length + h + w + e0 + e1)
    for angle, origin, outward in ((cuts[0], 0.0, -1), (cuts[1], length, 1)):
        if not angle:
            continue
        a = math.radians(angle)
        normal = V(0, -outward * math.sin(a), outward * math.cos(a))
        waste = Part.makeBox(big, big, big, V(-big / 2, -big / 2, 0))
        waste.Placement = FreeCAD.Placement(V(0, 0, origin), FreeCAD.Rotation(V(0, 0, 1), normal))
        box = box.cut(waste)
    box.Placement = FreeCAD.Placement(V(*start), FreeCAD.Rotation(V(*x), V(*y), V(*z), "ZXY"))
    return box


def fixes_end_to_face(joint):
    """A joint preset that fixes an end to a face (not hinges, slides or pins)."""
    return "end_to_face" in joint.get("meets", ()) and joint.get("fixes", True)


def joined_solids(result):
    """One solid per part of a Joinery.Result, its pockets cut out."""
    out = []
    for i, p in enumerate(result.boxes):
        solid = Part.makeBox(*p.size, FreeCAD.Vector(*p.pos))
        cuts = [_cut_shape(c) for j, c in result.pockets if j == i]
        out.append(solid.cut(cuts) if cuts else solid)
    return out


def _cut_shape(pocket):
    """Box of a pocket, the cylinder of a hole (its grain is the axis), or the
    prism of a triangular pocket (Parts.Part.profile)."""
    if pocket.profile and pocket.profile[0] == "triangle":
        _, a, ca, b, cb = pocket.profile
        k = 3 - a - b
        lo, size = pocket.pos, pocket.size

        def point(ua, ub):
            p = list(lo)
            p[a] += ua * size[a]
            p[b] += ub * size[b]
            return FreeCAD.Vector(*p)

        # The right angle at (ca, cb); the hypotenuse from (ca, 1 - cb) to (1 - ca, cb).
        triangle = [point(ca, cb), point(ca, 1 - cb), point(1 - ca, cb), point(ca, cb)]
        face = Part.Face(Part.makePolygon(triangle))
        direction = FreeCAD.Vector(*(size[k] if n == k else 0 for n in range(3)))
        return face.extrude(direction)
    if pocket.role != "hole":
        return Part.makeBox(*pocket.size, FreeCAD.Vector(*pocket.pos))
    k = "xyz".index(pocket.grain)
    centre = [p + s / 2 for p, s in zip(pocket.pos, pocket.size)]
    centre[k] = pocket.pos[k]
    axis = FreeCAD.Vector(*(1 if n == k else 0 for n in range(3)))
    radius = pocket.size[(k + 1) % 3] / 2
    return Part.makeCylinder(radius, pocket.size[k], FreeCAD.Vector(*centre), axis)


class ViewProvider:
    """View of a construction object: double-click opens its editing panel
    (ConstructionPanels) when it has one."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def doubleClicked(self, vobj):
        import ConstructionPanels

        return ConstructionPanels.show(vobj.Object)

    def dumps(self):
        return None

    def loads(self, state):
        return None


def set_shape(obj, shapes):
    """Sets the object's shape without disturbing its Placement. The compound
    keeps each child's own placement."""
    placement = obj.Placement
    obj.Shape = Part.makeCompound(shapes)
    obj.Placement = placement


class CabinetFeature:
    """Frameless cabinet. Every size is a property; edit in the property view."""

    IFC_TYPE = "Furniture"
    skip = ()  # Cabinet properties a subclass does not use

    def __init__(self, obj, preset="base"):
        obj.Proxy = self
        self.setProperties(obj, preset)

    def setProperties(self, obj, preset="base"):
        add_ifc_type(obj, self)
        defaults = Cabinet.defaults(preset)
        for prop, field, ptype, group, tip in PROPERTIES:
            if prop not in self.skip:
                add_property(obj, ptype, prop, group, tip, getattr(defaults, field))
        for prop, default in DEFAULT_MATERIALS.items():
            add_library_choice(
                obj, prop, Library.SHEET_GOODS, default, "Materials", MATERIAL_TIPS[prop]
            )
        add_library_choice(
            obj,
            "CarcassJoint",
            "joint",
            Cabinet.Cabinet.carcass_joint,
            "Joinery",
            "Joint between the sides and the bottom, top and stretchers",
            where=fixes_end_to_face,
        )

    def onDocumentRestored(self, obj):
        self.setProperties(obj, obj.Kind)

    def spec(self, obj):
        kwargs = {}
        for prop, field, ptype, _, _ in PROPERTIES:
            if prop in self.skip:
                continue
            value = getattr(obj, prop)
            if ptype == LENGTH:
                value = float(value.Value)
            elif ptype == INTEGER:
                value = int(value)
            kwargs[field] = value
        kwargs["thickness"] = sheet_thickness(obj.CarcassMaterial)
        kwargs["back_thickness"] = sheet_thickness(obj.BackMaterial)
        kwargs["drawer_thickness"] = sheet_thickness(obj.DrawerMaterial)
        kwargs["carcass_joint"] = obj.CarcassJoint
        return Cabinet.Cabinet(**kwargs)

    def joined(self, obj):
        """Joinery.Result: parts after joinery, cuts, operations, hardware."""
        return self.spec(obj).joined(items())

    def cabinets(self, obj):
        return [self.spec(obj)]

    def checks(self, obj, rules):
        return [r for c in self.cabinets(obj) for r in Checks.cabinet(c, rules)]

    def fasteners(self, obj, schedule):
        return self.joined(obj).fasteners

    def anchored(self, obj, rules):
        """Cabinets to fix to the wall."""
        kinds = rules.get("anchor_cabinet_kinds", ())
        return sum(1 for c in self.cabinets(obj) if c.kind in kinds)

    def parts(self, obj):
        """[(material id, Part)] for the cut list."""
        return [
            (getattr(obj, ROLE_MATERIAL.get(p.role, "CarcassMaterial")), p)
            for p in self.joined(obj).boxes
        ]

    def solids(self, obj):
        """Solids in the order of parts(), in the object's coordinates."""
        return joined_solids(self.joined(obj))

    def execute(self, obj):
        # ValueError from validate() marks the object as failed with its message.
        set_shape(obj, self.solids(obj))

    def dumps(self):
        return None

    def loads(self, state):
        return None


def parse(prop, text, allow_styles):
    try:
        return Cabinet.parse_entries(text, allow_styles)
    except ValueError as e:
        raise ValueError(f"{prop}: {e}")


class CabinetRunFeature(CabinetFeature):
    """Cabinets side by side along a wall; all share the cabinet properties."""

    skip = ("Width",)

    def setProperties(self, obj, preset="base"):
        super().setProperties(obj, preset)
        standard = ", ".join(f"{w:g}" for w in Cabinet.STANDARD_WIDTHS)
        run = [
            ("App::PropertyLength", "Length", "Run", "Wall length to fill", 2400.0),
            (
                "App::PropertyString",
                "Widths",
                "Run",
                "Cabinets left to right, e.g. 1000 blind_left, 600 drawers, 800 sink, 600. "
                "Styles: " + ", ".join(Cabinet.RUN_STYLES) + ". Empty = chosen from StandardWidths",
                "",
            ),
            (
                "App::PropertyString",
                "StandardWidths",
                "Run",
                "Widths to choose from when Widths is empty",
                standard,
            ),
            (ENUM, "FillerSide", "Run", "Where the leftover length goes", "both"),
            ("App::PropertyString", "Layout", "Run", "Result: widths and fillers", ""),
        ]
        for ptype, prop, group, tip, value in run:
            add_property(obj, ptype, prop, group, tip, value)
        obj.setEditorMode("Layout", 1)  # read-only

    def run(self, obj):
        widths, styles = parse("Widths", obj.Widths, allow_styles=True)
        standard, _ = parse("StandardWidths", obj.StandardWidths, allow_styles=False)
        return Cabinet.Run(
            self.spec(obj),
            length=float(obj.Length.Value),
            widths=widths,
            standard=standard,
            filler_side=obj.FillerSide,
            styles=styles,
        )

    def joined(self, obj):
        return self.run(obj).joined(items())

    def cabinets(self, obj):
        run = self.run(obj)
        widths, _, _ = run.layout()
        styles = list(run.styles) + [None] * (len(widths) - len(run.styles))
        return [
            Cabinet.styled(replace(run.cabinet, width=w), s)
            for w, s in zip(widths, styles)
            if s != Cabinet.GAP
        ]

    def execute(self, obj):
        widths, left, right = self.run(obj).layout()
        layout = ", ".join(f"{w:g}" for w in widths)
        obj.Layout = f"{layout} | fillers {left:g} / {right:g}"
        super().execute(obj)


def sheet_thickness(material_id):
    return Library.mm(library_item(material_id), "t")


def _make(feature, preset, name, doc):
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    feature(obj, preset)
    if preset == "wall":
        placement = obj.Placement  # a copy: modify, then assign back
        placement.Base.z = Cabinet.WALL_ELEVATION
        obj.Placement = placement
    if FreeCAD.GuiUp:
        ViewProvider(obj.ViewObject)
    doc.recompute()
    return obj


def make_cabinet(preset="base", doc=None):
    """preset: a cabinet kind or "corner" (see Cabinet.DEFAULTS)."""
    return _make(CabinetFeature, preset, preset.capitalize() + "Cabinet", doc)


def make_cabinet_run(preset="base", doc=None, name=None):
    return _make(CabinetRunFeature, preset, name or preset.capitalize() + "Run", doc)


class MemberFeature(ArchStructure._Structure):
    """Lumber member: an Arch_Structure (BIM) whose profile is a BIM rectangle
    profile of the lumber section and whose extrusion path is a line (Tool).
    Added on top of the BIM object: library lumber size, angled end cuts and
    the cut-list, check and fastener hooks of construction objects."""

    IFC_TYPE = "Beam"

    def __init__(self, obj):
        super().__init__(obj)
        self.setConstructionProperties(obj)

    def setConstructionProperties(self, obj):
        for ptype, prop, tip in (
            (
                "App::PropertyAngle",
                "StartCut",
                "End cut at the start, degrees from square, across the depth (45 = miter)",
            ),
            ("App::PropertyAngle", "EndCut", "End cut at the end, degrees from square"),
        ):
            if prop not in obj.PropertiesList:
                obj.addProperty(ptype, prop, "Member", tip)
        add_library_choice(obj, "Lumber", Library.LUMBER, DEFAULT_LUMBER, "Member", "Lumber size")

    def onDocumentRestored(self, obj):
        super().onDocumentRestored(obj)
        self.setConstructionProperties(obj)

    def endpoints(self, obj):
        ((line, subs),) = obj.Tool
        edge = line.Shape.getElement(subs[0]) if subs else line.Shape.Edges[0]
        if edge.Curve.TypeId != "Part::GeomLine":
            raise ValueError("members follow straight edges only")
        return tuple(edge.Vertexes[0].Point), tuple(edge.Vertexes[-1].Point)

    def parts(self, obj):
        start, end = self.endpoints(obj)
        cuts = (obj.StartCut.Value, obj.EndCut.Value)
        section = lumber_section(obj.Lumber)
        return [(obj.Lumber, member_part(obj.Label, start, end, section, cuts))]

    def checks(self, obj, rules):
        return []

    def anchored(self, obj, rules):
        return 0

    def fasteners(self, obj, schedule):
        return {}

    def solids(self, obj):
        return [obj.Shape]

    def execute(self, obj):
        w, h = lumber_section(obj.Lumber)
        profile = obj.Base
        if (profile.Width.Value, profile.Height.Value) != (w, h):
            profile.Width, profile.Height = w, h
            profile.recompute()
        start, end = self.endpoints(obj)
        cuts = (obj.StartCut.Value, obj.EndCut.Value)
        # A cut through the centre line leaves the stock long point to long point.
        obj.ToolOffsetFirst, obj.ToolOffsetLast = (Member.end_extension(h, a) for a in cuts)
        super().execute(obj)
        if not any(cuts) or obj.Shape.isNull():
            return
        length, x, y, z = Member.frame(start, end, -obj.BaseRotation.Value)
        V = FreeCAD.Vector
        big = 4 * (length + h + w)
        shape = obj.Shape
        for angle, point, outward in ((cuts[0], start, -1), (cuts[1], end, 1)):
            if not angle:
                continue
            a = math.radians(angle)
            normal = V(*z) * (outward * math.cos(a)) - V(*y) * (outward * math.sin(a))
            waste = Part.makeBox(big, big, big, V(-big / 2, -big / 2, 0))
            waste.Placement = FreeCAD.Placement(V(*point), FreeCAD.Rotation(V(0, 0, 1), normal))
            shape = shape.cut(waste)
        obj.Shape = shape


DEFAULT_LUMBER = "lumber.metric.45x95"


def make_member(base=None, doc=None, name="Member"):
    """base: (object, "EdgeN") to follow, or None for a free 2400 mm stud
    (with a line of its own to edit)."""
    import Arch
    import Draft

    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    if base:
        line, subs = base
        path = [(line, subs)]
    else:
        line = Draft.make_line(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 2400))
        line.Label = f"{name} path"
        path = [(line, ["Edge1"])]
    w, h = lumber_section(DEFAULT_LUMBER)
    profile = Arch.makeProfile([0, "REC", f"{name} profile", "R", w, h])
    obj = Arch.makeStructure(profile, name=name)
    MemberFeature(obj)  # replaces BIM's proxy with the construction subclass
    obj.IfcType = "Beam"
    obj.Tool = path
    obj.BasePerpendicularToTool = True
    doc.recompute()
    return obj


def longest_stock(*material_ids):
    """Longest piece every listed lumber comes in (the shortest of their maxima)."""
    return min(max(library_item(m).get("stock_lengths_mm") or [6000.0]) for m in material_ids)


def profile_solid(piece, thickness):
    """Solid of a Framing.ProfilePiece: its (y, z) outline extruded along x by
    piece.extrude, or by the section thickness when that is 0."""
    thickness = piece.extrude or thickness
    x0 = piece.x - thickness / 2
    points = [FreeCAD.Vector(x0, y, z) for y, z in piece.profile]
    face = Part.Face(Part.makePolygon(points + points[:1]))
    return face.extrude(FreeCAD.Vector(thickness, 0, 0))


def framing_pieces(model):
    """[(piece, section name)] of a Framing model's members and profile boards."""
    pieces = list(model.pieces()) + list(getattr(model, "boards", list)())
    return [(p, p.section) for p in pieces]


def piece_part(piece, size):
    """Cut-list Part of a framing piece. size: (thickness, depth)."""
    if isinstance(piece, Framing.ProfilePiece):
        return Parts.Part(piece.name, "member", (*size, piece.cut_length()), (0, 0, 0), "z")
    return member_part(piece.name, piece.start, piece.end, size)


def piece_solid(piece, size):
    if isinstance(piece, Framing.ProfilePiece):
        return profile_solid(piece, size[0])
    return member_box(piece.start, piece.end, piece.roll, size)


def sheet_panels(surfaces, item, stagger):
    """[(surface, (u0, v0, du, dv))] covering surfaces with a sheet-goods item,
    and the sheet thickness."""
    w, h, t = (Library.mm(item, k) for k in ("w", "h", "t"))
    sheet = (max(w, h), min(w, h))
    panels = [
        (surface, panel)
        for surface in surfaces
        for panel in Sheathing.cover_surface(surface, sheet, stagger)
    ]
    return panels, t


def panel_part(surface, panel, t):
    grain = "x" if surface.long_along == "u" else "y"  # the sheet's long side
    return Parts.Part(surface.name, "sheathing", (panel[2], panel[3], t), (0, 0, 0), grain)


def panel_solid(surface, panel, t):
    V = FreeCAD.Vector
    u0, v0, du, dv = panel
    solid = Part.makeBox(du, dv, t, V(u0, v0, 0))
    for hu, hv, hdu, hdv in surface.openings:
        if hu < u0 + du and u0 < hu + hdu and hv < v0 + dv and v0 < hv + hdv:
            solid = solid.cut(Part.makeBox(hdu, hdv, t, V(hu, hv, 0)))
    if surface.clip:
        outline = [V(u, v, 0) for u, v in surface.clip]
        prism = Part.Face(Part.makePolygon(outline + outline[:1])).extrude(V(0, 0, t))
        solid = solid.common(prism)
    frame = FreeCAD.Placement(
        V(*surface.origin),
        FreeCAD.Rotation(V(*surface.u), V(*surface.v), V(*surface.normal()), "ZXY"),
    )
    solid.Placement = frame.multiply(solid.Placement)
    return solid


class FramingFeature:
    """Base of framing objects. A subclass defines PROPERTIES and MATERIALS
    (property, section name, default lumber, tip) and model(obj), which returns
    a Framing.Wall / Floor / GableRoof."""

    GROUP = "Framing"
    IFC_TYPE = "Building Element Part"
    PROPERTIES = []
    MATERIALS = []

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        add_ifc_type(obj, self)
        for ptype, prop, tip, value in self.PROPERTIES:
            add_property(obj, ptype, prop, self.GROUP, tip, value)
        for prop, _, default, tip in self.MATERIALS:
            add_library_choice(obj, prop, Library.LUMBER, default, self.GROUP, tip)

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

    def materials(self, obj):
        """section name -> (lumber id, (thickness, depth))."""
        return {
            section: (getattr(obj, prop), lumber_section(getattr(obj, prop)))
            for prop, section, _, _ in self.MATERIALS
        }

    def max_piece(self, obj):
        return longest_stock(*(getattr(obj, prop) for prop, _, _, _ in self.MATERIALS))

    def _all(self, obj):
        """[(piece, (material id, (thickness, depth)))]."""
        mats = self.materials(obj)
        return [(p, mats[section]) for p, section in framing_pieces(self.model(obj))]

    def parts(self, obj):
        return [(material, piece_part(p, size)) for p, (material, size) in self._all(obj)]

    def solids(self, obj):
        return [piece_solid(p, size) for p, (_, size) in self._all(obj)]

    def execute(self, obj):
        set_shape(obj, self.solids(obj))

    def design_values(self, obj, prop):
        return library_item(getattr(obj, prop)).get("design_values")

    def anchored(self, obj, rules):
        return 0

    def fasteners(self, obj, schedule):
        return Framing.fasteners(self.model(obj), schedule)

    def dumps(self):
        return None

    def loads(self, state):
        return None


def _length(prop, tip, value):
    return (LENGTH, prop, tip, value)


class WallFrameFeature(FramingFeature):
    """Stud wall framing along the object's local X axis (see Framing.py)."""

    IFC_TYPE = "Wall"
    GROUP = "Wall"
    _d = Framing.Wall()
    PROPERTIES = [
        _length("Length", "Wall length", _d.length),
        _length("Height", "Bottom of the bottom plate to top of the top plates", _d.height),
        _length("StudSpacing", "Stud centres, e.g. 400 / 600 mm or 406.4 (16 in)", _d.spacing),
        (INTEGER, "TopPlates", "1 or 2", _d.top_plates),
        _length("CornerStart", "Depth of a wall butting at the start; 0 = none", 0.0),
        _length("CornerEnd", "Depth of a wall butting at the end; 0 = none", 0.0),
        (
            "App::PropertyFloat",
            "HeaderLoad",
            "Uniform load on each header in kN/m, from your load calculation; "
            "0 = headers not checked",
            0.0,
        ),
        (
            "App::PropertyString",
            "Openings",
            "Rough openings, e.g. 'door 900x2100 @ 600, window 1200x1000 @ 2400 sill 900' "
            "(mm; @ = left edge from the wall start)",
            "",
        ),
    ]
    MATERIALS = [
        ("StudMaterial", "stud", "lumber.metric.45x95", "Studs and plates"),
        ("HeaderMaterial", "header", "lumber.metric.45x195", "One header ply"),
    ]

    def model(self, obj):
        try:
            openings = Framing.parse_openings(obj.Openings)
        except ValueError as e:
            raise ValueError(f"Openings: {e}")
        return Framing.Wall(
            length=float(obj.Length.Value),
            height=float(obj.Height.Value),
            spacing=float(obj.StudSpacing.Value),
            top_plates=int(obj.TopPlates),
            stud=lumber_section(obj.StudMaterial),
            header=lumber_section(obj.HeaderMaterial),
            openings=openings,
            max_piece=longest_stock(obj.StudMaterial),
            corners=(float(obj.CornerStart.Value), float(obj.CornerEnd.Value)),
        )

    def checks(self, obj, rules):
        values = self.design_values(obj, "HeaderMaterial")
        return Checks.wall(self.model(obj), rules, values, float(obj.HeaderLoad))


LOAD_TIP = "from your load calculation; 0 = not checked"


class FloorFrameFeature(FramingFeature):
    """Floor platform: joists along local Y between rim joists along X."""

    IFC_TYPE = "Slab"
    GROUP = "Floor"
    _d = Framing.Floor()
    PROPERTIES = [
        _length("Length", "Along the rim joists", _d.length),
        _length("Width", "Along the joists (rim to rim)", _d.width),
        _length("JoistSpacing", "Joist centres", _d.spacing),
        ("App::PropertyFloat", "FloorLoad", "Floor load in kPa, " + LOAD_TIP, 0.0),
        (
            "App::PropertyString",
            "Beams",
            "Dropped beams under the joists: distances from the first rim, e.g. 1500, 3000",
            "",
        ),
        ("App::PropertyInteger", "BeamPlies", "Plies in each beam", _d.beam_plies),
        _length("PostHeight", "Posts under the beams, footing to beam; 0 = none", 0.0),
        _length("FootingSize", "Side of a square post footing, for the concrete", 400.0),
        _length("FootingDepth", "Depth of a post footing, for the concrete", 600.0),
        ("App::PropertyInteger", "BlockingRows", "Rows of blocking in each span", 0),
        (
            "App::PropertyString",
            "Openings",
            "Stairwells etc.: width x length @ x, y (mm, x along the rims), e.g. 900x2400 @ 600, 300",
            "",
        ),
    ]
    MATERIALS = [
        ("JoistMaterial", "joist", "lumber.metric.45x195", "Joists, rims, trimmers, headers"),
        ("BeamMaterial", "beam", "lumber.metric.45x195", "Beam plies"),
        ("PostMaterial", "post", "lumber.metric.95x95", "Posts under the beams"),
    ]

    def model(self, obj):
        return Framing.Floor(
            length=float(obj.Length.Value),
            width=float(obj.Width.Value),
            spacing=float(obj.JoistSpacing.Value),
            joist=lumber_section(obj.JoistMaterial),
            max_piece=self.max_piece(obj),
            beams=tuple(Framing.parse_numbers(obj.Beams)),
            beam=lumber_section(obj.BeamMaterial),
            beam_plies=int(obj.BeamPlies),
            post=lumber_section(obj.PostMaterial),
            post_height=float(obj.PostHeight.Value),
            blocking_rows=int(obj.BlockingRows),
            openings=tuple(Framing.parse_floor_openings(obj.Openings)),
            footing=(float(obj.FootingSize.Value), float(obj.FootingDepth.Value)),
        )

    def concrete(self, obj):
        """[(what, m³)] of concrete to buy."""
        return [("Floor post footings", self.model(obj).concrete_m3())]

    def checks(self, obj, rules):
        values = self.design_values(obj, "JoistMaterial")
        beam_values = self.design_values(obj, "BeamMaterial")
        return Checks.floor(self.model(obj), rules, values, float(obj.FloorLoad), beam_values)


class GableRoofFeature(FramingFeature):
    """Gable roof framing: ridge along local X, z = 0 at the top of the wall plates."""

    IFC_TYPE = "Roof"
    GROUP = "Roof"
    _d = Framing.GableRoof()
    PROPERTIES = [
        _length("Length", "Along the ridge: outside of the end walls", _d.length),
        _length("Span", "Outer face to outer face of the side walls", _d.span),
        ("App::PropertyAngle", "Pitch", "Roof slope (26.57 = 6 in 12)", _d.pitch),
        _length("Overhang", "Eave overhang, horizontal from the wall face", _d.overhang),
        _length("RafterSpacing", "Rafter centres", _d.spacing),
        _length("Seat", "Birdsmouth seat: the wall top plate width", _d.seat),
        ("App::PropertyBool", "CeilingJoists", "Ceiling joists as rafter ties", True),
        (
            "App::PropertyBool",
            "GableStuds",
            "Studs in the gable triangles over the end walls",
            True,
        ),
        ("App::PropertyFloat", "RoofLoad", "kPa on plan, " + LOAD_TIP, 0.0),
    ]
    MATERIALS = [
        ("RafterMaterial", "rafter", "lumber.metric.45x145", "Rafters"),
        ("RidgeMaterial", "ridge", "lumber.metric.45x195", "Ridge board"),
        ("TieMaterial", "tie", "lumber.metric.45x145", "Ceiling joists"),
        ("GableStudMaterial", "gable_stud", "lumber.metric.45x95", "Gable studs"),
    ]

    def model(self, obj):
        return Framing.GableRoof(
            length=float(obj.Length.Value),
            span=float(obj.Span.Value),
            pitch=float(obj.Pitch.Value),
            overhang=float(obj.Overhang.Value),
            spacing=float(obj.RafterSpacing.Value),
            rafter=lumber_section(obj.RafterMaterial),
            ridge=lumber_section(obj.RidgeMaterial),
            seat=float(obj.Seat.Value),
            ties=bool(obj.CeilingJoists),
            tie=lumber_section(obj.TieMaterial),
            gable_studs=bool(obj.GableStuds),
            gable_stud=lumber_section(obj.GableStudMaterial),
            max_piece=self.max_piece(obj),
        )

    def checks(self, obj, rules):
        values = self.design_values(obj, "RafterMaterial")
        return Checks.roof(self.model(obj), rules, values, float(obj.RoofLoad))


class ShedRoofFeature(FramingFeature):
    """Mono-pitch roof framing: rafters from the low wall (local y = 0) over the
    high wall; z = 0 at the top of the low wall's plates."""

    IFC_TYPE = "Roof"
    GROUP = "Roof"
    _d = Framing.ShedRoof()
    PROPERTIES = [
        _length("Length", "Along the walls", _d.length),
        _length("Span", "Outer face of the low wall to outer face of the high wall", _d.span),
        ("App::PropertyAngle", "Pitch", "Roof slope (14.04 = 3 in 12)", _d.pitch),
        _length("Overhang", "Overhang beyond each wall face, horizontal", _d.overhang),
        _length("RafterSpacing", "Rafter centres", _d.spacing),
        _length("Seat", "Birdsmouth seat: the wall top plate width", _d.seat),
        ("App::PropertyFloat", "RoofLoad", "kPa on plan, " + LOAD_TIP, 0.0),
        _length("HighWallRise", "Result: how much taller to frame the high wall", 0.0),
    ]
    MATERIALS = [("RafterMaterial", "rafter", "lumber.metric.45x145", "Rafters")]

    def setProperties(self, obj):
        super().setProperties(obj)
        obj.setEditorMode("HighWallRise", 1)  # read-only

    def model(self, obj):
        return Framing.ShedRoof(
            length=float(obj.Length.Value),
            span=float(obj.Span.Value),
            pitch=float(obj.Pitch.Value),
            overhang=float(obj.Overhang.Value),
            spacing=float(obj.RafterSpacing.Value),
            rafter=lumber_section(obj.RafterMaterial),
            seat=float(obj.Seat.Value),
            max_piece=self.max_piece(obj),
        )

    def execute(self, obj):
        rise = self.model(obj).rise()
        if abs(obj.HighWallRise.Value - rise) > 1e-6:
            obj.HighWallRise = rise
        super().execute(obj)

    def checks(self, obj, rules):
        values = self.design_values(obj, "RafterMaterial")
        return Checks.shed_roof(self.model(obj), rules, values, float(obj.RoofLoad))


class StairFeature(FramingFeature):
    """Stair plan on an Arch_Stairs (BIM): the Arch_Stairs gives the shape, rise,
    steps, tread depth, width, nosing, landing and railings. This object adds
    the lumber: treads cut from whole boards, cut stringers, newel posts,
    balusters, the advisory checks and the cut list."""

    IFC_TYPE = "Stair"
    GROUP = "Stair"
    _d = Framing.Stair()
    PROPERTIES = [
        _length("TreadGap", "Gap between tread boards", _d.tread_gap),
        _length("StringerSpacing", "Largest distance between stringers", _d.max_stringer_spacing),
        _length("HandrailHeight", "Top of the handrail above the nosings", _d.handrail_height),
        _length("BalusterGap", "Largest clear gap between balusters", _d.max_baluster_gap),
    ]
    MATERIALS = [
        ("StringerMaterial", "stringer", "lumber.metric.45x220", "Stringers (cut)"),
        ("TreadMaterial", "tread", "lumber.metric.45x145", "Tread boards, laid flat"),
        ("RailMaterial", "rail", "lumber.metric.45x70", "Handrails"),
        ("PostMaterial", "post", "lumber.metric.70x70", "Newel posts"),
        ("BalusterMaterial", "baluster", "lumber.metric.45x45", "Balusters"),
        ("LandingJoistMaterial", "landing_joist", "lumber.metric.45x145", "Landing frame"),
    ]

    def setProperties(self, obj):
        super().setProperties(obj)
        add_property(obj, "App::PropertyLink", "Stairs", self.GROUP, "The Arch_Stairs to build", None)

    def arch_stairs(self, obj):
        if obj.Stairs is None:
            raise ValueError("no Arch_Stairs linked")
        return obj.Stairs

    def model(self, obj):
        stair = self.stair(obj)
        arch = self.arch_stairs(obj)
        if arch.Landings == "None":
            return stair
        if arch.Landings != "At center" or arch.Flight != "Straight":
            raise ValueError("only straight stairs, with no landing or one at the center")
        return Framing.LandingStair(
            stair,
            int(arch.NumberOfSteps) // 2,
            float(arch.LandingDepth.Value),
            lumber_section(obj.LandingJoistMaterial),
        )

    def stair(self, obj):
        max_riser = rule_set().get("stair_riser_max_mm")
        if not max_riser:
            raise ValueError("the rule set has no stair_riser_max_mm")
        arch = self.arch_stairs(obj)
        sides = [bool(arch.RailingLeft), bool(arch.RailingRight)]
        return Framing.Stair(
            total_rise=float(arch.Height.Value),
            n_risers=int(arch.NumberOfSteps),
            tread_run=float(arch.TreadDepth.Value),
            width=float(arch.Width.Value),
            max_riser=float(max_riser),
            tread_gap=float(obj.TreadGap.Value),
            nosing=float(arch.Nosing.Value),
            tread=lumber_section(obj.TreadMaterial),
            stringer=lumber_section(obj.StringerMaterial),
            max_stringer_spacing=float(obj.StringerSpacing.Value),
            max_piece=self.max_piece(obj),
            open_sides={(True, True): "both", (True, False): "left", (False, True): "right"}.get(
                tuple(sides), "none"
            ),
            handrail_height=float(obj.HandrailHeight.Value),
            rail=lumber_section(obj.RailMaterial),
            post=lumber_section(obj.PostMaterial),
            baluster=lumber_section(obj.BalusterMaterial),
            max_baluster_gap=float(obj.BalusterGap.Value),
        )

    def solids(self, obj):
        return [self.arch_stairs(obj).Shape.copy()]

    def checks(self, obj, rules):
        model = self.model(obj)
        if isinstance(model, Framing.LandingStair):
            return Checks.landing_stair(model, rules)
        return Checks.stair(model, rules)


class DeckFeature(FramingFeature):
    """Deck against a house: ledger, joists, rim, dropped beam on posts, decking."""

    IFC_TYPE = "Slab"
    GROUP = "Deck"
    _d = Framing.Deck()
    PROPERTIES = [
        _length("Length", "Along the house", _d.length),
        _length("Projection", "Out from the house face to the outside of the rim", _d.projection),
        _length("Height", "Top of the decking above grade", _d.height),
        _length("JoistSpacing", "Joist centres", _d.spacing),
        (INTEGER, "BeamPlies", "Beam plies side by side", _d.beam_plies),
        _length("Cantilever", "Joists past the beam's outer face", _d.cantilever),
        _length("PostSpacing", "Largest distance between posts", _d.max_post_spacing),
        _length("DeckingGap", "Gap between decking boards", _d.decking_gap),
        ("App::PropertyFloat", "DeckLoad", "kPa on the deck, " + LOAD_TIP, 0.0),
        (
            "App::PropertyBool",
            "Attached",
            "Ledger on the house; off = freestanding on two beams",
            _d.attached,
        ),
        (INTEGER, "BlockingRows", "Rows of blocking between the joists", _d.blocking_rows),
        _length("FootingSize", "Side of a square post footing, for the concrete", _d.footing[0]),
        _length("FootingDepth", "Depth of a post footing, for the concrete", _d.footing[1]),
        (
            ENUM,
            "Guards",
            "Guards on the open sides: auto = when the deck is higher than the rule set's "
            "guard_min_rise_mm",
            "auto",
        ),
        _length("GuardHeight", "Top of the guard rail above the decking", _d.guard_height),
        _length("GuardPostSpacing", "Largest distance between guard posts", _d.guard_post_spacing),
        _length("BalusterGap", "Largest clear gap between balusters", _d.max_baluster_gap),
    ]
    MATERIALS = [
        ("JoistMaterial", "joist", "lumber.metric.45x195", "Joists, ledger and rim"),
        ("BeamMaterial", "beam", "lumber.metric.45x195", "One beam ply"),
        ("PostMaterial", "post", "lumber.metric.95x95", "Posts"),
        ("DeckingMaterial", "decking", "lumber.metric.28x120", "Decking boards"),
        ("RailMaterial", "rail", "lumber.metric.45x70", "Guard rails"),
        ("BalusterMaterial", "baluster", "lumber.metric.45x45", "Balusters"),
    ]

    def model(self, obj):
        return Framing.Deck(
            length=float(obj.Length.Value),
            projection=float(obj.Projection.Value),
            height=float(obj.Height.Value),
            spacing=float(obj.JoistSpacing.Value),
            joist=lumber_section(obj.JoistMaterial),
            beam=lumber_section(obj.BeamMaterial),
            beam_plies=int(obj.BeamPlies),
            cantilever=float(obj.Cantilever.Value),
            post=lumber_section(obj.PostMaterial),
            max_post_spacing=float(obj.PostSpacing.Value),
            decking=lumber_section(obj.DeckingMaterial),
            decking_gap=float(obj.DeckingGap.Value),
            max_piece=self.max_piece(obj),
            attached=bool(obj.Attached),
            blocking_rows=int(obj.BlockingRows),
            footing=(float(obj.FootingSize.Value), float(obj.FootingDepth.Value)),
            guards=self.guards(obj),
            guard_height=float(obj.GuardHeight.Value),
            guard_post_spacing=float(obj.GuardPostSpacing.Value),
            rail=lumber_section(obj.RailMaterial),
            baluster=lumber_section(obj.BalusterMaterial),
            max_baluster_gap=float(obj.BalusterGap.Value),
        )

    def guards(self, obj):
        if obj.Guards != "auto":
            return obj.Guards == "yes"
        rise = rule_set().get("guard_min_rise_mm")
        return rise is not None and float(obj.Height.Value) > rise

    def concrete(self, obj):
        """[(what, m³)] of concrete to buy."""
        return [("Deck post footings", self.model(obj).concrete_m3())]

    def checks(self, obj, rules):
        return Checks.deck(
            self.model(obj),
            rules,
            self.design_values(obj, "JoistMaterial"),
            self.design_values(obj, "BeamMaterial"),
            float(obj.DeckLoad),
        )


def make_deck(doc=None, name="Deck"):
    return _make_framing(DeckFeature, name, doc)


def make_stair(doc=None, name="Stair"):
    """A stair: an Arch_Stairs of the default rise and width on cut stringers,
    and the plan object that turns it into lumber."""
    import Arch

    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    d = Framing.Stair(max_riser=float(rule_set()["stair_riser_max_mm"]))
    arch = Arch.makeStairs(
        length=d.total_run(), width=d.width, height=d.total_rise, steps=d.risers()
    )
    arch.Label = f"{name} (Arch_Stairs)"
    arch.Nosing = d.nosing
    arch.TreadThickness = d.tread[0]
    arch.Structure = "Two stringers"
    arch.StringerWidth, arch.StructureThickness = d.stringer
    plan = doc.addObject("Part::FeaturePython", name)
    StairFeature(plan)
    plan.Stairs = arch
    if FreeCAD.GuiUp:
        ViewProvider(plan.ViewObject)
        arch.ViewObject.Visibility = False  # the plan object shows the same shape
    doc.recompute()
    return plan


def _make_framing(feature, name, doc):
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    feature(obj)
    if FreeCAD.GuiUp:
        ViewProvider(obj.ViewObject)
    doc.recompute()
    return obj


def make_wall_frame(doc=None, name="WallFrame"):
    return _make_framing(WallFrameFeature, name, doc)


def make_floor_frame(doc=None, name="FloorFrame"):
    return _make_framing(FloorFrameFeature, name, doc)


def make_shed_roof(doc=None, name="ShedRoof"):
    return _make_framing(ShedRoofFeature, name, doc)


def make_gable_roof(doc=None, name="GableRoof"):
    return _make_framing(GableRoofFeature, name, doc)


def make_bim_slab(owner, length, width, thickness, name):
    """A BIM slab (an Arch_Structure of type Slab) under `owner`, its size and
    placement bound by expressions to the owner's length, width and thickness
    properties, so it follows the owner's edits and moves."""
    import Arch

    doc = owner.Document
    slab = Arch.makeStructure(length=1000, width=1000, height=100, name=name)
    slab.IfcType = "Slab"
    n = owner.Name
    slab.setExpression("Length", f"{n}.{length}")
    slab.setExpression("Width", f"{n}.{width}")
    slab.setExpression("Height", f"max({n}.{thickness}; 0.001 mm)")
    slab.setExpression(
        "Placement",
        f"{n}.Placement * create(<<placement>>; create(<<vector>>; {n}.{length} / 2; "
        f"{n}.{width} / 2; -{n}.{thickness}); create(<<rotation>>; 0; 0; 0))",
    )
    if FreeCAD.GuiUp:
        slab.ViewObject.Visibility = False  # the owner shows the slab with its edges
    doc.recompute()
    return slab


def slab_solids(owner, bim_slab, model):
    """Solids of a slab in the owner's coordinates: the BIM slab's shape (when
    the slab has thickness) and the thickened edge boxes added below it."""
    out = []
    if bim_slab is not None and model.thickness > 0:
        shape = bim_slab.Shape.copy()
        shape.Placement = owner.Placement.inverse().multiply(shape.Placement)
        out.append(shape)
    out += [
        Part.makeBox(*size, FreeCAD.Vector(*pos))
        for name, size, pos in model.boxes()
        if name == "Edge"
    ]
    return out


def slab_concrete_m3(solids):
    return sum(s.Volume for s in solids) / 1e9


class SlabFeature(FramingFeature):
    """Concrete slab on grade with a thickened edge, or a strip footing alone
    (Framing.Slab); counted as concrete, not in the cut list. The slab itself
    is a BIM slab (Arch_Structure) bound to this object's size; the thickened
    edge is added below it."""

    IFC_TYPE = "Footing"
    GROUP = "Slab"
    _d = Framing.Slab()
    PROPERTIES = [
        _length("Length", "Along local X", _d.length),
        _length("Width", "Along local Y", _d.width),
        _length("Thickness", "Slab thickness; 0 = a strip footing only", _d.thickness),
        _length("EdgeWidth", "Thickened edge or strip footing width", _d.edge_width),
        _length("EdgeDepth", "Top of the slab to the bottom of the edge", _d.edge_depth),
    ]

    def setProperties(self, obj):
        super().setProperties(obj)
        add_property(obj, "App::PropertyLink", "BimSlab", self.GROUP, "The BIM slab", None)

    def model(self, obj):
        return Framing.Slab(
            *(float(getattr(obj, p).Value) for _, p, _, _ in self.PROPERTIES)
        )

    def parts(self, obj):
        return []

    def solids(self, obj):
        return slab_solids(obj, obj.BimSlab, self.model(obj))

    def fasteners(self, obj, schedule):
        return {}

    def concrete(self, obj):
        return [("Slab and footings", slab_concrete_m3(self.solids(obj)))]

    def checks(self, obj, rules):
        return Checks.slab(self.model(obj), rules)


def make_slab(doc=None, name="Slab"):
    obj = _make_framing(SlabFeature, name, doc)
    obj.BimSlab = make_bim_slab(obj, "Length", "Width", "Thickness", f"{name} (BIM slab)")
    obj.Document.recompute()
    return obj


DEFAULT_SHEATHING = "sheet.metric.plywood.12"
FLOOR_SHEATHING = "sheet.metric.plywood.18"


class SheathingFeature:
    """Sheet goods on a framing object's surfaces (see Sheathing.py)."""

    IFC_TYPE = "Covering"

    def __init__(self, obj, material=DEFAULT_SHEATHING):
        obj.Proxy = self
        self.setProperties(obj, material)

    def setProperties(self, obj, material=DEFAULT_SHEATHING):
        add_ifc_type(obj, self)
        # "Host", not "Base": BIM's IFC export treats a Base as a sub-part and drops it.
        add_property(obj, "App::PropertyLink", "Host", "Sheathing", "Framing to cover", None)
        if "Base" in obj.PropertiesList:  # files from before the rename
            obj.Host = obj.Base
            obj.removeProperty("Base")
        add_property(
            obj, "App::PropertyBool", "Stagger", "Sheathing", "Offset every other row", True
        )
        add_library_choice(obj, "Material", Library.SHEET_GOODS, material, "Sheathing", "Sheets")
        add_library_choice(
            obj, "Covering", AREA, "none", "Sheathing", "Roofing, wrap or cladding over it"
        )

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

    def coverings(self, obj):
        """[(area material id, m²)]."""
        if obj.Covering == "none":
            return []
        return [(obj.Covering, sheathing_area(p for _, p in self.parts(obj)))]

    def _panels(self, obj):
        """[(surface, (u0, v0, du, dv))] and the sheet thickness."""
        if obj.Host is None or not isinstance(obj.Host.Proxy, FramingFeature):
            raise ValueError("Base must be a wall, floor or roof framing object")
        model = obj.Host.Proxy.model(obj.Host)
        return sheet_panels(Sheathing.surfaces(model), library_item(obj.Material), obj.Stagger)

    def parts(self, obj):
        panels, t = self._panels(obj)
        return [(obj.Material, panel_part(surface, panel, t)) for surface, panel in panels]

    def solids(self, obj):
        panels, t = self._panels(obj)
        return [panel_solid(surface, panel, t) for surface, panel in panels]

    def execute(self, obj):
        set_shape(obj, self.solids(obj))

    def checks(self, obj, rules):
        return []

    def anchored(self, obj, rules):
        return 0

    def fasteners(self, obj, schedule):
        return {}

    def dumps(self):
        return None

    def loads(self, state):
        return None


def make_sheathing(base, doc=None, name="Sheathing"):
    """Covers a framing object; follows its placement."""
    doc = doc or base.Document
    material = FLOOR_SHEATHING if isinstance(base.Proxy, FloorFrameFeature) else DEFAULT_SHEATHING
    obj = doc.addObject("Part::FeaturePython", name)
    SheathingFeature(obj, material)
    obj.Host = base
    obj.setExpression("Placement", f"{base.Name}.Placement")
    if FreeCAD.GuiUp:
        ViewProvider(obj.ViewObject)
    doc.recompute()
    return obj


class ShedFeature:
    """Gable shed template (see Shed.py): every part regenerates from its properties."""

    GROUP = "Shed"
    IFC_TYPE = "Element Assembly"
    _d = Shed.Shed()
    PROPERTIES = [
        _length("Length", "Front and back walls, outside", _d.length),
        _length("Width", "Side walls, outside", _d.width),
        _length("WallHeight", "Bottom plate to top of the top plates", _d.wall_height),
        _length(
            "DoorWidth",
            "Rough opening of the door centred in the front wall, used when Openings is empty",
            _d.door_width,
        ),
        _length("DoorHeight", "Rough opening, used when Openings is empty", _d.door_height),
        (
            "App::PropertyString",
            "Openings",
            "Doors and windows per wall (double-click the shed to edit as a list), e.g. "
            "'front: door 900x2100 @ 1350; right: window 600x600 @ 1000 sill 1200'; "
            "empty = one door centred in the front wall; none = no openings",
            "",
        ),
        (ENUM, "RoofType", "gable, or shed (mono-pitch, low at the front)", "gable"),
        ("App::PropertyAngle", "Pitch", "Roof slope (26.57 = 6 in 12)", _d.pitch),
        (ENUM, "Foundation", "floor: framed floor platform; slab: walls on a concrete slab", "floor"),
        _length("SlabThickness", "Slab thickness (Foundation slab)", _d.slab[0]),
        _length("SlabEdgeWidth", "Thickened edge width (Foundation slab)", _d.slab[1]),
        _length("SlabEdgeDepth", "Top of the slab to the bottom of the edge", _d.slab[2]),
        _length("Overhang", "Eave overhang, horizontal", _d.overhang),
        _length("StudSpacing", "Stud centres", _d.stud_spacing),
        _length("JoistSpacing", "Floor joist centres", _d.joist_spacing),
        _length("RafterSpacing", "Rafter centres", _d.rafter_spacing),
        ("App::PropertyFloat", "HeaderLoad", "kN/m on the door header, " + LOAD_TIP, 0.0),
        ("App::PropertyFloat", "FloorLoad", "kPa, " + LOAD_TIP, 0.0),
        ("App::PropertyFloat", "RoofLoad", "kPa on plan, " + LOAD_TIP, 0.0),
        (
            "App::PropertyBool",
            "ShowSheathing",
            "Show the sheathing; turn off for a framing drawing (the cut list keeps it)",
            True,
        ),
    ]
    LUMBER = [  # property, framing section, default
        ("StudMaterial", "stud", "lumber.metric.45x95"),
        ("HeaderMaterial", "header", "lumber.metric.45x195"),
        ("JoistMaterial", "joist", "lumber.metric.45x195"),
        ("RafterMaterial", "rafter", "lumber.metric.45x145"),
        ("RidgeMaterial", "ridge", "lumber.metric.45x195"),
        ("TieMaterial", "tie", "lumber.metric.45x145"),
    ]
    COVERINGS = [  # property, sheathing it goes on, tip
        ("RoofCovering", ("Roof sheathing",), "Roofing over the roof sheathing"),
        ("WallCovering", ("Wall sheathing", "Gable sheathing"), "Wrap or cladding on the walls"),
        ("WallCladding", ("Wall sheathing", "Gable sheathing"), "Siding or cladding over the wrap"),
        ("WallInsulation", ("Wall sheathing",), "Insulation between the wall studs"),
    ]
    SHEETS = [  # property, components it covers, default
        ("FloorSheet", ("Floor",), FLOOR_SHEATHING),
        ("WallSheet", ("Front wall", "Back wall", "Left wall", "Right wall"), DEFAULT_SHEATHING),
        ("RoofSheet", ("Roof",), DEFAULT_SHEATHING),
    ]

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        add_ifc_type(obj, self)
        add_property(obj, "App::PropertyLink", "FoundationSlab", self.GROUP, "The BIM slab", None)
        for ptype, prop, tip, value in self.PROPERTIES:
            add_property(obj, ptype, prop, self.GROUP, tip, value)
        for prop, section, default in self.LUMBER:
            add_library_choice(obj, prop, Library.LUMBER, default, "Lumber", section)
        for prop, covers, default in self.SHEETS:
            tip = "Sheathing on " + ", ".join(covers).lower()
            add_library_choice(obj, prop, Library.SHEET_GOODS, default, "Sheathing", tip)
        for prop, _, tip in self.COVERINGS:
            add_library_choice(obj, prop, AREA, "none", "Coverings", tip)

    def coverings(self, obj):
        """[(area material id, m²)] of the roof and wall coverings."""
        parts = [p for _, p in self.parts(obj)]
        return [
            (getattr(obj, prop), sheathing_area(p for p in parts if p.name in names))
            for prop, names, _ in self.COVERINGS
            if getattr(obj, prop) != "none"
        ]

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

    def model(self, obj):
        sizes = {section: lumber_section(getattr(obj, prop)) for prop, section, _ in self.LUMBER}
        return Shed.Shed(
            length=float(obj.Length.Value),
            width=float(obj.Width.Value),
            wall_height=float(obj.WallHeight.Value),
            door_width=float(obj.DoorWidth.Value),
            door_height=float(obj.DoorHeight.Value),
            openings=shed_openings(obj.Openings),
            roof=obj.RoofType,
            foundation=obj.Foundation,
            slab=tuple(
                float(getattr(obj, p).Value)
                for p in ("SlabThickness", "SlabEdgeWidth", "SlabEdgeDepth")
            ),
            pitch=float(obj.Pitch.Value),
            overhang=float(obj.Overhang.Value),
            stud_spacing=float(obj.StudSpacing.Value),
            joist_spacing=float(obj.JoistSpacing.Value),
            rafter_spacing=float(obj.RafterSpacing.Value),
            floor_sheet=sheet_thickness(obj.FloorSheet),
            wall_sheet=sheet_thickness(obj.WallSheet),
            max_piece=longest_stock(*(getattr(obj, prop) for prop, _, _ in self.LUMBER)),
            **sizes,
        )

    def _items(self, obj):
        """[(placement, material id, part, solid builder)] for every piece and panel."""
        lumber = {section: getattr(obj, prop) for prop, section, _ in self.LUMBER}
        lumber["gable_stud"] = obj.StudMaterial
        sheet_for = {name: prop for prop, covers, _ in self.SHEETS for name in covers}
        shed = self.model(obj)
        sizes = shed.sections()
        out = []
        for c in shed.components():
            placement = FreeCAD.Placement(
                FreeCAD.Vector(*c.origin), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), c.rotation)
            )
            for p, section in framing_pieces(c.model):
                size = sizes[section]
                out.append(
                    (placement, lumber[section], piece_part(p, size), (piece_solid, p, size))
                )
            material = getattr(obj, sheet_for[c.name])
            panels, t = sheet_panels(Shed.sheathing_surfaces(c), library_item(material), True)
            for surface, panel in panels:
                part = panel_part(surface, panel, t)
                out.append((placement, material, part, (panel_solid, surface, panel, t)))
        return out

    def parts(self, obj):
        return [(material, part) for _, material, part, _ in self._items(obj)]

    def solids(self, obj):
        shapes = []
        for placement, _, _, (build, *args) in self._items(obj):
            solid = build(*args)
            solid.Placement = placement.multiply(solid.Placement)
            shapes.append(solid)
        return shapes

    def slab_solids(self, obj):
        slab = self.model(obj).slab_model()
        return slab_solids(obj, obj.FoundationSlab, slab) if slab else []

    def concrete(self, obj):
        return [("Slab", slab_concrete_m3(self.slab_solids(obj)))] if self.model(obj).slab_model() else []

    def onChanged(self, obj, prop):
        # A shed on a slab gets a BIM slab bound to its size.
        if (
            prop == "Foundation"
            and "FoundationSlab" in obj.PropertiesList
            and obj.Foundation == "slab"
            and obj.FoundationSlab is None
            and not obj.Document.Restoring
        ):
            obj.FoundationSlab = make_bim_slab(
                obj, "Length", "Width", "SlabThickness", f"{obj.Label} (BIM slab)"
            )

    def execute(self, obj):
        solids = self.solids(obj)
        if not obj.ShowSheathing:
            parts = self.parts(obj)
            solids = [s for s, (_, p) in zip(solids, parts) if p.role != "sheathing"]
        set_shape(obj, solids + self.slab_solids(obj))

    def checks(self, obj, rules):
        def values(prop):
            return library_item(getattr(obj, prop)).get("design_values")

        out = []
        for c in self.model(obj).components():
            if isinstance(c.model, Framing.Wall):
                results = Checks.wall(
                    c.model, rules, values("HeaderMaterial"), float(obj.HeaderLoad)
                )
            elif isinstance(c.model, Framing.Floor):
                results = Checks.floor(
                    c.model, rules, values("JoistMaterial"), float(obj.FloorLoad)
                )
            elif isinstance(c.model, Framing.ShedRoof):
                results = Checks.shed_roof(
                    c.model, rules, values("RafterMaterial"), float(obj.RoofLoad), framed=True
                )
            else:
                results = Checks.roof(c.model, rules, values("RafterMaterial"), float(obj.RoofLoad))
            out += [(f"{c.name}: {check}", status, detail) for check, status, detail in results]
        slab = self.model(obj).slab_model()
        if slab:
            out += [(f"Slab: {check}", s, detail) for check, s, detail in Checks.slab(slab, rules)]
            out.append(
                (
                    "Slab: Bottom plates",
                    Checks.REQUIRED,
                    "bottom plates on concrete: preservative-treated lumber on a damp-proof "
                    "course, anchored to the slab to a design for your site; anchors are not "
                    "generated",
                )
            )
        return out

    def anchored(self, obj, rules):
        return 0

    def fasteners(self, obj, schedule):
        """Per component; joints between components (e.g. wall to floor) are not counted."""
        total = {}
        for c in self.model(obj).components():
            for hardware_id, count in Framing.fasteners(c.model, schedule).items():
                total[hardware_id] = total.get(hardware_id, 0) + count
        return total

    def dumps(self):
        return None

    def loads(self, state):
        return None


def shed_openings(text):
    """Shed openings from the Openings property: None (empty: the default
    door), () for "none", else Shed.parse_openings."""
    text = text.strip()
    if not text:
        return None
    return () if text.lower() == "none" else tuple(Shed.parse_openings(text))


def make_shed(doc=None, name="Shed"):
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    ShedFeature(obj)
    if FreeCAD.GuiUp:
        ViewProvider(obj.ViewObject)
    doc.recompute()
    return obj


def make_garage(doc=None, name="Garage"):
    """A shed on a slab with a wide door (Shed.GARAGE); its door header is an
    LVL, to be checked for your loads."""
    obj = make_shed(doc, name)
    obj.Length, obj.Width = Shed.GARAGE["length"], Shed.GARAGE["width"]
    obj.DoorWidth, obj.DoorHeight = Shed.GARAGE["door_width"], Shed.GARAGE["door_height"]
    obj.Foundation = Shed.GARAGE["foundation"]
    obj.HeaderMaterial = "lumber.metric.lvl.45x240"
    obj.Document.recompute()
    return obj


DEFAULT_BOARD = "lumber.metric.45x95"
DEFAULT_PANEL = "sheet.metric.plywood.18"


class BuildFeature:
    """Woodworking build (design doc Phase 5.1, see Build.py): the parts and
    joints are rows of two linked spreadsheets; select parts by clicking the
    solids of this one object."""

    IFC_TYPE = "Element Assembly"
    GROUP = "Build"

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        add_ifc_type(obj, self)
        for prop, tip in (
            ("PartsTable", "Spreadsheet of parts, one per row (see Build.py)"),
            ("JointsTable", "Spreadsheet of joints, one per row (see Build.py)"),
        ):
            add_property(obj, "App::PropertyLink", prop, self.GROUP, tip, None)
        add_library_choice(
            obj, "BoardStock", Library.LUMBER, DEFAULT_BOARD, self.GROUP, "Stock for new boards"
        )
        add_library_choice(
            obj,
            "PanelStock",
            Library.SHEET_GOODS,
            DEFAULT_PANEL,
            self.GROUP,
            "Stock for new panels",
        )

        add_property(obj, "App::PropertyString", "Template", self.GROUP, "Template it follows", "")
        obj.setEditorMode("Template", 1)  # read-only
        add_property(obj, "App::PropertyString", "Generated", self.GROUP, "Template rows", "")
        obj.setEditorMode("Generated", 2)  # hidden: the rows last generated, as JSON

    def onDocumentRestored(self, obj):
        self.setProperties(obj)
        self.ready = True

    # -------------------------------------------------------- templates

    def template_properties(self, obj):
        return [prop for prop, _, _ in Build.TEMPLATES[obj.Template][1]] if obj.Template else []

    def add_template_properties(self, obj, values):
        """Template parameters as properties (group "Template") with values."""
        for prop, kind, arg in Build.TEMPLATES[obj.Template][1]:
            value, tip = values[prop], arg.replace("_", " ")
            if kind == "length":
                add_property(obj, LENGTH, prop, "Template", tip, value)
            elif kind == "count":
                add_property(obj, INTEGER, prop, "Template", tip, value)
            elif kind in ("leg", "board", "optional_board"):
                add_library_choice(obj, prop, Library.LUMBER, value, "Template", tip)
            elif kind in ("sheet", "optional_sheet"):
                add_library_choice(obj, prop, Library.SHEET_GOODS, value, "Template", tip)
            elif kind == "joint":
                add_library_choice(obj, prop, "joint", value, "Template", tip, fixes_end_to_face)
            elif kind == "top_joint":
                where = lambda j: "face_to_face" in j.get("meets", ())  # noqa: E731
                add_library_choice(obj, prop, "joint", value, "Template", tip, where)

    def template_values(self, obj):
        return {
            prop: getattr(getattr(obj, prop), "Value", getattr(obj, prop))
            for prop in self.template_properties(obj)
        }

    def onChanged(self, obj, prop):
        if getattr(self, "ready", False) and prop in self.template_properties(obj):
            self.regenerate(obj)

    def regenerate(self, obj):
        """Rewrites the tables from the template's current parameters, keeping
        rows the user edited or added (see Build.merge)."""
        function = Build.TEMPLATES[obj.Template][0]
        try:
            arguments = Build.template_arguments(
                obj.Template, self.template_values(obj), lumber_section, sheet_thickness
            )
            parts, joints = function(**arguments)
        except ValueError as e:
            self.error = str(e)  # execute() reports it
            obj.touch()
            return
        self.error = None
        old = json.loads(obj.Generated) if obj.Generated else {"parts": [], "joints": []}
        merged = Build.merge(old["parts"], parts, self.part_rows(obj), lambda r: r[0])
        _rewrite_table(obj.PartsTable, Build.PARTS_HEADER, merged)
        merged = Build.merge(old["joints"], joints, self.joint_rows(obj), lambda r: tuple(r[:2]))
        _rewrite_table(obj.JointsTable, Build.JOINTS_HEADER, merged)
        obj.Generated = json.dumps({"parts": parts, "joints": joints})
        obj.touch()

    def part_rows(self, obj):
        return _table_rows(obj.PartsTable, len(Build.PARTS_HEADER))

    def joint_rows(self, obj):
        return _table_rows(obj.JointsTable, len(Build.JOINTS_HEADER))

    def _build(self, obj):
        return Build.build(self.part_rows(obj), self.joint_rows(obj), items())

    def parts(self, obj):
        return self._build(obj)[0]

    def drawn_parts(self, obj):
        """{name: Part} as the table places them, before joinery lengthens or
        cuts them: how parts meet, and where new parts go, are read from these."""
        return {row[0]: Build.part(row, items()) for row in self.part_rows(obj)}

    def solids(self, obj):
        return joined_solids(self._build(obj)[1])

    def execute(self, obj):
        if getattr(self, "error", None):
            raise ValueError(f"template: {self.error}")
        set_shape(obj, self.solids(obj))

    def checks(self, obj, rules):
        parts, result = self._build(obj)
        return Checks.build(parts, result, rules, items())

    def anchored(self, obj, rules):
        return int(Checks.build_anchored([p for _, p in self.parts(obj)], rules))

    def fasteners(self, obj, schedule):
        return self._build(obj)[1].fasteners

    def part_at(self, obj, element):
        """Index in the parts table of the part a sub-element ("Face12") lies on."""
        face = obj.Shape.getElement(element)
        for i, child in enumerate(obj.Shape.childShapes()):
            if any(face.isSame(f) for f in child.Faces):
                return i
        return None

    def add_part(self, obj, row):
        """Appends a parts-table row; returns its name."""
        sheet = obj.PartsTable
        _write_row(sheet, len(self.part_rows(obj)) + 2, list(row))
        obj.touch()
        return row[0]

    def add_joint(self, obj, receiver, inserted, joint, opts=""):
        """Appends a joints-table row; returns its row number."""
        row = len(self.joint_rows(obj)) + 2
        self.set_joint(obj, row, receiver, inserted, joint, opts)
        return row

    def set_joint(self, obj, row, receiver, inserted, joint, opts=""):
        """Writes joints-table row `row` (2 = the first joint)."""
        sheet = obj.JointsTable
        for col in "ABCD":
            sheet.clear(f"{col}{row}")
        _write_row(sheet, row, [receiver, inserted, joint, opts])
        obj.touch()

    def dumps(self):
        return None

    def loads(self, state):
        return None


def _table_rows(sheet, width):
    """Rows below the header until the first empty name; cells as numbers or text."""
    if sheet is None:
        raise ValueError("the build has no table linked")
    sheet.recompute()  # rows just written have no value until then
    used = set(sheet.getUsedCells())
    rows = []
    r = 2
    while f"A{r}" in used:
        row = []
        for c in range(width):
            cell = f"{chr(65 + c)}{r}"
            value = sheet.get(cell) if cell in used else ""
            row.append(getattr(value, "Value", value))  # a Quantity: its number
        rows.append(tuple(row))
        r += 1
    return rows


def make_build(doc=None, name="Build"):
    """A build with empty parts and joints tables."""
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    BuildFeature(obj)
    for prop, header in (("PartsTable", Build.PARTS_HEADER), ("JointsTable", Build.JOINTS_HEADER)):
        sheet = doc.addObject("Spreadsheet::Sheet", f"{obj.Name}{prop[:-5]}")
        _write_row(sheet, 1, list(header))
        setattr(obj, prop, sheet)
    if FreeCAD.GuiUp:
        ViewProvider(obj.ViewObject)
    doc.recompute()
    return obj


def make_end_table(doc=None, name="EndTable", **sizes):
    """A build from the end table template (Build.table: sizes)."""
    return make_from_template("end_table", doc, name, **sizes)


def make_dining_table(doc=None, name="DiningTable", **sizes):
    """A build filled from the dining table template (Build.dining_table: sizes)."""
    return make_from_template("dining_table", doc, name, **sizes)


def make_workbench(doc=None, name="Workbench", **sizes):
    """A build filled from the workbench template (Build.workbench: sizes)."""
    return make_from_template("workbench", doc, name, **sizes)


def make_bookcase(doc=None, name="Bookcase", **sizes):
    """A build filled from the bookcase template (Build.bookcase: sizes)."""
    return make_from_template("bookcase", doc, name, **sizes)


def make_from_template(preset, doc=None, name="Build", **sizes):
    """A build following a Build.py template preset (Build.PRESETS): its sizes
    and choices are properties (group "Template"); changing one regenerates
    the tables, keeping rows edited by hand. sizes: template arguments."""
    template, arguments = Build.preset_arguments(preset)
    values = Build.property_values(template, {**arguments, **sizes})
    build = make_build(doc, name)
    build.Template = template
    build.Proxy.add_template_properties(build, values)
    build.Proxy.regenerate(build)
    build.Proxy.ready = True
    build.Document.recompute()
    return build


def _rewrite_table(sheet, header, rows):
    """Rewrites a build table below its header: [(row, overridden)]; an
    overridden row is marked "edited" after its last column."""
    for cell in sheet.getUsedCells():
        if int("".join(c for c in cell if c.isdigit())) >= 2:
            sheet.clear(cell)
    note = chr(65 + len(header))
    for r, (row, overridden) in enumerate(rows, start=2):
        _write_row(sheet, r, list(row))
        if overridden:
            sheet.set(f"{note}{r}", "'edited")


def add_board(
    build, name=None, stock=None, length=1000, pos=(0, 0, 0), along="x", thick="z", **sizes
):
    """Adds a board (lumber) to a build; returns its name."""
    feature = build.Proxy
    names = [row[0] for row in feature.part_rows(build)]
    name = name or Build.new_name(names, "Board")
    row = (
        name,
        stock or build.BoardStock,
        length,
        sizes.get("width", ""),
        sizes.get("thickness", ""),
        *pos,
        along,
        thick,
    )
    return feature.add_part(build, row)


def add_panel(
    build, name=None, stock=None, length=500, width=500, pos=(0, 0, 0), along="x", thick="z"
):
    """Adds a panel (sheet goods) to a build; returns its name."""
    feature = build.Proxy
    names = [row[0] for row in feature.part_rows(build)]
    name = name or Build.new_name(names, "Panel")
    row = (name, stock or build.PanelStock, length, width, "", *pos, along, thick)
    return feature.add_part(build, row)


def add_on_face(build, part, axis, sign, panel=False, name=None, stock=None):
    """Adds a board (or a panel) lying on a face of the part named `part`:
    the face's normal is +/- axis (0, 1, 2 = x, y, z) in the build's
    coordinates. Returns its name."""
    p = build.Proxy.drawn_parts(build)[part]
    if panel:
        stock = stock or build.PanelStock
        length, width, x, y, z, along, thick = Build.on_face(p, axis, sign, sheet_thickness(stock))
        return add_panel(build, name, stock, length, width, (x, y, z), along, thick)
    stock = stock or build.BoardStock
    t, w = lumber_section(stock)
    length, _, x, y, z, along, thick = Build.on_face(p, axis, sign, t, w)
    return add_board(build, name, stock, length, (x, y, z), along, thick)


def move_part(build, part, axis, distance):
    """Moves the part named `part` by distance along axis (0, 1, 2 = x, y, z)
    in its parts-table row."""
    rows = build.Proxy.part_rows(build)
    r = next(n for n, row in enumerate(rows) if row[0] == part)
    cell = f"{'FGH'[axis]}{r + 2}"
    build.PartsTable.set(cell, f"{float(rows[r][5 + axis] or 0) + distance:g}")
    build.touch()


def add_board_between(build, a, b, name=None, stock=None):
    """Adds a board spanning the gap between parts named a and b."""
    parts = build.Proxy.drawn_parts(build)
    stock = stock or build.BoardStock
    section = lumber_section(stock)
    length, x, y, z, along, thick = Build.between(parts[a], parts[b], section)
    return add_board(build, name, stock, length, (x, y, z), along, thick)


class RoomFeature:
    """A measured room (Room.py): walls, openings and appliance gaps, edited in
    its panel (double-click). Generate makes and updates wall framing and
    cabinet runs from it; they stay ordinary objects to edit further."""

    IFC_TYPE = "Space"
    GROUP = "Room"

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        add_ifc_type(obj, self)
        props = [
            (LENGTH, "Height", "Floor to ceiling framing height", 2440.0),
            ("App::PropertyString", "WallsData", "Walls (JSON: [[length, turn], ...])", ""),
            ("App::PropertyString", "OpeningsData", "Openings (JSON)", "[]"),
            ("App::PropertyString", "GapsData", "Appliance gaps (JSON)", "[]"),
            ("App::PropertyString", "BaseCabinetWalls", "Walls with base cabinets, e.g. 1, 2", ""),
            ("App::PropertyString", "WallCabinetWalls", "Walls with wall cabinets, e.g. 1, 2", ""),
            ("App::PropertyBool", "FrameWalls", "Generate wall framing for every wall", False),
            (
                "App::PropertyLink",
                "Base",
                "Closed or open sketch of the walls (square corners)",
                None,
            ),
            ("App::PropertyLinkList", "Generated", "Objects made from this room", []),
        ]
        for ptype, prop, tip, value in props:
            add_property(obj, ptype, prop, self.GROUP, tip, value)
        if not obj.WallsData:
            obj.WallsData = json.dumps([[3600.0, "left"], [2400.0, "left"]])
        for prop in ("WallsData", "OpeningsData", "GapsData", "Generated"):
            obj.setEditorMode(prop, 2)  # edited in the panel

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

    def model(self, obj):
        walls = json.loads(obj.WallsData)
        if obj.Base is not None:
            wire = Part.Wire(Part.__sortEdges__(obj.Base.Shape.Edges))
            points = [(v.Point.x, v.Point.y) for v in wire.OrderedVertexes]
            if wire.isClosed():
                points.append(points[0])
            walls = Room.plan(points)
        return Room.Room(
            walls=[tuple(w) for w in walls],
            height=float(obj.Height.Value),
            openings=[tuple(o) for o in json.loads(obj.OpeningsData)],
            gaps=[tuple(g) for g in json.loads(obj.GapsData)],
        )

    def execute(self, obj):
        room = self.model(obj)
        room.validate()
        points = [FreeCAD.Vector(x, y, 0) for x, y in room.corners()]
        obj.Shape = Part.makePolygon(points)

    def generate(self, obj):
        """Makes or updates the room's wall framing and cabinet runs."""
        doc = obj.Document
        room = self.model(obj)
        keep = []

        def child(name, make):
            existing = doc.getObject(f"{obj.Name}_{name}")
            if existing is None:
                existing = make()
                existing.Label = f"{obj.Label} {name}"
            keep.append(existing)
            return existing

        def place(target, origin, local_x, z=0.0):
            angle = math.degrees(math.atan2(local_x[1], local_x[0]))
            target.Placement = FreeCAD.Placement(
                FreeCAD.Vector(origin[0], origin[1], z),
                FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), angle),
            )

        if obj.FrameWalls:
            depth = lumber_section(DEFAULT_LUMBER)[1]
            for i, (name, wall, origin, local_x, _) in enumerate(room.framing(depth)):
                frame = child(
                    f"Wall{i + 1}", lambda: make_wall_frame(doc, f"{obj.Name}_Wall{i + 1}")
                )
                frame.Length = wall.length
                frame.Height = wall.height
                frame.CornerStart, frame.CornerEnd = wall.corners
                frame.Openings = Framing.format_openings(wall.openings)
                place(frame, origin, local_x)
        for kind, prop in (("base", "BaseCabinetWalls"), ("wall", "WallCabinetWalls")):
            walls = [int(w) for w in Framing.parse_numbers(getattr(obj, prop))]
            spec = Cabinet.defaults(kind)
            depth = spec.depth + spec.thickness  # with the fronts
            for w, entries, origin, local_x in room.runs(walls, depth, upper=kind == "wall"):
                label = "Base" if kind == "base" else "Upper"
                run = child(
                    f"{label}{w}",
                    lambda: make_cabinet_run(kind, doc, f"{obj.Name}_{label}{w}"),
                )
                run.Length = room.walls[w - 1][0]
                run.Widths = Cabinet.format_entries(
                    [e[0] for e in entries], [e[1] for e in entries]
                )
                ny, nx = local_x[0], -local_x[1]  # outward = local y
                back = (origin[0] - nx * spec.depth, origin[1] - ny * spec.depth)
                place(run, back, local_x, Cabinet.WALL_ELEVATION if kind == "wall" else 0.0)
        for old in obj.Generated:
            if old not in keep:
                doc.removeObject(old.Name)
        obj.Generated = keep
        doc.recompute()
        return keep

    def dumps(self):
        return None

    def loads(self, state):
        return None


def make_room(doc=None, name="Room"):
    """A measured room (an open L of two walls to start with)."""
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    RoomFeature(obj)
    if FreeCAD.GuiUp:
        ViewProvider(obj.ViewObject)
    doc.recompute()
    return obj


def construction_objects(doc):
    kinds = (
        CabinetFeature,
        MemberFeature,
        FramingFeature,
        SheathingFeature,
        ShedFeature,
        BuildFeature,
    )
    return [o for o in doc.Objects if isinstance(getattr(o, "Proxy", None), kinds)]


PARAMS = "User parameter:BaseApp/Preferences/Mod/Construction"


def rule_set():
    """The rule set chosen in preferences Mod/Construction/RuleSet."""
    rule_id = FreeCAD.ParamGet(PARAMS).GetString("RuleSet", "rules.generic-example")
    return library_item(rule_id)


def write_checks(doc):
    """Writes advisory checks of every construction object to spreadsheet 'Checks'."""
    rules = rule_set()
    sheet = _sheet(doc, "Checks")
    _write_row(sheet, 1, [Checks.DISCLAIMER])
    _write_row(sheet, 2, [f"Rule set: {rules.get('name', rules['id'])}"])
    _write_row(sheet, 4, ["Object", "Check", "Status", "Detail"])
    row, problems = 5, 0
    for obj in construction_objects(doc):
        for check, status, detail in obj.Proxy.checks(obj, rules):
            _write_row(sheet, row, [obj.Label, check, status, detail])
            row += 1
            if status in (Checks.WARNING, Checks.REQUIRED):
                problems += 1
                FreeCAD.Console.PrintWarning(f"{obj.Label}: {check}: {detail}\n")
    doc.recompute()
    return problems


def fastening_schedule():
    """Joinery rules of the schedule chosen in preferences Mod/Construction/FasteningSchedule."""
    schedule_id = FreeCAD.ParamGet(PARAMS).GetString(
        "FasteningSchedule", "fastening.generic-example"
    )
    return [Joinery.Rule(**r) for r in library_item(schedule_id)["rules"]]


def saw_settings():
    """(kerf, trim) in mm from preferences: Mod/Construction/Kerf and /Trim."""
    params = FreeCAD.ParamGet(PARAMS)
    return params.GetFloat("Kerf", 3.2), params.GetFloat("Trim", 10.0)


def _sheet(doc, name):
    sheet = doc.getObject(name) or doc.addObject("Spreadsheet::Sheet", name)
    sheet.clearAll()
    return sheet


def _text(value):
    return "'" + str(value)  # force text, never a formula


def _write_row(sheet, row, values):
    for col, value in enumerate(values):
        if value == "":
            continue  # leave the cell empty
        cell = f"{chr(65 + col)}{row}"
        sheet.set(cell, _text(value) if isinstance(value, str) else f"{value:g}")


def write_cut_list(doc):
    """Writes the cut list, sheet and lumber counts and hardware of every
    construction object to the spreadsheet 'CutList', the panel-saw layout to
    'SheetLayout' with a flat drawing in 'SheetLayoutView', and the lumber
    cutting plan to 'LumberPlan'."""
    parts = [mp for obj in construction_objects(doc) for mp in obj.Proxy.parts(obj)]
    rows = CutList.rows(parts)
    lib = items()
    kerf, trim = saw_settings()

    def label(material):
        return lib.get(material, {}).get("name", material)

    cut = _sheet(doc, "CutList")
    headers = [
        "Material",
        "Part",
        "Length (mm)",
        "Width (mm)",
        "Thickness (mm)",
        "Grain",
        "Qty",
        "Tag",
        "Operations",
        "Cost",
    ]
    _write_row(cut, 1, headers)
    cut.setColumnWidth("A", 240)  # material names are long
    cut.setColumnWidth("B", 150)
    cut.setColumnWidth("I", 300)
    operations = CutList.operations(parts)
    for r, (material, name, length, width, thick, grain, qty) in enumerate(rows, start=2):
        # Tag: the row number, used by the balloons on drawings (CutList.row_numbers).
        values = [label(material), name, length, width, thick, grain, qty, r - 1]
        _write_row(cut, r, values + [operations[r - 2]])

    def of_category(cut_rows, category):
        materials = sorted({r[0] for r in cut_rows})
        return [m for m in materials if lib.get(m, {}).get("category") == category]

    # Shop parts are cut from trimmed sheets; sheathing is cut against the
    # factory edges (no trim) and laid out separately.
    shop = CutList.rows(mp for mp in parts if mp[1].role != "sheathing")
    sheathing = CutList.rows(mp for mp in parts if mp[1].role == "sheathing")
    groups = [
        (shop, of_category(shop, Library.SHEET_GOODS), trim, ""),
        (sheathing, of_category(sheathing, Library.SHEET_GOODS), 0.0, " (sheathing)"),
    ]
    costs = []  # every priced line; None for a line without a price

    def line(values, cost):
        nonlocal summary
        summary += 1
        costs.append(cost)
        _write_row(cut, summary, values + ["", ""] + ([round(cost, 2)] if cost is not None else []))

    summary = len(rows) + 3
    _write_row(cut, summary, [f"Sheets (panel-saw layout, kerf {kerf:g} mm, trim {trim:g} mm)"])
    for material, suffix, count, share in _write_sheet_layouts(doc, groups, lib, label, kerf):
        name = label(material) + suffix
        line(
            [name, f"{share:.0%} used", "", "", "", "", count], CutList.price(lib[material], count)
        )
    summary += 2
    _write_row(cut, summary, [f"Lumber (stock lengths, kerf {kerf:g} mm)"])
    volumes = {}
    for material, stock, count in _write_lumber_plan(
        doc, rows, of_category(rows, Library.LUMBER), lib, label, kerf
    ):
        item = lib[material]
        line(
            [label(material), f"{stock:g} mm", "", "", "", "", count],
            CutList.price(item, count, stock),
        )
        m3, bf = volumes.get(material, (0.0, 0.0))
        volumes[material] = (
            m3 + count * CutList.volume_m3(item, stock),
            bf + count * CutList.board_feet(item, stock),
        )
    for material, (m3, bf) in volumes.items():
        summary += 1
        _write_row(cut, summary, [label(material), f"bought: {m3:.3f} m³ = {bf:.1f} board feet"])
    coverings = {}
    for obj in construction_objects(doc):
        for covering, area in getattr(obj.Proxy, "coverings", lambda o: [])(obj):
            coverings[covering] = coverings.get(covering, 0.0) + area
    concrete = [
        (f"{obj.Label}: {what}", m3)
        for obj in construction_objects(doc)
        for what, m3 in getattr(obj.Proxy, "concrete", lambda o: [])(obj)
        if m3 > 0
    ]
    if concrete:
        summary += 2
        _write_row(cut, summary, ["Concrete"])
        for what, m3 in concrete:
            summary += 1
            _write_row(cut, summary, [what, f"{m3:.2f} m³"])
    if coverings:
        summary += 2
        _write_row(cut, summary, ["Coverings (area with the item's waste allowance)"])
        for covering, area in sorted(coverings.items()):
            item = lib[covering]
            units = CutList.covering_units(item, area)
            line(
                [item["name"], f"{area:.1f} m²", "", "", "", "", units], CutList.price(item, units)
            )
    summary += 2
    _write_row(cut, summary, ["Hardware"])
    rules = rule_set()
    anchored = sum(obj.Proxy.anchored(obj, rules) for obj in construction_objects(doc))
    schedule = fastening_schedule()
    fasteners = {}
    for obj in construction_objects(doc):
        for hardware_id, count in obj.Proxy.fasteners(obj, schedule).items():
            fasteners[hardware_id] = fasteners.get(hardware_id, 0) + count
    hardware = CutList.hardware(lib, anchored, fasteners)
    hardware_costs = CutList.hardware_costs(lib, anchored, fasteners)
    for name, qty in hardware:
        line([name, "", "", "", "", "", qty], hardware_costs.get(name))
    priced = [c for c in costs if c is not None]
    if priced:
        summary += 2
        missing = len(costs) - len(priced)
        note = (
            f"{missing} line(s) without a price in the library" if missing else "all lines priced"
        )
        _write_row(
            cut, summary, ["Total cost", note, "", "", "", "", "", "", "", round(sum(priced), 2)]
        )
    doc.recompute()
    return cut


def _write_sheet_layouts(doc, groups, lib, label, kerf):
    """Lays out sheet materials. groups: [(cut rows, materials, trim, label suffix)].
    Each sheet is a BIM panel sheet (Arch_Panel_Sheet) holding its placed parts,
    in the group 'SheetLayoutView'. Returns [(material, suffix, sheets, share used)]."""
    layout = _sheet(doc, "SheetLayout")
    _write_row(
        layout,
        1,
        ["Material", "Sheet", "Part", "X (mm)", "Y (mm)", "Across (mm)", "Along (mm)", "Rotated"],
    )
    import Arch

    group = doc.getObject("SheetLayoutView") or doc.addObject(
        "App::DocumentObjectGroup", "SheetLayoutView"
    )
    for old in list(group.Group):  # lay out afresh: drop the earlier sheets and their parts
        for piece in getattr(old, "Group", []):
            doc.removeObject(piece.Name)
        doc.removeObject(old.Name)
    offset, row, out = 0.0, 2, []
    for rows, material, trim, suffix in (
        (rows, m, trim, suffix) for rows, materials, trim, suffix in groups for m in materials
    ):
        item = lib[material]
        sheet_w, sheet_h = Library.mm(item, "w"), Library.mm(item, "h")
        sheets = CutList.layout_sheets(
            CutList.pieces(rows, material),
            sheet_w,
            sheet_h,
            kerf=kerf,
            trim=trim,
            grain_locked=item.get("grain_axis") is not None,
        )
        used = sum(p.w * p.h for placed in sheets for p in placed)
        out.append((material, suffix, len(sheets), used / (len(sheets) * sheet_w * sheet_h)))
        for number, placed in enumerate(sheets, start=1):
            panels = []
            for p in placed:
                rotated = "yes" if p.rotated else "no"
                _write_row(
                    layout,
                    row,
                    [label(material) + suffix, number, p.name, p.x, p.y, p.w, p.h, rotated],
                )
                # The sheet's coordinates are centred on the sheet.
                corner = FreeCAD.Vector(p.x - sheet_w / 2, p.y - sheet_h / 2, 0)
                piece = doc.addObject("Part::Feature", "SheetPart")
                piece.Label = p.name
                piece.Shape = Part.makePlane(p.w, p.h, corner).OuterWire
                panels.append(piece)
                row += 1
            sheet = Arch.makePanelSheet(panels, f"{label(material)}{suffix} sheet {number}")
            sheet.Width, sheet.Height = sheet_w, sheet_h
            sheet.Placement.Base = FreeCAD.Vector(offset + sheet_w / 2, sheet_h / 2, 0)
            group.addObject(sheet)
            offset += sheet_w + 200.0  # sheets side by side, 200 mm apart
    return out


def _write_lumber_plan(doc, rows, materials, lib, label, kerf):
    """Plans lumber cuts; returns (material, stock length, boards) per stock length."""
    plan = _sheet(doc, "LumberPlan")
    _write_row(plan, 1, ["Material", "Board", "Stock (mm)", "Cuts", "Offcut (mm)"])
    row, out = 2, []
    for material in materials:
        pieces = [(name, length) for name, length, _, _ in CutList.pieces(rows, material)]
        boards = CutList.plan_lengths(pieces, lib[material]["stock_lengths_mm"], kerf=kerf)
        for number, board in enumerate(boards, start=1):
            cuts = ", ".join(f"{name} {length:g}" for name, length in board.cuts)
            _write_row(plan, row, [label(material), number, board.stock, cuts, board.offcut()])
            row += 1
        for stock in sorted({b.stock for b in boards}, reverse=True):
            out.append((material, stock, sum(1 for b in boards if b.stock == stock)))
    return out


DRAWING_TEMPLATE = ("Mod", "TechDraw", "Templates", "ISO", "A3_Landscape_ISO5457_minimal.svg")
TAGS_PER_COLUMN = 16  # bubbles in one column before a new one starts
TAG_GAP = 1 / 7  # spacing between bubbles, as a share of the view's height


def _page(doc, name, title):
    page = doc.addObject("TechDraw::DrawPage", name)
    template = doc.addObject("TechDraw::DrawSVGTemplate", name + "Template")
    template.Template = os.path.join(FreeCAD.getResourceDir(), *DRAWING_TEMPLATE)
    texts = template.EditableTexts
    texts.update(
        {
            "title": title,
            "part_material": "Timber and sheet goods: see the cut list",
            "document_type": "Construction drawing",
            # The template's sample entries: left for the user to fill in.
            "creator": "",
            "approval_person": "",
            "general_tolerances": "",
            "revision_index": "",
            "sheet_number": "",
        }
    )
    template.EditableTexts = texts
    page.Template = template
    return page


def make_drawing(objects, doc=None):
    """Framing drawing of construction objects: an A3 page with front, top and
    right views in a projection group and member tags (balloons) numbered like
    the cut list's Tag column, and a second page with the cut list table.
    Returns the views page."""
    if not objects:
        raise ValueError("select the construction objects to draw")
    doc = doc or objects[0].Document
    title = ", ".join(o.Label for o in objects)
    page = _page(doc, "FramingDrawing", title)
    group = doc.addObject("TechDraw::DrawProjGroup", "FramingViews")
    page.addView(group)
    group.X, group.Y = 170, 160  # left of centre: the tags stand to its right
    group.Source = list(objects)
    # A set scale, not "Automatic" (which TechDraw settles only once the page
    # is shown): front and right side by side, top above, on an A3 sheet.
    box = _bound_box(objects)
    group.ScaleType = "Custom"
    group.Scale = fit_scale([(box.XLength + box.YLength, box.ZLength + box.YLength)], [(300, 200)])
    _set_scale_text(page, group.Scale)
    group.addProjection("Front")
    group.Anchor.Direction = FreeCAD.Vector(0, -1, 0)  # looking at the front (y = 0) face
    group.Anchor.RotationVector = FreeCAD.Vector(1, 0, 0)
    group.Anchor.recompute()
    group.addProjection("Top")
    group.addProjection("Right")

    sheet = write_cut_list(doc)
    parts = [mp for obj in construction_objects(doc) for mp in obj.Proxy.parts(obj)]
    table_page = _page(doc, "FramingCutList", title + ": cut list")
    table = doc.addObject("TechDraw::DrawViewSpreadsheet", "CutListTable")
    table.Source = sheet
    table.CellStart = "A1"
    table.CellEnd = f"I{len(CutList.rows(parts)) + 1}"
    table_page.addView(table)
    doc.recompute()
    _add_tags(page, group.Anchor, objects)
    _add_overall_dimensions(page, group.Anchor)
    _section_page(doc, objects, group.Anchor, title)
    doc.recompute()
    return page


SCALES = (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000)


def _set_scale_text(page, scale):
    """The title block's scale field, e.g. "1 : 50"."""
    texts = page.Template.EditableTexts
    texts["scale"] = f"1 : {round(1 / scale):d}"
    page.Template.EditableTexts = texts


def fit_scale(sizes, room):
    """The largest standard drawing scale 1:n at which every (width, height)
    in sizes (mm) fits its (width, height) in room (mm)."""
    for n in SCALES:
        if all(w / n <= rw and h / n <= rh for (w, h), (rw, rh) in zip(sizes, room)):
            return 1.0 / n
    return 1.0 / SCALES[-1]


def _bound_box(objects):
    box = objects[0].Shape.BoundBox
    for obj in objects[1:]:
        box.add(obj.Shape.BoundBox)
    return box


def _view_vertices(view, wait=10.0):
    """[(index, x, y)] of a TechDraw view's vertices (unscaled view coordinates).
    With the GUI up, TechDraw finds the lines in a background thread: wait up
    to `wait` seconds for them."""
    if FreeCAD.GuiUp:
        import time

        from PySide import QtGui

        end = time.time() + wait
        while time.time() < end and not _vertex_count(view):
            QtGui.QApplication.processEvents()
            time.sleep(0.05)
    out, i = [], 0
    while True:
        try:
            p = view.getVertexByIndex(i).Point
        except Exception:  # past the last vertex
            return out
        out.append((i, p.x, p.y))
        i += 1


def _vertex_count(view):
    try:
        view.getVertexByIndex(0)
        return 1
    except Exception:  # no lines yet
        return 0


def _add_overall_dimensions(page, view):
    """Overall width and height dimensions on a view, between its extreme vertices."""
    points = _view_vertices(view)
    if len(points) < 2:
        return []
    doc = page.Document
    out = []
    for name, kind, low, high in (
        (
            "OverallWidth",
            "DistanceX",
            min(points, key=lambda q: (q[1], q[2])),
            max(points, key=lambda q: (q[1], -q[2])),
        ),
        (
            "OverallHeight",
            "DistanceY",
            min(points, key=lambda q: (q[2], -q[1])),
            max(points, key=lambda q: (q[2], q[1])),
        ),
    ):
        dim = doc.addObject("TechDraw::DrawViewDimension", name)
        dim.Type = kind
        dim.MeasureType = "Projected"
        dim.FormatSpec = "%.0f"  # whole millimetres
        dim.References2D = [(view, f"Vertex{low[0]}"), (view, f"Vertex{high[0]}")]
        page.addView(dim)
        # Beside the view, 16 mm clear of it on paper (X, Y in page millimetres).
        xs, ys = [q[1] for q in points], [q[2] for q in points]
        clear = 16 / view.getScale()
        if kind == "DistanceX":
            dim.X, dim.Y = (min(xs) + max(xs)) / 2 * view.getScale(), (
                min(ys) - clear
            ) * view.getScale()
        else:
            dim.X, dim.Y = (min(xs) - clear) * view.getScale(), (
                min(ys) + max(ys)
            ) / 2 * view.getScale()
        out.append(dim)
    return out


def _section_page(doc, objects, base, title):
    """A page with section A-A across the middle of the objects, seen from
    the right, with its overall dimensions."""
    page = _page(doc, "FramingSection", title + ": section A-A")
    box = _bound_box(objects)
    section = doc.addObject("TechDraw::DrawViewSection", "SectionA")
    section.BaseView = base
    section.Source = list(objects)
    section.SectionNormal = FreeCAD.Vector(1, 0, 0)
    section.Direction = FreeCAD.Vector(1, 0, 0)
    section.XDirection = FreeCAD.Vector(0, 1, 0)
    section.SectionOrigin = box.Center
    section.SectionSymbol = "A"
    # A set scale ("Automatic" makes a section view recompute forever here).
    section.ScaleType = "Custom"
    section.Scale = fit_scale([(box.YLength, box.ZLength)], [(330, 220)])
    _set_scale_text(page, section.Scale)
    page.addView(section)
    section.X, section.Y = 200, 150
    doc.recompute()
    _add_overall_dimensions(page, section)
    return page


def write_part_labels(doc):
    """Spreadsheet 'PartLabels': one row per piece to cut (not grouped), for
    printing labels: tag (the cut list row), object, part, size, material,
    grain and operations."""
    every = construction_objects(doc)
    pairs = [(obj, mp) for obj in every for mp in obj.Proxy.parts(obj)]
    tags = CutList.row_numbers(mp for _, mp in pairs)
    sheet = _sheet(doc, "PartLabels")
    header = [
        "Tag",
        "Object",
        "Part",
        "Length",
        "Width",
        "Thickness",
        "Material",
        "Grain",
        "Operations",
    ]
    _write_row(sheet, 1, header)
    lib = items()
    for r, ((obj, (material, part)), tag) in enumerate(zip(pairs, tags), start=2):
        length, width, thick = (round(v, 1) for v in part.cut_size())
        name = lib.get(material, {}).get("name", material)
        grain = "yes" if part.grain else "no"
        ops = "; ".join(part.operations)
        _write_row(sheet, r, [tag, obj.Label, part.name, length, width, thick, name, grain, ops])
    doc.recompute()
    return sheet


def export_csv(doc, folder):
    """Writes the cut list and the part labels as CSV files into folder;
    returns their paths."""
    write_cut_list(doc)
    write_part_labels(doc)
    paths = []
    for name in ("CutList", "PartLabels"):
        path = os.path.join(folder, f"{doc.Name}-{name}.csv")
        doc.getObject(name).exportFile(path)
        paths.append(path)
    return paths


STEP_LIMIT = 8  # build-sequence pages hold this many steps


def build_steps(parts, lows=None):
    """Assembly order of named parts: parts grouped by name without its
    number ("Leg 3" -> "Leg"), groups ordered bottom up (by their lowest part:
    lows[i], else the part's own z), at most STEP_LIMIT steps (neighbouring
    groups merged). Returns [(step names, part indices)]."""
    lows = lows or [p.pos[2] for p in parts]
    import re

    groups = {}
    for i, p in enumerate(parts):
        stem = re.sub(r"\s*\d+$", "", p.name)
        groups.setdefault(stem, []).append(i)
    order = sorted(groups, key=lambda s: (round(min(lows[i] for i in groups[s]), 1), s))
    per = -(-len(order) // STEP_LIMIT)  # groups per step
    steps = []
    for k in range(0, len(order), per):
        names = order[k : k + per]
        steps.append((names, [i for s in names for i in groups[s]]))
    return steps


def make_build_steps(obj):
    """Build-sequence views of a construction object: a page of iso views,
    each step adding the next groups of parts (build_steps), with the
    cumulative shapes in a hidden group 'BuildSteps'."""
    doc = obj.Document
    parts = [p for _, p in obj.Proxy.parts(obj)]
    solids = obj.Proxy.solids(obj)
    steps = build_steps(parts, [solid.BoundBox.ZMin for solid in solids])
    group = doc.getObject(f"{obj.Name}Steps") or doc.addObject(
        "App::DocumentObjectGroup", f"{obj.Name}Steps"
    )
    for child in list(group.Group):
        doc.removeObject(child.Name)
    page = _page(doc, f"{obj.Name}Sequence", f"{obj.Label}: build sequence")
    shown = []
    columns = 4
    box = obj.Shape.BoundBox  # an iso view spans about the box's diagonal
    diagonal = (box.XLength**2 + box.YLength**2 + box.ZLength**2) ** 0.5
    scale = fit_scale([(diagonal, diagonal)], [(85, 85)])
    for n, (names, indices) in enumerate(steps, start=1):
        shown += indices
        step = doc.addObject("Part::Feature", f"{obj.Name}Step{n}")
        shapes = [solids[i].copy() for i in shown]
        compound = Part.makeCompound(shapes)
        compound.Placement = obj.Placement.multiply(compound.Placement)
        step.Shape = compound
        step.Label = f"Step {n}: {', '.join(names)}"
        group.addObject(step)
        if FreeCAD.GuiUp:
            step.ViewObject.Visibility = False
        view = doc.addObject("TechDraw::DrawViewPart", f"{obj.Name}StepView{n}")
        view.Source = [step]
        view.Direction = FreeCAD.Vector(1, -1, 1)
        view.ScaleType = "Custom"
        view.Scale = scale  # one scale for every step
        view.Caption = step.Label
        page.addView(view)  # addView places the view; the grid position comes after
        view.X = 60 + ((n - 1) % columns) * 95
        view.Y = 220 - ((n - 1) // columns) * 110
    doc.recompute()
    return page


def _add_tags(page, view, objects):
    """One balloon per cut-list row of framing members on the front view,
    numbered like the cut list's Tag column, pointing at the instance nearest
    the viewer. Bubbles stand in a column right of the view, centred on it,
    TAG_GAP of the view's height apart (spacing follows the view, not the page
    scale, which TechDraw settles only after the page is shown); more than
    TAGS_PER_COLUMN start a new column. Balloon coordinates are
    unscaled view coordinates: the
    projected point minus the projected centre of the view's sources' bounding
    box."""
    doc = page.Document
    every = construction_objects(doc)
    pairs = [(obj, mp) for obj in every for mp in obj.Proxy.parts(obj)]
    tags = iter(CutList.row_numbers(mp for _, mp in pairs))
    nearest = {}  # tag -> world point of its front-most instance
    for obj in every:
        for (_, part), solid in zip(obj.Proxy.parts(obj), obj.Proxy.solids(obj)):
            tag = next(tags)
            if obj not in objects or part.role == "sheathing":
                continue
            centre = obj.Placement.multVec(solid.BoundBox.Center)
            if tag not in nearest or centre.y < nearest[tag].y:
                nearest[tag] = centre
    if not nearest:
        return []
    box = objects[0].Shape.BoundBox
    for obj in objects[1:]:
        box.add(obj.Shape.BoundBox)
    centre = view.projectPoint(box.Center)
    corners = [
        view.projectPoint(FreeCAD.Vector(x, y, z)) - centre
        for x in (box.XMin, box.XMax)
        for y in (box.YMin, box.YMax)
        for z in (box.ZMin, box.ZMax)
    ]
    right = max(c.x for c in corners)
    top, bottom = max(c.y for c in corners), min(c.y for c in corners)
    per_column = TAGS_PER_COLUMN
    # At least 14 mm apart on paper, so the bubbles do not overlap.
    gap = max((top - bottom) * TAG_GAP, 14 / view.getScale())
    rows = min(per_column, len(nearest))
    first = (top + bottom) / 2 + (rows - 1) * gap / 2  # column centred on the view
    origins = sorted(
        ((tag, view.projectPoint(p) - centre) for tag, p in nearest.items()),
        key=lambda t: -t[1].y,
    )
    balloons = []
    for i, (tag, origin) in enumerate(origins):
        column, slot = divmod(i, per_column)
        balloon = doc.addObject("TechDraw::DrawViewBalloon", f"Tag{tag}")
        balloon.SourceView = view
        balloon.OriginX = origin.x
        balloon.OriginY = origin.y
        balloon.Text = str(tag)
        balloon.X = right + 2 * gap + column * 1.5 * gap
        balloon.Y = first - slot * gap
        page.addView(balloon)
        balloons.append(balloon)
    return balloons

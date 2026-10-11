# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: parametric construction objects (design doc §5.4, §5.6).

import os
from dataclasses import replace

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
import Sheathing
import Shed

DEFAULT_MATERIALS = {
    "CarcassMaterial": "sheet.metric.plywood.18",
    "BackMaterial": "sheet.metric.plywood.6",
    "DrawerMaterial": "sheet.metric.plywood.12",
}
MATERIAL_TIPS = {
    "CarcassMaterial": "Sides, bottom, top, shelves, fronts, plinth, fillers",
    "BackMaterial": "Back panel and drawer bottoms",
    "DrawerMaterial": "Drawer box sides, fronts and backs",
}
# Cabinet part role -> material property; anything else uses CarcassMaterial.
ROLE_MATERIAL = {
    "back": "BackMaterial",
    "drawer_bottom": "BackMaterial",
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
]
CHOICES = {
    "Kind": Cabinet.KINDS,
    "Fronts": Cabinet.FRONTS,
    "FillerSide": Cabinet.FILLER_SIDES,
    "BlindSide": Cabinet.BLIND_SIDES,
    "OpenSides": Framing.OPEN_SIDES,
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


def add_library_choice(obj, prop, category, default, group, tip):
    """Enumeration of library item ids of one category. A value whose item is
    gone (user library changed) stays selectable and fails in execute()."""
    ids = [i["id"] for i in Library.of_category(items(), category)]
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


def member_part(name, start, end, section):
    """Cut-list Part of a member: grain along its length."""
    length = Member.frame(start, end)[0]
    return Parts.Part(name, "member", (*section, length), (0, 0, 0), "z")


def lumber_section(material_id):
    """(thickness, depth) in mm."""
    item = library_item(material_id)
    return Library.mm(item, "w"), Library.mm(item, "h")


def member_box(start, end, roll, section):
    """Solid of a member (see Member.py), placed in the object's coordinates."""
    length, x, y, z = Member.frame(start, end, roll)
    w, h = section
    box = Part.makeBox(w, h, length, FreeCAD.Vector(-w / 2, -h / 2, 0))
    V = FreeCAD.Vector
    box.Placement = FreeCAD.Placement(V(*start), FreeCAD.Rotation(V(*x), V(*y), V(*z), "ZXY"))
    return box


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
        return Cabinet.Cabinet(**kwargs)

    def model_parts(self, obj):
        return self.spec(obj).parts()

    def cabinets(self, obj):
        return [self.spec(obj)]

    def checks(self, obj, rules):
        return [r for c in self.cabinets(obj) for r in Checks.cabinet(c, rules)]

    def fasteners(self, obj, schedule):
        return {}

    def anchored(self, obj, rules):
        """Cabinets to fix to the wall."""
        kinds = rules.get("anchor_cabinet_kinds", ())
        return sum(1 for c in self.cabinets(obj) if c.kind in kinds)

    def parts(self, obj):
        """[(material id, Part)] for the cut list."""
        return [
            (getattr(obj, ROLE_MATERIAL.get(p.role, "CarcassMaterial")), p)
            for p in self.model_parts(obj)
        ]

    def solids(self, obj):
        """Solids in the order of parts(), in the object's coordinates."""
        return [Part.makeBox(*p.size, FreeCAD.Vector(*p.pos)) for p in self.model_parts(obj)]

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

    def model_parts(self, obj):
        return self.run(obj).parts()

    def cabinets(self, obj):
        run = self.run(obj)
        widths, _, _ = run.layout()
        styles = list(run.styles) + [None] * (len(widths) - len(run.styles))
        return [Cabinet.styled(replace(run.cabinet, width=w), s) for w, s in zip(widths, styles)]

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
        obj.ViewObject.Proxy = 0
    doc.recompute()
    return obj


def make_cabinet(preset="base", doc=None):
    """preset: a cabinet kind or "corner" (see Cabinet.DEFAULTS)."""
    return _make(CabinetFeature, preset, preset.capitalize() + "Cabinet", doc)


def make_cabinet_run(preset="base", doc=None):
    return _make(CabinetRunFeature, preset, preset.capitalize() + "Run", doc)


class MemberFeature:
    """Lumber member along a line: a linked straight edge (Base), or Start to End."""

    IFC_TYPE = "Member"

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        add_ifc_type(obj, self)
        props = [
            ("App::PropertyLinkSub", "Base", "Line or straight edge to follow; empty = Start/End"),
            ("App::PropertyVector", "Start", "Start point when Base is empty"),
            ("App::PropertyVector", "End", "End point when Base is empty"),
            ("App::PropertyAngle", "Roll", "Turns the profile about the member axis (90 = flat)"),
        ]
        for ptype, prop, tip in props:
            if prop not in obj.PropertiesList:
                obj.addProperty(ptype, prop, "Member", tip)
        if obj.Start == obj.End:
            obj.End = FreeCAD.Vector(0, 0, 2400)  # a stud
        add_library_choice(obj, "Material", Library.LUMBER, DEFAULT_LUMBER, "Member", "Lumber size")

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

    def endpoints(self, obj):
        if obj.Base:
            source, subs = obj.Base
            edge = source.Shape.getElement(subs[0]) if subs else source.Shape.Edges[0]
            if edge.Curve.TypeId != "Part::GeomLine":
                raise ValueError("members follow straight edges only")
            return tuple(edge.Vertexes[0].Point), tuple(edge.Vertexes[-1].Point)
        return tuple(obj.Start), tuple(obj.End)

    def parts(self, obj):
        start, end = self.endpoints(obj)
        return [(obj.Material, member_part(obj.Label, start, end, lumber_section(obj.Material)))]

    def checks(self, obj, rules):
        return []

    def anchored(self, obj, rules):
        return 0

    def fasteners(self, obj, schedule):
        return {}

    def solids(self, obj):
        start, end = self.endpoints(obj)
        return [member_box(start, end, obj.Roll.Value, lumber_section(obj.Material))]

    def execute(self, obj):
        set_shape(obj, self.solids(obj))

    def dumps(self):
        return None

    def loads(self, state):
        return None


DEFAULT_LUMBER = "lumber.metric.45x95"


def make_member(base=None, doc=None, name="Member"):
    """base: (object, "EdgeN") to follow, or None for a free member."""
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    MemberFeature(obj)
    if base:
        obj.Base = base
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = 0
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
    ]
    MATERIALS = [("JoistMaterial", "joist", "lumber.metric.45x195", "Joists and rims")]

    def model(self, obj):
        return Framing.Floor(
            length=float(obj.Length.Value),
            width=float(obj.Width.Value),
            spacing=float(obj.JoistSpacing.Value),
            joist=lumber_section(obj.JoistMaterial),
            max_piece=self.max_piece(obj),
        )

    def checks(self, obj, rules):
        values = self.design_values(obj, "JoistMaterial")
        return Checks.floor(self.model(obj), rules, values, float(obj.FloorLoad))


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


class StairFeature(FramingFeature):
    """Straight stair on cut stringers; the riser limit comes from the rule set."""

    IFC_TYPE = "Stair"
    GROUP = "Stair"
    _d = Framing.Stair()
    PROPERTIES = [
        _length("TotalRise", "Finished floor to finished floor", _d.total_rise),
        _length("Width", "Outside of the stringers", _d.width),
        (INTEGER, "TreadBoards", "Boards per tread: the run follows from them", _d.tread_boards),
        _length("TreadGap", "Gap between tread boards", _d.tread_gap),
        _length("Nosing", "Tread overhang past the riser face", _d.nosing),
        _length("StringerSpacing", "Largest distance between stringers", _d.max_stringer_spacing),
        (ENUM, "OpenSides", "Sides without a wall: they get a guard", _d.open_sides),
        _length("HandrailHeight", "Top of the handrail above the nosings", _d.handrail_height),
        _length("BalusterGap", "Largest clear gap between balusters", _d.max_baluster_gap),
    ]
    MATERIALS = [
        ("StringerMaterial", "stringer", "lumber.metric.45x220", "Stringers (cut)"),
        ("TreadMaterial", "tread", "lumber.metric.45x145", "Tread boards, laid flat"),
        ("RailMaterial", "rail", "lumber.metric.45x70", "Handrails"),
        ("PostMaterial", "post", "lumber.metric.70x70", "Newel posts"),
        ("BalusterMaterial", "baluster", "lumber.metric.45x45", "Balusters"),
    ]

    def model(self, obj):
        max_riser = rule_set().get("stair_riser_max_mm")
        if not max_riser:
            raise ValueError("the rule set has no stair_riser_max_mm")
        return Framing.Stair(
            total_rise=float(obj.TotalRise.Value),
            width=float(obj.Width.Value),
            max_riser=float(max_riser),
            tread_boards=int(obj.TreadBoards),
            tread_gap=float(obj.TreadGap.Value),
            nosing=float(obj.Nosing.Value),
            tread=lumber_section(obj.TreadMaterial),
            stringer=lumber_section(obj.StringerMaterial),
            max_stringer_spacing=float(obj.StringerSpacing.Value),
            max_piece=self.max_piece(obj),
            open_sides=obj.OpenSides,
            handrail_height=float(obj.HandrailHeight.Value),
            rail=lumber_section(obj.RailMaterial),
            post=lumber_section(obj.PostMaterial),
            baluster=lumber_section(obj.BalusterMaterial),
            max_baluster_gap=float(obj.BalusterGap.Value),
        )

    def checks(self, obj, rules):
        return Checks.stair(self.model(obj), rules)


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
    ]
    MATERIALS = [
        ("JoistMaterial", "joist", "lumber.metric.45x195", "Joists, ledger and rim"),
        ("BeamMaterial", "beam", "lumber.metric.45x195", "One beam ply"),
        ("PostMaterial", "post", "lumber.metric.95x95", "Posts"),
        ("DeckingMaterial", "decking", "lumber.metric.28x120", "Decking boards"),
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
        )

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
    return _make_framing(StairFeature, name, doc)


def _make_framing(feature, name, doc):
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    feature(obj)
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = 0
    doc.recompute()
    return obj


def make_wall_frame(doc=None, name="WallFrame"):
    return _make_framing(WallFrameFeature, name, doc)


def make_floor_frame(doc=None, name="FloorFrame"):
    return _make_framing(FloorFrameFeature, name, doc)


def make_gable_roof(doc=None, name="GableRoof"):
    return _make_framing(GableRoofFeature, name, doc)


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

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

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
        obj.ViewObject.Proxy = 0
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
        _length("DoorWidth", "Rough opening, centred in the front wall", _d.door_width),
        _length("DoorHeight", "Rough opening", _d.door_height),
        ("App::PropertyAngle", "Pitch", "Roof slope (26.57 = 6 in 12)", _d.pitch),
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
        for ptype, prop, tip, value in self.PROPERTIES:
            add_property(obj, ptype, prop, self.GROUP, tip, value)
        for prop, section, default in self.LUMBER:
            add_library_choice(obj, prop, Library.LUMBER, default, "Lumber", section)
        for prop, covers, default in self.SHEETS:
            tip = "Sheathing on " + ", ".join(covers).lower()
            add_library_choice(obj, prop, Library.SHEET_GOODS, default, "Sheathing", tip)

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

    def execute(self, obj):
        solids = self.solids(obj)
        if not obj.ShowSheathing:
            parts = self.parts(obj)
            solids = [s for s, (_, p) in zip(solids, parts) if p.role != "sheathing"]
        set_shape(obj, solids)

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
            else:
                results = Checks.roof(c.model, rules, values("RafterMaterial"), float(obj.RoofLoad))
            out += [(f"{c.name}: {check}", status, detail) for check, status, detail in results]
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


def make_shed(doc=None, name="Shed"):
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    ShedFeature(obj)
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = 0
    doc.recompute()
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

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

    def part_rows(self, obj):
        return _table_rows(obj.PartsTable, len(Build.PARTS_HEADER))

    def joint_rows(self, obj):
        return _table_rows(obj.JointsTable, len(Build.JOINTS_HEADER))

    def _build(self, obj):
        return Build.build(self.part_rows(obj), self.joint_rows(obj), items())

    def parts(self, obj):
        return self._build(obj)[0]

    def solids(self, obj):
        parts, result = self._build(obj)
        out = []
        for i, (_, p) in enumerate(parts):
            solid = Part.makeBox(*p.size, FreeCAD.Vector(*p.pos))
            cuts = [
                Part.makeBox(*c.size, FreeCAD.Vector(*c.pos)) for j, c in result.pockets if j == i
            ]
            out.append(solid.cut(cuts) if cuts else solid)
        return out

    def execute(self, obj):
        set_shape(obj, self.solids(obj))

    def checks(self, obj, rules):
        return []

    def anchored(self, obj, rules):
        return 0

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
        _write_row(
            obj.JointsTable, len(self.joint_rows(obj)) + 2, [receiver, inserted, joint, opts]
        )
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
        obj.ViewObject.Proxy = 0
    doc.recompute()
    return obj


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


def add_board_between(build, a, b, name=None, stock=None):
    """Adds a board spanning the gap between parts named a and b."""
    parts = {p.name: p for _, p in build.Proxy.parts(build)}
    stock = stock or build.BoardStock
    section = lumber_section(stock)
    length, x, y, z, along, thick = Build.between(parts[a], parts[b], section)
    return add_board(build, name, stock, length, (x, y, z), along, thick)


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
    summary = len(rows) + 3
    _write_row(cut, summary, [f"Sheets (panel-saw layout, kerf {kerf:g} mm, trim {trim:g} mm)"])
    for material, suffix, count, share in _write_sheet_layouts(doc, groups, lib, label, kerf):
        summary += 1
        _write_row(
            cut, summary, [label(material) + suffix, f"{share:.0%} used", "", "", "", "", count]
        )
    summary += 2
    _write_row(cut, summary, [f"Lumber (stock lengths, kerf {kerf:g} mm)"])
    for material, stock, count in _write_lumber_plan(
        doc, rows, of_category(rows, Library.LUMBER), lib, label, kerf
    ):
        summary += 1
        _write_row(cut, summary, [label(material), f"{stock:g} mm", "", "", "", "", count])
    summary += 2
    _write_row(cut, summary, ["Hardware"])
    rules = rule_set()
    anchored = sum(obj.Proxy.anchored(obj, rules) for obj in construction_objects(doc))
    schedule = fastening_schedule()
    fasteners = {}
    for obj in construction_objects(doc):
        for hardware_id, count in obj.Proxy.fasteners(obj, schedule).items():
            fasteners[hardware_id] = fasteners.get(hardware_id, 0) + count
    hardware = CutList.hardware([part for _, part in parts], lib, anchored, fasteners)
    for name, qty in hardware:
        summary += 1
        _write_row(cut, summary, [name, "", "", "", "", "", qty])
    doc.recompute()
    return cut


def _write_sheet_layouts(doc, groups, lib, label, kerf):
    """Lays out sheet materials. groups: [(cut rows, materials, trim, label suffix)].
    Returns [(material, suffix, sheets, share used)]."""
    layout = _sheet(doc, "SheetLayout")
    _write_row(
        layout,
        1,
        ["Material", "Sheet", "Part", "X (mm)", "Y (mm)", "Across (mm)", "Along (mm)", "Rotated"],
    )
    shapes, offset, row, out = [], 0.0, 2, []
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
            outline = Part.makePlane(sheet_w, sheet_h, FreeCAD.Vector(offset, 0, 0)).OuterWire
            shapes.append(outline)
            for p in placed:
                rotated = "yes" if p.rotated else "no"
                _write_row(
                    layout,
                    row,
                    [label(material) + suffix, number, p.name, p.x, p.y, p.w, p.h, rotated],
                )
                shapes.append(Part.makePlane(p.w, p.h, FreeCAD.Vector(offset + p.x, p.y, 0)))
                row += 1
            offset += sheet_w + 200.0  # sheets side by side, 200 mm apart
    view = doc.getObject("SheetLayoutView") or doc.addObject("Part::Feature", "SheetLayoutView")
    view.Shape = Part.makeCompound(shapes)
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
            "document_type": "Framing drawing",
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
    group.Source = list(objects)
    group.ScaleType = "Automatic"
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
    gap = (top - bottom) * TAG_GAP
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

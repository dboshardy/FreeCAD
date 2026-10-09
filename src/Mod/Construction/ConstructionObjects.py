# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: parametric construction objects (design doc §5.4, §5.6).

from dataclasses import replace

import FreeCAD
import Part

import Cabinet
import Checks
import CutList
import Framing
import Library
import Member

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
}


def add_property(obj, kind, prop, group, tip, value):
    """Adds prop when missing (new object or older file) and sets its default."""
    if prop in obj.PropertiesList:
        return
    obj.addProperty(kind, prop, group, tip)
    if kind == ENUM:
        setattr(obj, prop, list(CHOICES[prop]))
    setattr(obj, prop, value)


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
    return Cabinet.Part(name, "member", (*section, length), (0, 0, 0), "z")


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

    skip = ()  # Cabinet properties a subclass does not use

    def __init__(self, obj, preset="base"):
        obj.Proxy = self
        self.setProperties(obj, preset)

    def setProperties(self, obj, preset="base"):
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

    def execute(self, obj):
        # ValueError from validate() marks the object as failed with its message.
        set_shape(
            obj, [Part.makeBox(*p.size, FreeCAD.Vector(*p.pos)) for p in self.model_parts(obj)]
        )

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

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
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

    def execute(self, obj):
        start, end = self.endpoints(obj)
        set_shape(obj, [member_box(start, end, obj.Roll.Value, lumber_section(obj.Material))])

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


class WallFrameFeature:
    """Stud wall framing along the object's local X axis (see Framing.py)."""

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        d = Framing.Wall()
        props = [
            (LENGTH, "Length", "Wall length", d.length),
            (LENGTH, "Height", "Bottom of the bottom plate to top of the top plates", d.height),
            (LENGTH, "StudSpacing", "Stud centres, e.g. 400 / 600 mm or 406.4 (16 in)", d.spacing),
            (INTEGER, "TopPlates", "1 or 2", d.top_plates),
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
        for ptype, prop, tip, value in props:
            add_property(obj, ptype, prop, "Wall", tip, value)
        add_library_choice(
            obj, "StudMaterial", Library.LUMBER, DEFAULT_LUMBER, "Wall", "Studs and plates"
        )
        add_library_choice(
            obj, "HeaderMaterial", Library.LUMBER, DEFAULT_HEADER, "Wall", "One header ply"
        )

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

    def wall(self, obj):
        try:
            openings = Framing.parse_openings(obj.Openings)
        except ValueError as e:
            raise ValueError(f"Openings: {e}")
        stock = library_item(obj.StudMaterial).get("stock_lengths_mm") or [6000.0]
        return Framing.Wall(
            length=float(obj.Length.Value),
            height=float(obj.Height.Value),
            spacing=float(obj.StudSpacing.Value),
            top_plates=int(obj.TopPlates),
            stud=lumber_section(obj.StudMaterial),
            header=lumber_section(obj.HeaderMaterial),
            openings=openings,
            max_piece=max(stock),
        )

    def _pieces(self, obj):
        wall = self.wall(obj)
        sections = {"stud": wall.stud, "header": wall.header}
        materials = {"stud": obj.StudMaterial, "header": obj.HeaderMaterial}
        return [(p, sections[p.section], materials[p.section]) for p in wall.pieces()]

    def parts(self, obj):
        return [(m, member_part(p.name, p.start, p.end, s)) for p, s, m in self._pieces(obj)]

    def checks(self, obj, rules):
        values = library_item(obj.HeaderMaterial).get("design_values")
        return Checks.wall(self.wall(obj), rules, values, float(obj.HeaderLoad))

    def anchored(self, obj, rules):
        return 0

    def execute(self, obj):
        set_shape(obj, [member_box(p.start, p.end, p.roll, s) for p, s, _ in self._pieces(obj)])

    def dumps(self):
        return None

    def loads(self, state):
        return None


DEFAULT_HEADER = "lumber.metric.45x195"


def make_wall_frame(doc=None, name="WallFrame"):
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    WallFrameFeature(obj)
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = 0
    doc.recompute()
    return obj


def construction_objects(doc):
    kinds = (CabinetFeature, MemberFeature, WallFrameFeature)
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
    headers = ["Material", "Part", "Length (mm)", "Width (mm)", "Thickness (mm)", "Grain", "Qty"]
    _write_row(cut, 1, headers)
    for r, (material, name, length, width, thick, grain, qty) in enumerate(rows, start=2):
        _write_row(cut, r, [label(material), name, length, width, thick, grain, qty])

    materials = sorted({r[0] for r in rows})
    by_category = {
        cat: [m for m in materials if lib.get(m, {}).get("category") == cat]
        for cat in (Library.SHEET_GOODS, Library.LUMBER)
    }
    summary = len(rows) + 3
    _write_row(cut, summary, [f"Sheets (panel-saw layout, kerf {kerf:g} mm, trim {trim:g} mm)"])
    for material, count, share in _write_sheet_layouts(
        doc, rows, by_category[Library.SHEET_GOODS], lib, label, kerf, trim
    ):
        summary += 1
        _write_row(cut, summary, [label(material), f"{share:.0%} used", "", "", "", "", count])
    summary += 2
    _write_row(cut, summary, [f"Lumber (stock lengths, kerf {kerf:g} mm)"])
    for material, stock, count in _write_lumber_plan(
        doc, rows, by_category[Library.LUMBER], lib, label, kerf
    ):
        summary += 1
        _write_row(cut, summary, [label(material), f"{stock:g} mm", "", "", "", "", count])
    summary += 2
    _write_row(cut, summary, ["Hardware"])
    rules = rule_set()
    anchored = sum(obj.Proxy.anchored(obj, rules) for obj in construction_objects(doc))
    for name, qty in CutList.hardware([part for _, part in parts], lib, anchored):
        summary += 1
        _write_row(cut, summary, [name, "", "", "", "", "", qty])
    doc.recompute()
    return cut


def _write_sheet_layouts(doc, rows, materials, lib, label, kerf, trim):
    """Lays out sheet materials; yields (material, sheets, share used)."""
    layout = _sheet(doc, "SheetLayout")
    _write_row(
        layout,
        1,
        ["Material", "Sheet", "Part", "X (mm)", "Y (mm)", "Across (mm)", "Along (mm)", "Rotated"],
    )
    shapes, offset, row, out = [], 0.0, 2, []
    for material in materials:
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
        out.append((material, len(sheets), used / (len(sheets) * sheet_w * sheet_h)))
        for number, placed in enumerate(sheets, start=1):
            outline = Part.makePlane(sheet_w, sheet_h, FreeCAD.Vector(offset, 0, 0)).OuterWire
            shapes.append(outline)
            for p in placed:
                rotated = "yes" if p.rotated else "no"
                _write_row(
                    layout, row, [label(material), number, p.name, p.x, p.y, p.w, p.h, rotated]
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

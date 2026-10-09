# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: parametric construction objects (design doc §5.4, §5.6).

import FreeCAD
import Part

import Cabinet
import CutList
import Library

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
        sheet_ids = [i["id"] for i in Library.sheets(items())]
        for prop, default in DEFAULT_MATERIALS.items():
            if prop in obj.PropertiesList:
                current = getattr(obj, prop)
            else:
                obj.addProperty(ENUM, prop, "Materials", MATERIAL_TIPS[prop])
                current = default
            # A value whose library item is gone stays selectable, and fails in execute().
            setattr(obj, prop, sheet_ids if current in sheet_ids else sheet_ids + [current])
            setattr(obj, prop, current)

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

    def parts(self, obj):
        """[(material id, Part)] for the cut list."""
        return [
            (getattr(obj, ROLE_MATERIAL.get(p.role, "CarcassMaterial")), p)
            for p in self.model_parts(obj)
        ]

    def execute(self, obj):
        # ValueError from validate() marks the object as failed with its message.
        boxes = [Part.makeBox(*p.size, FreeCAD.Vector(*p.pos)) for p in self.model_parts(obj)]
        placement = obj.Placement
        obj.Shape = Part.makeCompound(boxes)
        obj.Placement = placement

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

    def execute(self, obj):
        widths, left, right = self.run(obj).layout()
        layout = ", ".join(f"{w:g}" for w in widths)
        obj.Layout = f"{layout} | fillers {left:g} / {right:g}"
        super().execute(obj)


def sheet_thickness(material_id):
    item = items().get(material_id)
    if item is None:
        raise ValueError(f"material '{material_id}' not found in the construction library")
    return Library.mm(item, "t")


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


def construction_objects(doc):
    return [o for o in doc.Objects if isinstance(getattr(o, "Proxy", None), CabinetFeature)]


PARAMS = "User parameter:BaseApp/Preferences/Mod/Construction"


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
    """Writes the cut list, sheet counts and hardware of every construction
    object to the spreadsheet 'CutList', the panel-saw layout to 'SheetLayout',
    and a flat view of the sheets to 'SheetLayoutView'."""
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

    layout = _sheet(doc, "SheetLayout")
    _write_row(
        layout,
        1,
        ["Material", "Sheet", "Part", "X (mm)", "Y (mm)", "Across (mm)", "Along (mm)", "Rotated"],
    )
    summary = len(rows) + 3
    _write_row(cut, summary, [f"Sheets (panel-saw layout, kerf {kerf:g} mm, trim {trim:g} mm)"])
    shapes, offset, row = [], 0.0, 2
    for material in sorted({r[0] for r in rows}):
        item = lib.get(material)
        if item is None or "actual" not in item:
            continue  # sheet_thickness() already reported a missing material
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
        share = used / (len(sheets) * sheet_w * sheet_h)
        summary += 1
        _write_row(
            cut, summary, [label(material), f"{share:.0%} used", "", "", "", "", len(sheets)]
        )
        for number, placed in enumerate(sheets, start=1):
            outline = Part.makePlane(sheet_w, sheet_h, FreeCAD.Vector(offset, 0, 0)).OuterWire
            shapes.append(outline)
            for p in placed:
                _write_row(
                    layout,
                    row,
                    [
                        label(material),
                        number,
                        p.name,
                        p.x,
                        p.y,
                        p.w,
                        p.h,
                        "yes" if p.rotated else "no",
                    ],
                )
                shapes.append(Part.makePlane(p.w, p.h, FreeCAD.Vector(offset + p.x, p.y, 0)))
                row += 1
            offset += sheet_w + 200.0  # sheets side by side, 200 mm apart
    summary += 2
    _write_row(cut, summary, ["Hardware"])
    for name, qty in CutList.hardware([part for _, part in parts], lib):
        summary += 1
        _write_row(cut, summary, [name, "", "", "", "", "", qty])
    view = doc.getObject("SheetLayoutView") or doc.addObject("Part::Feature", "SheetLayoutView")
    view.Shape = Part.makeCompound(shapes)
    doc.recompute()
    return cut

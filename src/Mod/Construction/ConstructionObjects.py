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
    ("Kind", "kind", ENUM, "Cabinet", "base: top stretchers; wall / tall: full top panel"),
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
]
CHOICES = {"Kind": Cabinet.KINDS, "Fronts": Cabinet.FRONTS, "FillerSide": Cabinet.FILLER_SIDES}


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

    def __init__(self, obj, kind="base"):
        obj.Proxy = self
        self.setProperties(obj, kind)

    def setProperties(self, obj, kind="base"):
        defaults = Cabinet.defaults(kind)
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


def parse_widths(text, prop):
    """'600, 600, 900' -> (600.0, 600.0, 900.0). Raises ValueError naming prop."""
    try:
        values = tuple(float(v) for v in text.replace(";", ",").split(",") if v.strip())
    except ValueError:
        raise ValueError(f"{prop}: use comma-separated numbers in mm, e.g. 600, 600, 900")
    if any(v <= 0 for v in values):
        raise ValueError(f"{prop}: widths must be positive")
    return values


class CabinetRunFeature(CabinetFeature):
    """Cabinets side by side along a wall; all share the cabinet properties."""

    skip = ("Width",)

    def setProperties(self, obj, kind="base"):
        super().setProperties(obj, kind)
        standard = ", ".join(f"{w:g}" for w in Cabinet.STANDARD_WIDTHS)
        run = [
            ("App::PropertyLength", "Length", "Run", "Wall length to fill", 2400.0),
            (
                "App::PropertyString",
                "Widths",
                "Run",
                "Cabinet widths in mm, left to right; empty = chosen from StandardWidths",
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
        return Cabinet.Run(
            self.spec(obj),
            length=float(obj.Length.Value),
            widths=parse_widths(obj.Widths, "Widths"),
            standard=parse_widths(obj.StandardWidths, "StandardWidths"),
            filler_side=obj.FillerSide,
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


def _make(feature, kind, name, doc):
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    feature(obj, kind)
    if kind == "wall":
        placement = obj.Placement  # a copy: modify, then assign back
        placement.Base.z = Cabinet.WALL_ELEVATION
        obj.Placement = placement
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = 0
    doc.recompute()
    return obj


def make_cabinet(kind="base", doc=None):
    return _make(CabinetFeature, kind, kind.capitalize() + "Cabinet", doc)


def make_cabinet_run(kind="base", doc=None):
    return _make(CabinetRunFeature, kind, kind.capitalize() + "Run", doc)


def construction_objects(doc):
    return [o for o in doc.Objects if isinstance(getattr(o, "Proxy", None), CabinetFeature)]


def write_cut_list(doc):
    """Writes the cut list of every construction object to the spreadsheet 'CutList'."""
    parts = [mp for obj in construction_objects(doc) for mp in obj.Proxy.parts(obj)]
    rows = CutList.rows(parts)
    lib = items()

    def label(material):
        return lib.get(material, {}).get("name", material)

    def text(value):
        return "'" + str(value)  # force text, never a formula

    sheet = doc.getObject("CutList") or doc.addObject("Spreadsheet::Sheet", "CutList")
    sheet.clearAll()
    headers = ["Material", "Part", "Length (mm)", "Width (mm)", "Thickness (mm)", "Grain", "Qty"]
    for col, h in enumerate(headers):
        sheet.set(f"{chr(65 + col)}1", text(h))
    for r, (material, name, length, width, thick, grain, qty) in enumerate(rows, start=2):
        values = [text(label(material)), text(name), length, width, thick, text(grain), qty]
        for col, value in enumerate(values):
            sheet.set(f"{chr(65 + col)}{r}", str(value))

    areas = {m: Library.mm(i, "w") * Library.mm(i, "h") for m, i in lib.items() if "actual" in i}
    r = len(rows) + 3
    sheet.set(f"A{r}", text("Sheets (area estimate, 15% waste)"))
    for material, count in sorted(CutList.sheet_estimate(rows, areas).items()):
        r += 1
        sheet.set(f"A{r}", text(label(material)))
        sheet.set(f"G{r}", str(count))
    doc.recompute()
    return sheet

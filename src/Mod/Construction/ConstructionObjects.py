# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: parametric construction objects (design doc §5.4, §5.6).

import FreeCAD
import Part

import Cabinet
import CutList
import Library

DEFAULT_CARCASS = "sheet.metric.plywood.18"
DEFAULT_BACK = "sheet.metric.plywood.6"

_items = None


def items():
    """Shipped library plus user overrides, loaded once per session."""
    global _items
    if _items is None:
        _items = Library.load([Library.LIBRARY_DIR, Library.user_dir()])
    return _items


# (property, BaseCabinet field, type, group, tooltip). Thicknesses come from the materials.
LENGTH = "App::PropertyLength"
INTEGER = "App::PropertyInteger"
PROPERTIES = [
    ("Width", "width", LENGTH, "Size", "Outside width of the carcass"),
    ("Height", "height", LENGTH, "Size", "Floor to top of the carcass, plinth included"),
    ("Depth", "depth", LENGTH, "Size", "Carcass and back, doors excluded"),
    ("PlinthHeight", "plinth_height", LENGTH, "Plinth", "0 for no plinth"),
    ("PlinthSetback", "plinth_setback", LENGTH, "Plinth", "Kick board behind the carcass front"),
    ("StretcherWidth", "stretcher_width", LENGTH, "Carcass", "Front and back top stretchers"),
    ("Shelves", "shelves", INTEGER, "Interior", "Number of adjustable shelves"),
    ("ShelfSetback", "shelf_setback", LENGTH, "Interior", "Shelf front behind the carcass front"),
    ("ShelfClearance", "shelf_clearance", LENGTH, "Interior", "Gap at each shelf end"),
    ("Doors", "doors", INTEGER, "Doors", "0 = one door up to 600 mm wide, else two"),
    ("DoorGap", "door_gap", LENGTH, "Doors", "Gap between doors; half of it at the outer edges"),
]
MATERIALS = [
    ("CarcassMaterial", DEFAULT_CARCASS, "Sides, bottom, stretchers, shelves, doors, plinth"),
    ("BackMaterial", DEFAULT_BACK, "Back panel"),
]


class BaseCabinetFeature:
    """Frameless base cabinet. Every size is a property; edit in the property view."""

    def __init__(self, obj):
        obj.Proxy = self
        self.setProperties(obj)

    def setProperties(self, obj):
        defaults = Cabinet.BaseCabinet()
        for prop, field, kind, group, tip in PROPERTIES:
            if prop not in obj.PropertiesList:
                obj.addProperty(kind, prop, group, tip)
                setattr(obj, prop, getattr(defaults, field))
        sheet_ids = [i["id"] for i in Library.sheets(items())]
        for prop, default, tip in MATERIALS:
            if prop in obj.PropertiesList:
                current = getattr(obj, prop)
            else:
                obj.addProperty("App::PropertyEnumeration", prop, "Materials", tip)
                current = default
            # A value whose library item is gone stays selectable, and fails in execute().
            setattr(obj, prop, sheet_ids if current in sheet_ids else sheet_ids + [current])
            setattr(obj, prop, current)

    def onDocumentRestored(self, obj):
        self.setProperties(obj)

    def spec(self, obj):
        kwargs = {}
        for prop, field, kind, _, _ in PROPERTIES:
            value = getattr(obj, prop)
            kwargs[field] = int(value) if kind == INTEGER else float(value.Value)
        kwargs["thickness"] = sheet_thickness(obj.CarcassMaterial)
        kwargs["back_thickness"] = sheet_thickness(obj.BackMaterial)
        return Cabinet.BaseCabinet(**kwargs)

    def parts(self, obj):
        """[(material id, Part)] for the cut list."""
        out = []
        for part in self.spec(obj).parts():
            material = obj.BackMaterial if part.role == "back" else obj.CarcassMaterial
            out.append((material, part))
        return out

    def execute(self, obj):
        # ValueError from validate() marks the object as failed with its message.
        boxes = [Part.makeBox(*p.size, FreeCAD.Vector(*p.pos)) for _, p in self.parts(obj)]
        placement = obj.Placement
        obj.Shape = Part.makeCompound(boxes)
        obj.Placement = placement

    def dumps(self):
        return None

    def loads(self, state):
        return None


def sheet_thickness(material_id):
    item = items().get(material_id)
    if item is None:
        raise ValueError(f"material '{material_id}' not found in the construction library")
    return Library.mm(item, "t")


def make_base_cabinet(doc=None, name="BaseCabinet"):
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", name)
    BaseCabinetFeature(obj)
    if FreeCAD.GuiUp:
        obj.ViewObject.Proxy = 0
    doc.recompute()
    return obj


def construction_objects(doc):
    return [o for o in doc.Objects if isinstance(getattr(o, "Proxy", None), BaseCabinetFeature)]


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

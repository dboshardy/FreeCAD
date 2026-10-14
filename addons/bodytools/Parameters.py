# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parameters from a JSON file, and variants (named sets of values, suppression and properties).

Both sit on stock objects: parameters are Spreadsheet aliases, so expressions in any
feature can use them. Variants are stored as JSON text in one property of a
Part::FeaturePython object, so they save with the document.
"""

import json

import FreeCAD

VARIANTS_LABEL = "Variants"


def _column_cell(sheet, row):
    return "A%d" % row, "B%d" % row


def set_parameter(sheet, name, value):
    """Set sheet alias `name` to `value`, creating the row if the alias is new."""
    cell = sheet.getCellFromAlias(name)
    if cell is None:
        row = 1
        while sheet.getContents("A%d" % row):
            row += 1
        a, b = _column_cell(sheet, row)
        sheet.set(a, name)
        sheet.set(b, str(value))
        sheet.setAlias(b, name)
    else:
        sheet.set(cell, str(value))


def load_json(sheet, path):
    """Load {"name": number-or-quantity-string, ...} into `sheet`. No network, local file only.

    Returns the list of names set. Raises ValueError on a non-object file or an invalid name.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("%s: top level must be an object of name: value" % path)
    for name, value in data.items():
        if not name.isidentifier():
            raise ValueError("%s: %r is not a valid alias name" % (path, name))
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError("%s: value of %r must be a number or a string" % (path, name))
    for name, value in data.items():
        set_parameter(sheet, name, value)
    sheet.recompute()
    return list(data)


class VariantTable:
    """Variants of one part: per variant, parameter values, suppression flags and properties.

    Layout of one variant:
      {"params": {alias: value}, "suppress": {object name: bool}, "props": {"Obj.Prop": value}}
    """

    def __init__(self, doc, sheet):
        self.doc = doc
        self.sheet = sheet
        obj = doc.getObject("VariantTable")
        if obj is None:
            obj = doc.addObject("App::FeaturePython", "VariantTable")
            obj.Label = VARIANTS_LABEL
            obj.addProperty("App::PropertyString", "Data", "Variants", "JSON, one entry per variant")
            obj.addProperty("App::PropertyString", "Active", "Variants", "Variant last applied")
            obj.Data = "{}"
        self.obj = obj

    @property
    def variants(self):
        return json.loads(self.obj.Data)

    def _store(self, data):
        self.obj.Data = json.dumps(data, sort_keys=True)

    def names(self):
        return list(self.variants)

    def define(self, name, params=None, suppress=None, props=None):
        data = self.variants
        data[name] = {"params": params or {}, "suppress": suppress or {}, "props": props or {}}
        self._store(data)

    def remove(self, name):
        data = self.variants
        del data[name]
        self._store(data)

    def apply(self, name):
        """Apply variant `name`, recompute, return the names of objects that failed to recompute."""
        v = self.variants[name]
        for key, value in v["params"].items():
            set_parameter(self.sheet, key, value)
        for oname, flag in v["suppress"].items():
            obj = self.doc.getObject(oname)
            if obj is None:
                raise KeyError("variant %r: no object %r" % (name, oname))
            obj.Suppressed = bool(flag)
        for path, value in v["props"].items():
            oname, _, prop = path.partition(".")
            setattr(self.doc.getObject(oname), prop, value)
        self.obj.Active = name
        self.sheet.recompute()
        # a cell set back to an earlier value does not always mark its dependents
        # stale: touch every object that has expressions
        for o in self.doc.Objects:
            if getattr(o, "ExpressionEngine", None):
                o.touch()
        self.doc.recompute()
        return [o.Name for o in self.doc.Objects if "Invalid" in o.State or "Error" in o.State]

    def as_rows(self):
        """Flat table for an editor: one row per (variant, kind, key, value)."""
        rows = []
        for vname, v in self.variants.items():
            for kind in ("params", "suppress", "props"):
                for key, value in v[kind].items():
                    rows.append((vname, kind, key, value))
        return rows

    def set_row(self, vname, kind, key, value):
        data = self.variants
        data[vname][kind][key] = value
        self._store(data)

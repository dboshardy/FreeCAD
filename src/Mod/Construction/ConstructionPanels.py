# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: editing panels for construction objects (design doc Phase 5.2).
"""Task panels that edit construction objects through lists with dropdowns
instead of typed strings, spreadsheet cells and library ids.

One generic TableEditor (columns of text, numbers or choices) is used for a
build's parts and joints, a wall's openings, a floor's beams and openings and
a cabinet run's cabinets. edit_panel(obj) returns the panel for an object, or
None when it has none.
"""

import FreeCAD
import FreeCADGui
from PySide import QtGui

import Build
import Cabinet
import ConstructionObjects as CO
import Framing
import Library

translate = FreeCAD.Qt.translate
TEXT, NUMBER, CHOICE = "text", "number", "choice"


def library_choices(*categories, where=None):
    """[(label, id)] of library items of the categories, in the active
    document's region (generic items always)."""
    region = CO.document_region(FreeCAD.ActiveDocument)
    out = []
    for category in categories:
        for item in Library.of_category(CO.items(), category):
            if region != "all" and item.get("region") not in (region, "generic"):
                continue
            if where is None or where(item):
                out.append((item.get("name", item["id"]), item["id"]))
    return out


class TableEditor(QtGui.QWidget):
    """A list of rows with typed columns: (header, kind, choices) where kind is
    TEXT, NUMBER (empty allowed when optional) or CHOICE ([(label, value)])."""

    def __init__(self, title, columns, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.columns = columns
        layout = QtGui.QVBoxLayout(self)
        self.table = QtGui.QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels([c[0] for c in columns])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        buttons = QtGui.QHBoxLayout()
        for text, slot in (
            (translate("Construction", "Add"), self.add_row),
            (translate("Construction", "Remove"), self.remove_row),
        ):
            button = QtGui.QPushButton(text)
            button.clicked.connect(lambda checked=False, s=slot: s())
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.set_rows(rows)

    def add_row(self, values=None):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, (_, kind, choices) in enumerate(self.columns):
            value = values[c] if values else ""
            if kind == CHOICE:
                combo = QtGui.QComboBox()
                for label, data in choices:
                    combo.addItem(label, data)
                index = combo.findData(value)
                if index < 0 and value not in ("", None):
                    combo.addItem(str(value), value)  # e.g. an item of another region
                    index = combo.count() - 1
                combo.setCurrentIndex(max(index, 0))
                self.table.setCellWidget(r, c, combo)
            else:
                text = (
                    "" if value in ("", None) else (f"{value:g}" if kind == NUMBER else str(value))
                )
                self.table.setItem(r, c, QtGui.QTableWidgetItem(text))

    def remove_row(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows or [self.table.rowCount() - 1]:
            if r >= 0:
                self.table.removeRow(r)

    def set_rows(self, rows):
        self.table.setRowCount(0)
        for row in rows:
            self.add_row(list(row))

    def rows(self):
        """The rows as values; numbers as floats ('' when empty). Raises
        ValueError for a number that does not read."""
        out = []
        for r in range(self.table.rowCount()):
            row = []
            for c, (header, kind, _) in enumerate(self.columns):
                if kind == CHOICE:
                    row.append(self.table.cellWidget(r, c).currentData())
                    continue
                item = self.table.item(r, c)
                text = item.text().strip() if item else ""
                if kind == NUMBER and text:
                    try:
                        row.append(float(text))
                    except ValueError:
                        raise ValueError(f"{header} in row {r + 1}: '{text}' is not a number")
                else:
                    row.append(text)
            out.append(tuple(row))
        return out


class EditPanel:
    """Task panel of TableEditors; apply(editors) writes them to the object."""

    def __init__(self, obj, editors, apply):
        self.obj, self.editors, self.apply_rows = obj, editors, apply
        self.form = editors

    def accept(self):
        doc = self.obj.Document
        doc.openTransaction(translate("Construction", "Edit {}").format(self.obj.Label))
        try:
            self.apply_rows(*[e.rows() for e in self.editors])
            doc.recompute()
        except ValueError as e:
            doc.abortTransaction()
            QtGui.QMessageBox.warning(
                FreeCADGui.getMainWindow(), translate("Construction", "Edit"), str(e)
            )
            return False
        if "Invalid" in self.obj.State:
            doc.abortTransaction()
            doc.recompute()
            QtGui.QMessageBox.warning(
                FreeCADGui.getMainWindow(),
                translate("Construction", "Edit"),
                translate("Construction", "{} cannot be built that way; nothing changed.").format(
                    self.obj.Label
                ),
            )
            return False
        doc.commitTransaction()
        FreeCADGui.Control.closeDialog()
        return True

    def reject(self):
        FreeCADGui.Control.closeDialog()
        return True

    def getStandardButtons(self):
        buttons = QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        return int(getattr(buttons, "value", buttons))  # PySide6 flags carry .value


AXES = [(a, a) for a in "xyz"]


def build_panel(obj):
    stock = library_choices(Library.LUMBER, Library.SHEET_GOODS)
    parts = TableEditor(
        translate("Construction", "Parts"),
        [
            ("Name", TEXT, None),
            ("Stock", CHOICE, stock),
            ("Length", NUMBER, None),
            ("Width", NUMBER, None),
            ("Thickness", NUMBER, None),
            ("X", NUMBER, None),
            ("Y", NUMBER, None),
            ("Z", NUMBER, None),
            ("Along", CHOICE, AXES),
            ("Thick", CHOICE, AXES),
        ],
        obj.Proxy.part_rows(obj),
    )
    joints = TableEditor(
        translate("Construction", "Joints"),
        [
            ("Receiver", TEXT, None),
            ("Inserted", TEXT, None),
            ("Joint", CHOICE, library_choices("joint")),
            ("Options", TEXT, None),
        ],
        obj.Proxy.joint_rows(obj),
    )

    def apply(part_rows, joint_rows):
        names = [r[0] for r in part_rows]
        if any(not n for n in names) or len(set(names)) != len(names):
            raise ValueError(translate("Construction", "Every part needs its own name"))
        CO._rewrite_table(obj.PartsTable, Build.PARTS_HEADER, [(r, False) for r in part_rows])
        CO._rewrite_table(obj.JointsTable, Build.JOINTS_HEADER, [(r, False) for r in joint_rows])
        obj.touch()

    return EditPanel(obj, [parts, joints], apply)


def wall_panel(obj):
    openings = [
        (o.kind, o.width, o.height, o.x, o.sill) for o in Framing.parse_openings(obj.Openings)
    ]
    editor = TableEditor(
        translate("Construction", "Openings"),
        [
            ("Kind", CHOICE, [("door", "door"), ("window", "window")]),
            ("Width", NUMBER, None),
            ("Height", NUMBER, None),
            ("From wall start", NUMBER, None),
            ("Sill", NUMBER, None),
        ],
        openings,
    )

    def apply(rows):
        obj.Openings = Framing.format_openings(
            [
                Framing.Opening(k, float(x or 0), float(w), float(h), float(s or 0))
                for k, w, h, x, s in rows
            ]
        )

    return EditPanel(obj, [editor], apply)


def floor_panel(obj):
    beams = TableEditor(
        translate("Construction", "Beams"),
        [("From the first rim", NUMBER, None)],
        [(y,) for y in Framing.parse_numbers(obj.Beams)],
    )
    openings = TableEditor(
        translate("Construction", "Openings"),
        [
            ("Width", NUMBER, None),
            ("Length", NUMBER, None),
            ("X", NUMBER, None),
            ("Y", NUMBER, None),
        ],
        [(w, l, x, y) for x, y, w, l in Framing.parse_floor_openings(obj.Openings)],
    )

    def apply(beam_rows, opening_rows):
        obj.Beams = ", ".join(f"{y:g}" for (y,) in beam_rows if y != "")
        obj.Openings = Framing.format_floor_openings(
            [(float(x), float(y), float(w), float(l)) for w, l, x, y in opening_rows]
        )

    return EditPanel(obj, [beams, openings], apply)


def run_panel(obj):
    widths, styles = Cabinet.parse_entries(obj.Widths, allow_styles=True)
    styles = list(styles) + [None] * (len(widths) - len(styles))
    choices = [(translate("Construction", "as the run"), "")] + [(s, s) for s in Cabinet.RUN_STYLES]
    editor = TableEditor(
        translate("Construction", "Cabinets, left to right (none: chosen from StandardWidths)"),
        [("Width", NUMBER, None), ("Style", CHOICE, choices)],
        [(w, s or "") for w, s in zip(widths, styles)],
    )

    def apply(rows):
        obj.Widths = Cabinet.format_entries(
            [float(w) for w, _ in rows], [s or None for _, s in rows]
        )

    return EditPanel(obj, [editor], apply)


def edit_panel(obj):
    """The editing panel for a construction object, or None."""
    proxy = getattr(obj, "Proxy", None)
    for kind, make in (
        (CO.BuildFeature, build_panel),
        (CO.WallFrameFeature, wall_panel),
        (CO.FloorFrameFeature, floor_panel),
        (CO.CabinetRunFeature, run_panel),
    ):
        if isinstance(proxy, kind):
            return make(obj)
    return None


def show(obj):
    """Opens obj's panel in the task view; False when it has none."""
    panel = edit_panel(obj)
    if panel is None:
        return False
    FreeCADGui.Control.closeDialog()
    FreeCADGui.Control.showDialog(panel)
    return True

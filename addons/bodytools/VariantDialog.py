# SPDX-License-Identifier: LGPL-2.1-or-later
"""Table editor for Parameters.VariantTable: one row per variant/kind/key/value."""

import json

import FreeCADGui
from PySide import QtWidgets

import Parameters

KINDS = ("params", "suppress", "props")


class VariantDialog(QtWidgets.QDialog):
    def __init__(self, doc, sheet, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Variants")
        self.table = Parameters.VariantTable(doc, sheet)
        self.grid = QtWidgets.QTableWidget(0, 4)
        self.grid.setHorizontalHeaderLabels(["Variant", "Kind", "Key", "Value"])
        self.grid.horizontalHeader().setStretchLastSection(True)
        add = QtWidgets.QPushButton("Add row")
        apply_ = QtWidgets.QPushButton("Apply selected variant")
        add.clicked.connect(lambda: self.grid.insertRow(self.grid.rowCount()))
        apply_.clicked.connect(self.apply_selected)
        col = QtWidgets.QHBoxLayout()
        col.addWidget(add)
        col.addWidget(apply_)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.grid)
        lay.addLayout(col)
        for row in self.table.as_rows():
            self._append(*row)

    def _append(self, variant, kind, key, value):
        r = self.grid.rowCount()
        self.grid.insertRow(r)
        for c, text in enumerate((variant, kind, key, json.dumps(value))):
            self.grid.setItem(r, c, QtWidgets.QTableWidgetItem(text))

    def _text(self, r, c):
        item = self.grid.item(r, c)
        return item.text().strip() if item else ""

    def collect(self):
        """Write the grid into the table. Raises ValueError on an incomplete or bad row."""
        data = {}
        for r in range(self.grid.rowCount()):
            variant, kind, key, raw = (self._text(r, c) for c in range(4))
            if not (variant or kind or key or raw):
                continue
            if kind not in KINDS or not variant or not key:
                raise ValueError(f"Row {r + 1}: need a variant, a kind ({', '.join(KINDS)}) and a key")
            try:
                value = json.loads(raw)
            except ValueError:
                value = raw
            v = data.setdefault(variant, {k: {} for k in KINDS})
            v[kind][key] = value
        for name in self.table.names():
            self.table.remove(name)
        for name, v in data.items():
            self.table.define(name, **v)

    def apply_selected(self):
        r = self.grid.currentRow()
        name = self._text(r, 0) if r >= 0 else ""
        try:
            self.collect()
            if name not in self.table.variants:
                raise ValueError("Select a row of an existing variant")
            bad = self.table.apply(name)
        except (ValueError, KeyError, AttributeError) as e:
            QtWidgets.QMessageBox.warning(self, "Variants", str(e))
            return
        if bad:
            QtWidgets.QMessageBox.warning(self, "Variants", "Failed to recompute: " + ", ".join(bad))

    def done(self, result):
        try:
            self.collect()
        except ValueError:
            pass  # unfinished rows are dropped on close
        super().done(result)


def show(doc, sheet):
    dlg = VariantDialog(doc, sheet, FreeCADGui.getMainWindow())
    dlg.exec_()

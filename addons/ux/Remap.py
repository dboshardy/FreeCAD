# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hotkey remapping dialog: edit the layers' bindings, see conflicts, import and export profiles."""

import Hotkeys


def show():
    from PySide import QtWidgets
    import FreeCADGui as Gui

    dlg = QtWidgets.QDialog(Gui.getMainWindow())
    dlg.setWindowTitle("Hotkeys")
    dlg.resize(720, 420)
    lay = QtWidgets.QVBoxLayout(dlg)
    search = QtWidgets.QLineEdit()
    search.setPlaceholderText("Search")
    table = QtWidgets.QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["Layer", "Workbench", "Key", "Command"])
    table.horizontalHeader().setStretchLastSection(True)
    warn = QtWidgets.QLabel()
    row = QtWidgets.QHBoxLayout()
    buttons = {n: QtWidgets.QPushButton(n) for n in ("Add", "Delete", "Reset", "Import...", "Export...", "Save")}
    for b in buttons.values():
        row.addWidget(b)
    for w in (search, table, warn):
        lay.addWidget(w)
    lay.addLayout(row)

    def fill(bindings):
        table.setRowCount(0)
        for b in bindings:
            add(b["layer"], b["workbench"] or "", b["key"], b["command"])

    def add(layer="workspace", wb="", key="", cmd=""):
        r = table.rowCount()
        table.insertRow(r)
        for c, v in enumerate((layer, wb, key, cmd)):
            table.setItem(r, c, QtWidgets.QTableWidgetItem(v))

    def bindings():
        out = []
        for r in range(table.rowCount()):
            items = [table.item(r, c) for c in range(4)]
            if not all(items):  # a row still being filled in
                continue
            t = [i.text().strip() for i in items]
            if t[2] and t[3]:
                out.append({"layer": t[0], "workbench": t[1] or None, "key": t[2], "command": t[3]})
        return out

    def check(*_):
        try:
            b = Hotkeys.parse(Hotkeys.dump(bindings()))
        except ValueError as e:
            warn.setText(str(e))
            return None
        warn.setText("; ".join(Hotkeys.conflicts(b)) or "")
        return b

    def filter_rows(text):
        words = text.lower().split()
        for r in range(table.rowCount()):
            hay = " ".join(
                table.item(r, c).text().lower() for c in range(4) if table.item(r, c)
            )
            table.setRowHidden(r, not all(w in hay for w in words))

    def do_import():
        path, _ = QtWidgets.QFileDialog.getOpenFileName(dlg, "Import hotkeys", "", "JSON (*.json)")
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    fill(Hotkeys.parse(f.read()))
            except (ValueError, OSError) as e:
                warn.setText(f"import failed: {e}")

    def do_export():
        path, _ = QtWidgets.QFileDialog.getSaveFileName(dlg, "Export hotkeys", "UxHotkeys.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(Hotkeys.dump(bindings()))

    def do_save():
        b = check()
        if b is not None:
            Hotkeys.save(b)
            dlg.accept()

    def delete():
        for r in sorted({i.row() for i in table.selectedIndexes()}, reverse=True):
            table.removeRow(r)
        check()

    search.textChanged.connect(filter_rows)
    table.itemChanged.connect(check)
    buttons["Add"].clicked.connect(lambda: add())
    buttons["Delete"].clicked.connect(delete)
    buttons["Reset"].clicked.connect(lambda: fill(Hotkeys.load()))
    buttons["Import..."].clicked.connect(do_import)
    buttons["Export..."].clicked.connect(do_export)
    buttons["Save"].clicked.connect(do_save)
    fill(Hotkeys.load())
    dlg.show()
    return dlg

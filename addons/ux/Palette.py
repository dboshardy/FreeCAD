# SPDX-License-Identifier: LGPL-2.1-or-later
"""Command palette: fuzzy search over every registered command."""


def search(entries, query):
    """entries: [(name, text)]. Every query word must appear in name or text; prefix matches first."""
    words = query.lower().split()
    hits = []
    for name, text in entries:
        hay = f"{text} {name}".lower().replace("&", "")
        if all(w in hay for w in words):
            hits.append((not hay.startswith(words[0]) if words else False, text.lower(), name, text))
    hits.sort()
    return [(n, t) for _, _, n, t in hits]


def command_entries():
    import FreeCADGui as Gui

    out = []
    for name in Gui.listCommands():
        info = Gui.Command.get(name).getInfo()
        out.append((name, info.get("menuText") or name))
    return out


def show():
    from PySide import QtCore, QtWidgets
    import FreeCADGui as Gui

    entries = command_entries()
    dlg = QtWidgets.QDialog(Gui.getMainWindow(), QtCore.Qt.Popup)
    lay = QtWidgets.QVBoxLayout(dlg)
    edit, lst = QtWidgets.QLineEdit(), QtWidgets.QListWidget()
    edit.setPlaceholderText("Type a command name")
    lay.addWidget(edit)
    lay.addWidget(lst)
    dlg.resize(480, 360)

    def refill():
        lst.clear()
        for name, text in search(entries, edit.text())[:50]:
            item = QtWidgets.QListWidgetItem(f"{text.replace('&', '')}  ({name})")
            item.setData(QtCore.Qt.UserRole, name)
            lst.addItem(item)
        if lst.count():
            lst.setCurrentRow(0)

    def run(*_):
        item = lst.currentItem()
        if item:
            dlg.accept()
            Gui.runCommand(item.data(QtCore.Qt.UserRole))

    edit.textChanged.connect(refill)
    edit.returnPressed.connect(run)
    lst.itemActivated.connect(run)
    refill()
    dlg.show()
    edit.setFocus()

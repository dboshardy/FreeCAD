# SPDX-License-Identifier: LGPL-2.1-or-later
"""Context-layered hotkeys: workspace layer, then global layer. First match wins.

shortcut: no command (active-tool) layer and no chords; Python sees no tool-handler
start/finish. The command layer needs the upstream hook (design doc §4.2).
"""

import json

LAYERS = ("workspace", "global")  # resolution order


def parse(text):
    """Return a list of bindings from JSON text; raise ValueError on bad shape."""
    data = json.loads(text)
    out = []
    for b in data.get("bindings", []):
        if b.get("layer") not in LAYERS or not b.get("key") or not b.get("command"):
            raise ValueError(f"bad binding: {b!r}")
        if b["layer"] == "workspace" and not b.get("workbench"):
            raise ValueError(f"workspace binding needs a workbench: {b!r}")
        out.append({"layer": b["layer"], "workbench": b.get("workbench"),
                    "key": b["key"], "command": b["command"]})
    return out


def dump(bindings):
    return json.dumps({"bindings": bindings}, indent=2)


def resolve(bindings, workbench, key):
    for layer in LAYERS:
        for b in bindings:
            if b["layer"] == layer and b["key"] == key and (layer == "global" or b["workbench"] == workbench):
                return b["command"]
    return None


def conflicts(bindings):
    """Two bindings on the same key in the same layer (and workbench)."""
    seen, out = {}, []
    for b in bindings:
        k = (b["layer"], b["workbench"], b["key"])
        if k in seen and seen[k] != b["command"]:
            out.append(f"{b['layer']} {b['workbench'] or ''} {b['key']}: {seen[k]} vs {b['command']}")
        seen.setdefault(k, b["command"])
    return out


def path():
    import FreeCAD

    return FreeCAD.getUserAppDataDir() + "UxHotkeys.json"


def load():
    try:
        with open(path(), encoding="utf-8") as f:
            return parse(f.read())
    except FileNotFoundError:
        return []


_state = {"bindings": [], "pending": None}


def reload():
    import FreeCAD

    _state["bindings"] = load()
    for c in conflicts(_state["bindings"]):
        FreeCAD.Console.PrintWarning(f"UX hotkey conflict: {c}\n")
    return _state["bindings"]


def active():
    """Bindings for the strip: workspace layer of the active workbench, then global."""
    import FreeCADGui as Gui

    wb = Gui.activeWorkbench().name() if Gui.activeWorkbench() else None
    return [b for b in _state["bindings"] if b["layer"] == "global" or b["workbench"] == wb]


def install():
    from PySide import QtCore, QtGui, QtWidgets
    import FreeCADGui as Gui

    TEXT = (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit, QtWidgets.QAbstractSpinBox,
            QtWidgets.QComboBox)

    class Filter(QtCore.QObject):
        def eventFilter(self, obj, ev):
            t = ev.type()
            if t not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
                return False
            if isinstance(QtWidgets.QApplication.focusWidget(), TEXT):
                return False
            key = QtGui.QKeySequence(ev.keyCombination()).toString()
            wb = Gui.activeWorkbench()
            cmd = resolve(_state["bindings"], wb.name() if wb else None, key)
            if not cmd:
                return False
            if t == QtCore.QEvent.ShortcutOverride:
                ev.accept()  # keep Qt shortcuts from taking the key
                _state["pending"] = cmd
                return False
            if _state["pending"] == cmd:
                _state["pending"] = None
                Gui.runCommand(cmd)
                return True
            return False

    reload()
    f = Filter(Gui.getMainWindow())
    QtWidgets.QApplication.instance().installEventFilter(f)
    Gui.getMainWindow()._ux_hotkey_filter = f

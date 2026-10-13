# SPDX-License-Identifier: LGPL-2.1-or-later
"""Context-layered hotkeys: task-dialog layer, workspace layer, global layer. First match wins.

A dialog binding names the open task dialog by a case-insensitive part of its panel header
("Pad Parameters"), or "*" for any task dialog.

shortcut: no command (active-tool) layer and no chords; Python sees no tool-handler
start/finish. The command layer needs the upstream hook (design doc §4.2).
"""

import json

LAYERS = ("dialog", "workspace", "global")  # resolution order


def parse(text):
    """Return a list of bindings from JSON text; raise ValueError on bad shape."""
    data = json.loads(text)
    out = []
    for b in data.get("bindings", []):
        if b.get("layer") not in LAYERS or not b.get("key") or not b.get("command"):
            raise ValueError(f"bad binding: {b!r}")
        if b["layer"] == "workspace" and not b.get("workbench"):
            raise ValueError(f"workspace binding needs a workbench: {b!r}")
        if b["layer"] == "dialog" and not b.get("dialog"):
            raise ValueError(f"dialog binding needs a dialog title part or '*': {b!r}")
        out.append({"layer": b["layer"], "workbench": b.get("workbench"), "dialog": b.get("dialog"),
                    "key": b["key"], "command": b["command"]})
    return out


def dump(bindings, radial=None):
    data = {"bindings": bindings}
    if radial:
        data["radial"] = radial
    return json.dumps(data, indent=2)


def parse_radial(text):
    """{workbench name or "default": [command ids]} from JSON text."""
    radial = json.loads(text).get("radial", {})
    for name, cmds in radial.items():
        if not isinstance(cmds, list) or not all(isinstance(c, str) for c in cmds) or len(cmds) > 8:
            raise ValueError(f"radial menu '{name}': a list of at most 8 command ids")
    return radial


def _applies(b, workbench, dialogs):
    if b["layer"] == "global":
        return True
    if b["layer"] == "workspace":
        return b["workbench"] == workbench
    want = b["dialog"].lower()
    return bool(dialogs) and (want == "*" or any(want in d.lower() for d in dialogs))


def resolve(bindings, workbench, key, dialogs=()):
    """dialogs: header texts of the open task dialog (empty when none)."""
    for layer in LAYERS:
        for b in bindings:
            if b["layer"] == layer and b["key"] == key and _applies(b, workbench, dialogs):
                return b["command"]
    return None


def conflicts(bindings):
    """Two bindings on the same key in the same layer (and workbench)."""
    seen, out = {}, []
    for b in bindings:
        k = (b["layer"], b["workbench"], b.get("dialog"), b["key"])
        if k in seen and seen[k] != b["command"]:
            out.append(f"{b['layer']} {b['workbench'] or b.get('dialog') or ''} {b['key']}: {seen[k]} vs {b['command']}")
        seen.setdefault(k, b["command"])
    return out


def path():
    import FreeCAD

    return FreeCAD.getUserAppDataDir() + "UxHotkeys.json"


def read_text():
    try:
        with open(path(), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return '{"bindings": []}'


def load():
    return parse(read_text())


def save(bindings, radial=None):
    """Writes the profile; keeps the radial menus when `radial` is None."""
    if radial is None:
        radial = parse_radial(read_text())
    with open(path(), "w", encoding="utf-8") as f:
        f.write(dump(bindings, radial))
    reload()


_state = {"bindings": [], "pending": None}


def reload():
    import FreeCAD

    _state["bindings"] = load()
    for c in conflicts(_state["bindings"]):
        FreeCAD.Console.PrintWarning(f"UX hotkey conflict: {c}\n")
    return _state["bindings"]


def dialog_titles():
    """Header texts of the open task dialog ("Pad Parameters"); [] when none is open."""
    import FreeCADGui as Gui

    if not Gui.Control.activeDialog():
        return []
    from PySide import QtWidgets

    tasks = Gui.getMainWindow().findChild(QtWidgets.QWidget, "Tasks")  # the task view
    labels = tasks.findChildren(QtWidgets.QLabel) if tasks else []
    return [
        w.text() for w in labels
        if w.isVisible() and w.inherits("QSint::ActionLabel") and w.text()
    ] or ["*"]


def active():
    """Bindings for the strip: the open dialog's layer, the active workbench's, then global."""
    import FreeCADGui as Gui

    wb = Gui.activeWorkbench().name() if Gui.activeWorkbench() else None
    dialogs = dialog_titles()
    return sorted(
        (b for b in _state["bindings"] if _applies(b, wb, dialogs)),
        key=lambda b: LAYERS.index(b["layer"]),
    )


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
            if key in ("Alt+1", "Alt+2", "Alt+3", "Alt+4", "Alt+5"):
                import Suggest

                if t == QtCore.QEvent.ShortcutOverride and int(key[-1]) <= len(Suggest.current()):
                    ev.accept()
                    _state["pending"] = key
                    return False
                if t == QtCore.QEvent.KeyPress and _state["pending"] == key:
                    _state["pending"] = None
                    Suggest.run_nth(int(key[-1]))
                    return True
            wb = Gui.activeWorkbench()
            cmd = resolve(_state["bindings"], wb.name() if wb else None, key, dialog_titles())
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

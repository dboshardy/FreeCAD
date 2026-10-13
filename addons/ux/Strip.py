# SPDX-License-Identifier: LGPL-2.1-or-later
"""Heads-up hotkey strip: a status-bar label listing the active layers' bindings."""

import Hotkeys


def text(bindings, limit=8):
    """Innermost layer first: dialog, workspace, global."""
    ordered = sorted(bindings, key=lambda b: Hotkeys.LAYERS.index(b["layer"]))
    items = [f"{b['key']} {b['command'].split('_', 1)[-1]}" for b in ordered[:limit]]
    more = len(ordered) - limit
    return "  |  ".join(items) + (f"  (+{more})" if more > 0 else "") if items else "no hotkeys bound"


def next_text(commands):
    return "Next: " + "  ".join(f"Alt+{i} {n}" for i, n in enumerate(commands, 1)) if commands else ""


def full_text():
    import Suggest

    names = [Suggest.label(c) for c in Suggest.current()]
    return "  ||  ".join(t for t in (text(Hotkeys.active()), next_text(names)) if t)


_label = []


def toggle():
    from PySide import QtCore, QtWidgets
    import FreeCADGui as Gui

    if _label:
        _label.pop().deleteLater()
        return
    label = QtWidgets.QLabel()
    timer = QtCore.QTimer(label)
    timer.timeout.connect(lambda: label.setText(full_text()))
    timer.start(500)
    label.setText(full_text())
    Gui.getMainWindow().statusBar().addWidget(label)
    _label.append(label)

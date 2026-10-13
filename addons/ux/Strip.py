# SPDX-License-Identifier: LGPL-2.1-or-later
"""Heads-up hotkey strip: a status-bar label listing the active layers' bindings."""

import Hotkeys


def text(bindings, limit=8):
    """Workspace bindings first (Hotkeys.active order is file order), then global."""
    ordered = sorted(bindings, key=lambda b: b["layer"] != "workspace")
    items = [f"{b['key']} {b['command'].split('_', 1)[-1]}" for b in ordered[:limit]]
    more = len(ordered) - limit
    return "  |  ".join(items) + (f"  (+{more})" if more > 0 else "") if items else "no hotkeys bound"


_label = []


def toggle():
    from PySide import QtCore, QtWidgets
    import FreeCADGui as Gui

    if _label:
        _label.pop().deleteLater()
        return
    label = QtWidgets.QLabel()
    timer = QtCore.QTimer(label)
    timer.timeout.connect(lambda: label.setText(text(Hotkeys.active())))
    timer.start(500)
    label.setText(text(Hotkeys.active()))
    Gui.getMainWindow().statusBar().addWidget(label)
    _label.append(label)

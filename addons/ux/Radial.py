# SPDX-License-Identifier: LGPL-2.1-or-later
"""Radial menu: up to 8 commands around the cursor, per workbench."""

import math

DEFAULT = [
    "Std_ViewFitAll",
    "Std_Undo",
    "Std_Redo",
    "Std_ToggleVisibility",
    "Std_ViewIsometric",
    "Std_ViewFront",
    "Std_ViewTop",
    "Std_ViewRight",
]


def commands_for(radial, workbench):
    """The workbench's list, else the "default" list, else the built-in 8."""
    return list(radial.get(workbench) or radial.get("default") or DEFAULT)[:8]


def positions(n, radius):
    """(dx, dy) of n buttons on a circle, the first straight up, clockwise."""
    return [
        (round(radius * math.sin(2 * math.pi * i / n)), round(-radius * math.cos(2 * math.pi * i / n)))
        for i in range(n)
    ]


def show():
    from PySide import QtCore, QtGui, QtWidgets
    import FreeCADGui as Gui
    import Hotkeys

    wb = Gui.activeWorkbench()
    ids = commands_for(Hotkeys.parse_radial(Hotkeys.read_text()), wb.name() if wb else None)
    size, radius = 56, 90
    popup = QtWidgets.QWidget(Gui.getMainWindow(), QtCore.Qt.Popup)
    popup.setFixedSize(2 * radius + size, 2 * radius + size)
    for cmd, (dx, dy) in zip(ids, positions(len(ids), radius)):
        info = Gui.Command.get(cmd).getInfo() if cmd in Gui.listCommands() else None
        button = QtWidgets.QToolButton(popup)
        button.setFixedSize(size, size)
        button.move(radius + dx, radius + dy)
        button.setToolTip(info["menuText"].replace("&", "") if info else cmd)
        icon = QtGui.QIcon(info["pixmap"]) if info and info.get("pixmap") else QtGui.QIcon()
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(32, 32))
        if icon.isNull():
            button.setText((info["menuText"] if info else cmd).replace("&", "")[:8])
        button.clicked.connect(lambda _=False, c=cmd: (popup.close(), Gui.runCommand(c)))
    pos = QtGui.QCursor.pos()
    popup.move(pos.x() - popup.width() // 2, pos.y() - popup.height() // 2)
    popup.show()
    return popup

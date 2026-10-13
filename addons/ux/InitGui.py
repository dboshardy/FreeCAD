# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCADGui


class _PaletteCommand:
    def GetResources(self):
        return {
            "MenuText": "Command Palette",
            "ToolTip": "Search and run any command",
        }

    def IsActive(self):
        return True

    def Activated(self):
        import Palette

        Palette.show()


class _StripCommand:
    def GetResources(self):
        return {"MenuText": "Hotkey Strip", "ToolTip": "Show or hide the hotkeys of the active workbench"}

    def IsActive(self):
        return True

    def Activated(self):
        import Strip

        Strip.toggle()


class UxWorkbench(FreeCADGui.Workbench):
    MenuText = "CADApp UX"
    ToolTip = "Keyboard-first UX tools"

    def Initialize(self):
        self.appendMenu("UX", ["UX_CommandPalette", "UX_HotkeyStrip"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addCommand("UX_CommandPalette", _PaletteCommand())
FreeCADGui.addCommand("UX_HotkeyStrip", _StripCommand())


def _install_shortcut():
    # A command's Accel only fires when its action sits on a widget of the active workbench.
    from PySide import QtCore, QtGui

    win = FreeCADGui.getMainWindow()
    sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+P"), win)
    sc.setContext(QtCore.Qt.ApplicationShortcut)
    sc.activated.connect(lambda: FreeCADGui.runCommand("UX_CommandPalette"))
    win._ux_palette_shortcut = sc


_install_shortcut()

import Hotkeys

Hotkeys.install()
FreeCADGui.addWorkbench(UxWorkbench())

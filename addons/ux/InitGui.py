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


class _ModuleCommand:
    """A command that runs <module>.<function>()."""

    def __init__(self, text, tip, module, function="show"):
        self.res = {"MenuText": text, "ToolTip": tip}
        self.module, self.function = module, function

    def GetResources(self):
        return self.res

    def IsActive(self):
        return True

    def Activated(self):
        getattr(__import__(self.module), self.function)()


class UxWorkbench(FreeCADGui.Workbench):
    MenuText = "CADApp UX"
    ToolTip = "Keyboard-first UX tools"

    def Initialize(self):
        self.appendMenu("UX", ["UX_CommandPalette", "UX_RadialMenu", "UX_Hotkeys", "UX_HotkeyStrip"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addCommand("UX_CommandPalette", _PaletteCommand())
FreeCADGui.addCommand("UX_HotkeyStrip", _StripCommand())
FreeCADGui.addCommand(
    "UX_RadialMenu", _ModuleCommand("Radial Menu", "Up to 8 commands around the cursor", "Radial")
)
FreeCADGui.addCommand("UX_Hotkeys", _ModuleCommand("Hotkeys...", "Edit, import and export hotkeys", "Remap"))


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

import Suggest

Suggest.install()
FreeCADGui.addWorkbench(UxWorkbench())

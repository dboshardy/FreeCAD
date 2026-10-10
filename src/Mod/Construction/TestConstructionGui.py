# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: GUI tests of the Construction workbench and the core UX layer
# (FreeCAD -t TestConstructionGui): commands, menus, context hotkeys.

import json
import os
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

COMMANDS = [
    "Construction_BaseCabinet",
    "Construction_WallCabinet",
    "Construction_TallCabinet",
    "Construction_SinkCabinet",
    "Construction_CornerCabinet",
    "Construction_BaseRun",
    "Construction_WallRun",
    "Construction_Member",
    "Construction_WallFrame",
    "Construction_FloorFrame",
    "Construction_GableRoof",
    "Construction_Stair",
    "Construction_Deck",
    "Construction_Shed",
]


def process_events(ms=200):
    from PySide6 import QtTest  # not in FreeCAD's PySide shim

    QtTest.QTest.qWait(ms)  # waits in C++: no Python timer left at exit


class TestConstructionGui(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("ConstructionGuiTest")
        FreeCADGui.activateWorkbench("ConstructionWorkbench")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def test_commands_registered(self):
        registered = FreeCADGui.listCommands()
        for name in COMMANDS + [
            "Construction_Sheathing",
            "Construction_CutList",
            "Construction_Check",
            "Construction_Drawing",
            "Construction_Tutorials",
            "Std_CommandPalette",
            "Std_RadialMenu",
            "Std_HotkeysReload",
        ]:
            self.assertIn(name, registered)

    def test_tools_menu_has_core_ux_commands(self):
        menus = FreeCADGui.getMainWindow().menuBar().actions()
        tools = next(a.menu() for a in menus if a.text().replace("&", "") == "Tools")
        texts = [a.text().replace("&", "") for a in tools.actions()]
        for text in ("Command Palette", "Radial Menu", "Reload Hotkeys"):
            self.assertIn(text, texts)

    def test_create_commands(self):
        for name in COMMANDS:
            before = len(self.doc.Objects)
            FreeCADGui.runCommand(name)
            self.doc.recompute()
            self.assertGreater(len(self.doc.Objects), before, name)
            obj = self.doc.Objects[-1]
            self.assertNotIn("Invalid", obj.State, f"{name}: {obj.State}")
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.doc.getObject("WallFrame"))
        FreeCADGui.runCommand("Construction_Sheathing")
        self.assertIsNotNone(self.doc.getObject("Sheathing"))
        FreeCADGui.runCommand("Construction_CutList")
        FreeCADGui.runCommand("Construction_Check")
        for name in ("CutList", "SheetLayout", "LumberPlan", "Checks"):
            self.assertIsNotNone(self.doc.getObject(name), name)


class TestCoreUx(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("CoreUxTest")
        self.name = self.doc.Name

    def tearDown(self):
        while QtGui.QApplication.activePopupWidget():
            QtGui.QApplication.activePopupWidget().close()
        process_events()
        if self.name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.name)

    def popups(self):
        popup = QtGui.QApplication.activePopupWidget()
        return [popup] if popup else []

    def test_command_palette_opens_with_commands(self):
        FreeCADGui.runCommand("Std_CommandPalette")
        process_events()
        edits = [w for w in self.popups() if isinstance(w, QtGui.QLineEdit)]
        self.assertEqual(len(edits), 1)
        completer = edits[0].findChild(QtGui.QCompleter)
        model = completer.model()
        names = [model.index(r, 0).data() for r in range(model.rowCount())]
        self.assertTrue(any("Construction_Shed" in n for n in names))

    def test_radial_menu_shows_buttons(self):
        FreeCADGui.runCommand("Std_RadialMenu")
        process_events()
        buttons = [b for w in self.popups() for b in w.findChildren(QtGui.QToolButton)]
        self.assertEqual(len(buttons), 8)  # the default list has 8 commands


class TestContextHotkeys(unittest.TestCase):
    """A key bound to the Construction workspace layer runs its command."""

    def setUp(self):
        self.path = os.path.join(FreeCAD.getUserAppDataDir(), "Hotkeys.json")
        self.saved = None
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self.saved = f.read()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "bindings": [
                        {
                            "keys": ["Ctrl+Alt+J"],
                            "command": "Construction_BaseCabinet",
                            "layer": "workspace",
                            "scope": "ConstructionWorkbench",
                        }
                    ]
                },
                f,
            )
        self.doc = FreeCAD.newDocument("HotkeyTest")
        FreeCADGui.activateWorkbench("ConstructionWorkbench")
        FreeCADGui.runCommand("Std_HotkeysReload")  # the keymap was read at startup

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)
        if self.saved is None:
            os.remove(self.path)
        else:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(self.saved)

    def test_hotkey_strip_lists_bindings(self):
        window = FreeCADGui.getMainWindow()
        process_events(700)  # the strip refreshes every 300 ms
        texts = [w.text() for w in window.statusBar().findChildren(QtGui.QLabel)]
        self.assertTrue(any("Ctrl+Alt+J" in t and "Base Cabinet" in t for t in texts), texts)

    def test_workspace_key_runs_command(self):
        from PySide6 import QtTest  # not in FreeCAD's PySide shim

        window = FreeCADGui.getMainWindow()
        window.activateWindow()
        view = FreeCADGui.ActiveDocument.ActiveView.graphicsView()
        view.setFocus()
        process_events()
        QtTest.QTest.keyClick(
            view, QtCore.Qt.Key_J, QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier
        )
        process_events(500)  # the command runs from a zero-delay timer
        self.assertEqual([o.TypeId for o in self.doc.Objects], ["Part::FeaturePython"])
        self.assertEqual(self.doc.Objects[0].Name, "BaseCabinet")


if __name__ == "__main__":
    unittest.main()

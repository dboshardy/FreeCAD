# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI tests of the UX add-on: FreeCAD -t TestUxGui."""

import os
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets

import Hotkeys


def process_events(ms=200):
    from PySide6 import QtTest  # not in FreeCAD's PySide shim

    QtTest.QTest.qWait(ms)


def close_popups():
    while QtWidgets.QApplication.activePopupWidget():
        QtWidgets.QApplication.activePopupWidget().close()
    process_events()


class TestUxGui(unittest.TestCase):
    def setUp(self):
        self.path = Hotkeys.path()
        self.saved = Hotkeys.read_text() if os.path.exists(self.path) else None
        self.docs = set(FreeCAD.listDocuments())

    def tearDown(self):
        close_popups()
        if self.saved is None:
            if os.path.exists(self.path):
                os.remove(self.path)
        else:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(self.saved)
        Hotkeys.reload()
        for name in set(FreeCAD.listDocuments()) - self.docs:
            FreeCAD.closeDocument(name)

    def test_commands_registered(self):
        for cmd in ("UX_CommandPalette", "UX_RadialMenu", "UX_Hotkeys", "UX_HotkeyStrip"):
            self.assertIn(cmd, FreeCADGui.listCommands())

    def test_palette_lists_commands(self):
        FreeCADGui.activateWorkbench("ConstructionWorkbench")  # a workbench's commands exist once it is loaded
        FreeCADGui.runCommand("UX_CommandPalette")
        process_events()
        popup = QtWidgets.QApplication.activePopupWidget()
        lst = popup.findChild(QtWidgets.QListWidget)
        edit = popup.findChild(QtWidgets.QLineEdit)
        edit.setText("construction shed")
        process_events()
        names = [lst.item(i).data(QtCore.Qt.UserRole) for i in range(lst.count())]
        self.assertIn("Construction_Shed", names)

    def test_radial_menu_has_eight_buttons(self):
        FreeCADGui.runCommand("UX_RadialMenu")
        process_events()
        popup = QtWidgets.QApplication.activePopupWidget()
        self.assertEqual(len(popup.findChildren(QtWidgets.QToolButton)), 8)

    def test_global_key_runs_its_command(self):
        from PySide6 import QtTest  # not in FreeCAD's PySide shim

        with open(self.path, "w", encoding="utf-8") as f:
            f.write(Hotkeys.dump([{"layer": "global", "workbench": None, "key": "Ctrl+Alt+J", "command": "Std_New"}]))
        Hotkeys.reload()
        FreeCADGui.getMainWindow().activateWindow()
        before = len(FreeCAD.listDocuments())
        QtTest.QTest.keyClick(
            FreeCADGui.getMainWindow(), QtCore.Qt.Key_J, QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier
        )
        process_events()
        self.assertEqual(len(FreeCAD.listDocuments()), before + 1)

    def test_strip_shows_bindings_and_suggestions(self):
        import Strip
        import Suggest

        with open(self.path, "w", encoding="utf-8") as f:
            f.write(Hotkeys.dump([{"layer": "global", "workbench": None, "key": "Ctrl+Alt+J", "command": "Std_New"}]))
        Hotkeys.reload()
        FreeCADGui.runCommand("UX_HotkeyStrip")
        process_events(700)
        labels = [w.text() for w in FreeCADGui.getMainWindow().statusBar().findChildren(QtWidgets.QLabel)]
        self.assertTrue(any("Ctrl+Alt+J New" in t for t in labels), labels)
        doc = FreeCAD.newDocument("UxStrip")
        doc.addObject("Sketcher::SketchObject", "Sketch")
        self.assertEqual(Suggest.current()[0], "PartDesign_Pad")
        process_events(700)
        labels = [w.text() for w in FreeCADGui.getMainWindow().statusBar().findChildren(QtWidgets.QLabel)]
        self.assertTrue(any("Alt+1" in t for t in labels), labels)
        FreeCADGui.runCommand("UX_HotkeyStrip")  # hide again
        process_events()

    def test_remap_dialog_edits_and_saves(self):
        import Remap

        with open(self.path, "w", encoding="utf-8") as f:
            f.write(Hotkeys.dump([{"layer": "global", "workbench": None, "key": "F8", "command": "Std_New"}]))
        dlg = Remap.show()
        table = dlg.findChild(QtWidgets.QTableWidget)
        self.assertEqual(table.rowCount(), 1)
        table.item(0, 2).setText("F9")
        for b in dlg.findChildren(QtWidgets.QPushButton):
            if b.text() == "Save":
                b.click()
        self.assertEqual(Hotkeys.load()[0]["key"], "F9")

# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI tests of the Body Tools add-on: FreeCAD -t TestBodyToolsGui."""

import json
import os
import tempfile
import unittest

import FreeCAD
import FreeCADGui
import Part

import Commands
import Parameters
import Strip
import TestBodyTools
import VariantDialog

V = FreeCAD.Vector


class TestBodyToolsGui(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self._notify, Commands.notify = Commands.notify, lambda t, text, warning=False: self.messages.append(text)
        self.doc = FreeCAD.newDocument("BtGui")
        self.body, self.sheet, self.volume = TestBodyTools._bracket(self.doc)

    def tearDown(self):
        Commands.notify = self._notify
        FreeCAD.closeDocument(self.doc.Name)

    def test_strip_lists_features_and_marker(self):
        strip = Strip.HistoryStrip(self.body, notify=self.messages.append)
        self.assertEqual(strip.count(), 30)
        item = next(strip.item(i) for i in range(strip.count()) if strip.item(i).text() == "Hole0_0")
        strip._marker(item)
        self.assertIs(self.body.Tip, self.doc.getObject("Hole0_0"))
        bold = [strip.item(i).text() for i in range(strip.count()) if strip.item(i).font().bold()]
        self.assertEqual(bold, ["Hole0_0"])

    def test_strip_refuses_bad_move(self):
        import History

        strip = Strip.HistoryStrip(self.body, notify=self.messages.append)
        plate = self.doc.getObject("Plate")
        with self.assertRaises(ValueError):
            History.move(self.body, plate, len(self.body.Group) - 1)
        self.assertEqual(strip.count(), 30)

    def test_load_parameters_command(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p.json")
            json.dump({"plate_t": 8}, open(p, "w"))
            self._ask, Commands.ask_file = Commands.ask_file, lambda: p
            try:
                Commands.COMMANDS["BT_LoadParameters"].Activated()
            finally:
                Commands.ask_file = self._ask
        self.assertEqual(self.sheet.get("plate_t"), 8)
        self.assertAlmostEqual(self.body.Shape.Volume, self.volume(100, 60, 8, 4, 10), delta=1e-3)

    def test_variant_dialog_roundtrip(self):
        dlg = VariantDialog.VariantDialog(self.doc, self.sheet)
        dlg._append("thin", "params", "plate_t", 3)
        dlg._append("thin", "suppress", "Hole0_0", True)
        dlg.grid.setCurrentCell(0, 0)
        dlg.apply_selected()
        self.assertEqual(self.messages, [])
        want = self.volume(100, 60, 3, 4, 10) + 3.141592653589793 * 16 * 3
        self.assertAlmostEqual(self.body.Shape.Volume, want, delta=1e-3)

    def test_variant_dialog_rejects_bad_row(self):
        dlg = VariantDialog.VariantDialog(self.doc, self.sheet)
        dlg._append("v", "bogus", "k", 1)
        with self.assertRaises(ValueError):
            dlg.collect()

    def test_inspect_commands(self):
        FreeCADGui.Selection.addSelection(self.body)
        Commands.COMMANDS["BT_WallThickness"].Activated()
        self.assertIn("Thinnest faces", self.messages[-1])
        Commands.COMMANDS["BT_DraftAnalysis"].Activated()
        self.assertIn("draft", self.messages[-1])

# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI tests of the Sketch add-on: FreeCAD -t TestSketchGui."""

import unittest

import FreeCAD
import FreeCADGui
import Part
import Sketcher

V = FreeCAD.Vector


class TestSketchGui(unittest.TestCase):
    def setUp(self):
        import Commands

        self.messages = []
        self._notify, Commands.notify = Commands.notify, lambda title, text, warning=False: self.messages.append(text)
        self.doc = FreeCAD.newDocument("SketchGuiTest")
        self.sk = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        self.sk.addGeometry(
            [Part.LineSegment(V(0, 0, 0), V(100, 0, 0)), Part.LineSegment(V(100, 0, 0), V(0, 100, 0)),
             Part.LineSegment(V(0, 100, 0), V(0, 0, 0))],
            False,
        )
        self.doc.recompute()

    def tearDown(self):
        import Commands

        Commands.notify = self._notify
        FreeCADGui.Selection.clearSelection()
        FreeCAD.closeDocument(self.doc.Name)

    def test_commands_registered(self):
        for name in ("Sketch_TangentCircle", "Sketch_Stretch", "Sketch_Diagnose", "Sketch_Regions"):
            self.assertIn(name, FreeCADGui.listCommands())

    def test_tangent_circle_command_from_a_selection(self):
        for edge in ("Edge1", "Edge2", "Edge3"):
            FreeCADGui.Selection.addSelection(self.doc.Name, self.sk.Name, edge)
        FreeCADGui.runCommand("Sketch_TangentCircle")
        self.assertEqual(len(self.sk.Geometry), 4)
        self.assertAlmostEqual(self.sk.Geometry[3].Radius, 29.289, places=2)

    def test_regions_command_makes_a_group(self):
        FreeCADGui.Selection.addSelection(self.doc.Name, self.sk.Name)
        FreeCADGui.runCommand("Sketch_Regions")
        group = self.doc.getObject("SketchRegions")
        self.assertEqual(len(group.Group), 1)

    def test_diagnose_command_names_the_constraint_and_selects_it(self):
        self.sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 100))
        self.sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 90))
        FreeCADGui.Selection.addSelection(self.doc.Name, self.sk.Name)
        FreeCADGui.runCommand("Sketch_Diagnose")
        self.assertIn("Remove constraint 2", self.messages[-1])
        self.assertEqual(FreeCADGui.Selection.getSelectionEx()[0].SubElementNames, ("Constraint1",))

    def test_wrong_selection_reports_instead_of_failing(self):
        FreeCADGui.Selection.addSelection(self.doc.Name, self.sk.Name, "Edge1")
        FreeCADGui.runCommand("Sketch_TangentCircle")  # one line: fine
        self.messages.clear()
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.runCommand("Sketch_TangentCircle")  # nothing selected
        self.assertIn("select a sketch", self.messages[-1])

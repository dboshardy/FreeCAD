# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: tests of the Construction document objects in a running application
# (FreeCADCmd -t TestConstructionApp). TestConstruction.py covers the
# standalone geometry; this covers the FreeCAD side: objects, recompute,
# spreadsheets and drawings.

import unittest

import FreeCAD

import ConstructionObjects as CO


class TestConstructionApp(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("ConstructionAppTest")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def assertBuilt(self, obj):
        self.assertNotIn("Invalid", obj.State, f"{obj.Label}: {obj.State}")
        self.assertFalse(obj.Shape.isNull(), obj.Label)
        self.assertGreater(obj.Shape.Volume, 0, obj.Label)

    def test_every_object_builds(self):
        objects = [CO.make_cabinet(p, self.doc) for p in ("base", "wall", "tall", "sink", "corner")]
        objects.append(CO.make_cabinet_run("base", self.doc))
        objects.append(CO.make_member(doc=self.doc))
        for make in (
            CO.make_wall_frame,
            CO.make_floor_frame,
            CO.make_gable_roof,
            CO.make_stair,
            CO.make_deck,
            CO.make_shed,
        ):
            objects.append(make(self.doc))
        objects.append(CO.make_sheathing(self.doc.getObject("WallFrame"), self.doc))
        self.doc.recompute()
        for obj in objects:
            self.assertBuilt(obj)
        wall = self.doc.getObject("WallCabinet")
        self.assertAlmostEqual(wall.Placement.Base.z, 1400)

    def test_edit_regenerates(self):
        shed = CO.make_shed(self.doc)
        volume = shed.Shape.Volume
        top = shed.Shape.BoundBox.ZMax
        shed.WallHeight = 2700
        shed.DoorWidth = 1200
        self.doc.recompute()
        self.assertBuilt(shed)
        self.assertAlmostEqual(shed.Shape.BoundBox.ZMax, top + 260, delta=1)
        self.assertNotAlmostEqual(shed.Shape.Volume, volume)

    def test_bad_size_marks_object_invalid(self):
        cabinet = CO.make_cabinet("base", self.doc)
        cabinet.Depth = 100  # too shallow
        self.doc.recompute()
        self.assertIn("Invalid", cabinet.State)

    def test_member_follows_its_edge(self):
        import Part

        line = self.doc.addObject("Part::Feature", "Line")
        line.Shape = Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(3000, 0, 0))
        member = CO.make_member((line, ["Edge1"]), self.doc)
        self.assertAlmostEqual(member.Shape.BoundBox.XLength, 3000)
        line.Shape = Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(2000, 0, 0))
        self.doc.recompute()
        self.assertAlmostEqual(member.Shape.BoundBox.XLength, 2000)

    def test_cut_list_and_checks(self):
        CO.make_cabinet("tall", self.doc)
        CO.make_shed(self.doc)
        sheet = CO.write_cut_list(self.doc)
        self.assertEqual(sheet.get("A1"), "Material")
        for name in ("SheetLayout", "LumberPlan", "SheetLayoutView"):
            self.assertIsNotNone(self.doc.getObject(name), name)
        self.assertEqual(self.doc.getObject("LumberPlan").get("A1"), "Material")
        problems = CO.write_checks(self.doc)
        checks = self.doc.getObject("Checks")
        self.assertIn("Advisory only", checks.get("A1"))
        self.assertGreaterEqual(problems, 1)  # the tall cabinet must be anchored

    def test_drawing(self):
        shed = CO.make_shed(self.doc)
        page = CO.make_drawing([shed], self.doc)
        self.assertEqual(page.TypeId, "TechDraw::DrawPage")
        views = [v.TypeId for v in page.Views]
        self.assertIn("TechDraw::DrawProjGroup", views)
        table_page = self.doc.getObject("FramingCutList")
        self.assertIn("TechDraw::DrawViewSpreadsheet", [v.TypeId for v in table_page.Views])
        texts = page.Template.EditableTexts
        self.assertNotIn("Stainless", texts["part_material"])
        # One balloon per cut-list row of framing members, numbered like the Tag column.
        balloons = [v for v in page.Views if v.TypeId == "TechDraw::DrawViewBalloon"]
        cut = self.doc.getObject("CutList")
        tags = set()
        row = 2
        while cut.getContents(f"H{row}"):
            if not cut.get(f"A{row}").startswith("Plywood"):  # sheathing: not tagged
                tags.add(str(int(float(cut.get(f"H{row}")))))
            row += 1
        self.assertEqual(sorted(b.Text for b in balloons), sorted(tags))
        for b in balloons:
            self.assertNotIn("Invalid", b.State, b.Label)


if __name__ == "__main__":
    unittest.main()

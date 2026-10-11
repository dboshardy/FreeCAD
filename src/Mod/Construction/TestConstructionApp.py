# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: tests of the Construction document objects in a running application
# (FreeCADCmd -t TestConstructionApp). TestConstruction.py covers the
# standalone geometry; this covers the FreeCAD side: objects, recompute,
# spreadsheets and drawings.

import math
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
            CO.make_shed_roof,
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
        column_a = [sheet.getContents(f"A{r}") for r in range(1, 200)]
        self.assertTrue(any("Framing nail" in c for c in column_a))  # the shed's schedule
        problems = CO.write_checks(self.doc)
        checks = self.doc.getObject("Checks")
        self.assertIn("Advisory only", checks.get("A1"))
        self.assertGreaterEqual(problems, 1)  # the tall cabinet must be anchored

    def test_ifc_export(self):
        import os
        import tempfile

        import ifcopenshell
        from importers import exportIFC

        objects = [CO.make_shed(self.doc), CO.make_cabinet("base", self.doc)]
        objects.append(CO.make_wall_frame(self.doc))
        objects.append(CO.make_sheathing(objects[-1], self.doc))
        path = os.path.join(tempfile.mkdtemp(), "construction.ifc")
        exportIFC.export(objects, path)
        ifc = ifcopenshell.open(path)
        for ifc_type, count in (
            ("IfcElementAssembly", 1),
            ("IfcFurnishingElement", 1),
            ("IfcWall", 1),
            ("IfcCovering", 1),
        ):
            self.assertEqual(len(ifc.by_type(ifc_type)), count, ifc_type)

    def test_build(self):
        build = CO.make_build(self.doc)
        leg = "lumber.metric.hw.45x45"
        CO.add_board(build, "Leg 1", leg, 600, (0, 0, 0), "z", "x")
        CO.add_board(build, "Leg 2", leg, 600, (455, 0, 0), "z", "x")
        apron = CO.add_board_between(build, "Leg 1", "Leg 2", stock="lumber.metric.hw.20x95")
        self.assertEqual(apron, "Board 1")
        build.Proxy.add_joint(build, "Leg*", "Board*", "joint.mortise_tenon")
        self.doc.recompute()
        self.assertBuilt(build)
        self.assertEqual(len(build.Shape.childShapes()), 3)
        # Two mortises of 6.7 x 75 x 25 cut from the legs; the tenons add the same back.
        volume = 2 * 45 * 45 * 600 + 410 * 20 * 95
        self.assertAlmostEqual(build.Shape.Volume, volume, delta=1)
        face = next(
            f"Face{i}"
            for i, f in enumerate(build.Shape.Faces, start=1)
            if abs(f.CenterOfMass.x - 250) < 1 and f.CenterOfMass.z > 590
        )
        self.assertEqual(build.Proxy.part_at(build, face), 2)  # the apron's top
        cut = CO.write_cut_list(self.doc)
        self.assertEqual(cut.get("I1"), "Operations")
        ops = [cut.getContents(f"I{r}") for r in range(2, 6)]
        self.assertTrue(any("mortise" in o for o in ops), ops)
        build.PartsTable.set("C2", "700")  # edit a leg's length in the table
        self.doc.recompute()
        self.assertAlmostEqual(build.Shape.BoundBox.ZMax, 700)

    def test_end_table_by_hand_matches_template(self):
        # Phase 5.1 exit criterion: a 500 x 500 x 600 end table built by hand, with the
        # mortise and tenon applied once and repeated for similar pairs, equals the template.
        import Build
        import CutList

        hand = CO.make_build(self.doc, "Hand")
        leg, apron = "lumber.metric.hw.45x45", "lumber.metric.hw.20x95"
        for n, (x, y) in enumerate(((25, 25), (430, 25), (430, 430), (25, 430)), start=1):
            CO.add_board(hand, f"Leg {n}", leg, 582, (x, y, 0), "z", "x")
        CO.add_board_between(hand, "Leg 1", "Leg 2", "Apron 1", apron)
        hand.PartsTable.set("G6", "30")  # Y: 5 mm back from the legs' outer face
        CO.add_board(hand, "Apron 2", apron, 360, (450, 70, 487), "y", "x")
        CO.add_board(hand, "Apron 3", apron, 360, (70, 450, 487), "x", "y")
        CO.add_board(hand, "Apron 4", apron, 360, (30, 70, 487), "y", "x")
        CO.add_panel(hand, "Top", "sheet.metric.edge_glued.18", 500, 500, (0, 0, 582))
        # The Joint command with "Apply to similar": Leg 1 / Apron 1 -> Leg* / Apron*.
        hand.Proxy.add_joint(
            hand, Build.similar("Leg 1"), Build.similar("Apron 1"), "joint.mortise_tenon"
        )
        hand.Proxy.add_joint(hand, Build.similar("Apron 1"), "Top", "joint.figure8")
        template = CO.make_end_table(self.doc)
        self.doc.recompute()
        for build in (hand, template):
            self.assertBuilt(build)
        self.assertEqual(hand.Proxy.parts(hand), template.Proxy.parts(template))
        parts = hand.Proxy.parts(hand)
        rows = {r[1]: r for r in CutList.rows(parts)}
        ops = dict(zip((r[1] for r in CutList.rows(parts)), CutList.operations(parts)))
        self.assertEqual(rows["Apron 1"][2:], (410, 95, 20, "yes", 4))  # 360 + two 25 tenons
        self.assertEqual(rows["Leg 1"][2:], (582, 45, 45, "yes", 4))
        self.assertEqual(ops["Leg 1"], "2 x mortise 75 x 6.7 x 25 deep")
        self.assertEqual(hand.Proxy.fasteners(hand, None), {"hardware.figure8": 8})
        self.assertAlmostEqual(hand.Shape.Volume, template.Shape.Volume)

    def test_cabinet_joints(self):
        cabinet = CO.make_cabinet("base", self.doc)
        self.assertEqual(cabinet.CarcassJoint, "joint.confirmat")
        choices = cabinet.getEnumerationsOfProperty("CarcassJoint")
        self.assertIn("joint.dado", choices)
        for other in ("joint.concealed_hinge", "joint.shelf_pins", "joint.figure8"):
            self.assertNotIn(other, choices)
        volume = cabinet.Shape.Volume
        cabinet.CarcassJoint = "joint.dado"  # housings: the bottom grows into the sides
        self.doc.recompute()
        self.assertBuilt(cabinet)
        # The dado moves material between parts; the confirmat holes are gone:
        # 12 screws, 5 mm holes through the 18 mm side and 35 mm into the bottom edge.
        holes = 12 * math.pi * 2.5**2 * (18 + 35)
        self.assertAlmostEqual(cabinet.Shape.Volume - volume, holes, delta=1)
        bottom = dict((p.name, p) for _, p in cabinet.Proxy.parts(cabinet))["Bottom"]
        self.assertEqual(bottom.size[0], 564 + 12)
        cut = CO.write_cut_list(self.doc)
        column_a = [cut.getContents(f"A{r}") for r in range(1, 80)]
        self.assertTrue(any("Concealed hinge" in c for c in column_a))

    def test_bookcase_is_anchored(self):
        bookcase = CO.make_bookcase(self.doc)
        self.assertBuilt(bookcase)
        cut = CO.write_cut_list(self.doc)
        rows = {
            cut.getContents(f"A{r}").lstrip("'"): cut.getContents(f"G{r}") for r in range(1, 80)
        }
        anchor = next(k for k in rows if k.startswith("Wall anchor"))
        self.assertEqual(rows[anchor], "2")
        self.assertGreaterEqual(CO.write_checks(self.doc), 1)  # anchoring required

    def test_templates_cut_and_check(self):
        for make in (CO.make_end_table, CO.make_dining_table, CO.make_workbench, CO.make_bookcase):
            self.assertBuilt(make(self.doc))
        cut = CO.write_cut_list(self.doc)  # every part fits its stock and sheets
        self.assertEqual(cut.get("A1"), "Material")
        CO.write_checks(self.doc)

    def test_region_costs_and_coverings(self):
        CO.set_document_region(self.doc, "US")
        cabinet = CO.make_cabinet("base", self.doc)
        choices = cabinet.getEnumerationsOfProperty("CarcassMaterial")
        self.assertIn("sheet.us.plywood.3-4", choices)
        self.assertNotIn("sheet.metric.plywood.12", choices)
        self.assertIn("sheet.metric.plywood.18", choices)  # the current value stays
        self.doc.removeObject(cabinet.Name)
        CO.set_document_region(self.doc, "all")
        shed = CO.make_shed(self.doc)
        shed.RoofCovering = "area.roofing.asphalt_shingles"
        saved = CO._items
        try:
            CO._items = {**saved}
            for key, price in (
                ("sheet.metric.plywood.12", 30),
                ("area.roofing.asphalt_shingles", 25),
            ):
                CO._items[key] = {**saved[key], "price": price}
            cut = CO.write_cut_list(self.doc)
        finally:
            CO._items = saved
        rows = {cut.getContents(f"A{r}").lstrip("'"): r for r in range(1, 120)}
        shingles = rows["Asphalt shingles, bundle"]
        # Two roof slopes of 3600 x 2012: 14.5 m² + 15 % at 3.1 m² -> 6 bundles, 25 each.
        self.assertEqual(cut.getContents(f"G{shingles}"), "6")
        self.assertEqual(cut.get(f"J{shingles}"), 150)
        total = rows["Total cost"]
        self.assertIn("without a price", cut.getContents(f"B{total}"))

    def test_floor_and_deck_options(self):
        floor = CO.make_floor_frame(self.doc)
        floor.Width = 6000
        floor.Beams = "3000"
        floor.PostHeight = 600
        floor.BlockingRows = 1
        floor.Openings = "900x1200 @ 1000, 800"
        deck = CO.make_deck(self.doc)
        deck.Attached = False
        self.doc.recompute()
        self.assertBuilt(floor)
        self.assertBuilt(deck)
        sheathing = CO.make_sheathing(floor, self.doc)
        self.assertBuilt(sheathing)
        # The stairwell is cut out of the subfloor.
        self.assertAlmostEqual(sheathing.Shape.Volume, (3600 * 6000 - 900 * 1200) * 18, delta=1)
        cut = CO.write_cut_list(self.doc)
        column_a = [cut.getContents(f"A{r}").lstrip("'") for r in range(1, 150)]
        self.assertIn("Concrete", column_a)
        self.assertTrue(any("Deck post footings" in c for c in column_a))

    def test_shed_roof(self):
        roof = CO.make_shed_roof(self.doc)
        self.assertBuilt(roof)
        self.assertAlmostEqual(roof.HighWallRise.Value, roof.Proxy.model(roof).rise())
        self.assertBuilt(CO.make_sheathing(roof, self.doc))

    def test_stair_landing(self):
        stair = CO.make_stair(self.doc)
        stair.LandingAfter = 7
        self.doc.recompute()
        self.assertBuilt(stair)
        self.assertGreater(stair.Shape.BoundBox.YLength, 13 * 271)  # 12 runs + landing

    def test_parametric_template(self):
        table = CO.make_end_table(self.doc)
        self.assertEqual(table.Template, "table")
        legs = lambda: [
            r for r in table.Proxy.part_rows(table) if r[0].startswith("Leg")
        ]  # noqa: E731
        table.Height = 650  # Phase 5.2 exit (b): one property
        self.doc.recompute()
        self.assertBuilt(table)
        self.assertEqual({r[2] for r in legs()}, {632.0})  # 650 - 18 top
        table.TopJoint = "joint.z_clip"
        self.doc.recompute()
        self.assertIn("hardware.z_clip", table.Proxy.fasteners(table, None))
        # A row edited by hand survives regeneration and is marked.
        table.PartsTable.set("C2", "700")  # Leg 1 length
        table.Width = 600
        self.doc.recompute()
        self.assertEqual(legs()[0][2], 700.0)
        self.assertEqual(legs()[1][2], 632.0)
        self.assertEqual(table.PartsTable.getContents("K2"), "'edited")
        table.Overhang = 400  # too big for the top: reported, not crashed
        self.doc.recompute()
        self.assertIn("Invalid", table.State)
        table.Overhang = 25
        self.doc.recompute()
        self.assertBuilt(table)
        shelf = CO.make_bookcase(self.doc)
        shelf.Shelves = 2
        self.doc.recompute()
        names = [r[0] for r in shelf.Proxy.part_rows(shelf)]
        self.assertNotIn("Shelf 3", names)

    def test_template_after_reopening(self):
        import os
        import tempfile

        CO.make_end_table(self.doc)
        path = os.path.join(tempfile.mkdtemp(), "table.FCStd")
        self.doc.saveAs(path)
        FreeCAD.closeDocument(self.doc.Name)
        self.doc = FreeCAD.openDocument(path)
        table = self.doc.getObject("EndTable")
        table.Height = 700
        self.doc.recompute()
        self.assertBuilt(table)
        legs = [r[2] for r in table.Proxy.part_rows(table) if r[0].startswith("Leg")]
        self.assertEqual(set(legs), {682.0})

    def test_room_generates_runs_and_walls(self):
        import json

        import Part

        room = CO.make_room(self.doc)
        room.OpeningsData = json.dumps([[1, "window", 1200, 1000, 1200, 900]])
        room.GapsData = json.dumps([[2, "range", 900, 600]])
        room.BaseCabinetWalls = "1, 2"
        room.WallCabinetWalls = "1, 2"
        room.FrameWalls = True
        made = room.Proxy.generate(room)
        names = sorted(o.Name.split("_", 1)[1] for o in made)
        self.assertEqual(names, ["Base1", "Base2", "Upper1", "Upper2", "Wall1", "Wall2"])
        for obj in made:
            self.assertBuilt(obj)
        base1, base2 = self.doc.getObject("Room_Base1"), self.doc.getObject("Room_Base2")
        # The runs meet at the corner without colliding: wall 2's run starts past
        # wall 1's cabinets.
        common = base1.Shape.common(base2.Shape)
        self.assertLess(common.Volume, 1)
        # Both runs stand inside the room, against the walls.
        box = base1.Shape.BoundBox
        self.assertAlmostEqual(box.YMin, 0, delta=1e-6)  # backs on wall 1 (y = 0)
        self.assertAlmostEqual(box.YMax, 598, delta=1e-6)  # 580 deep + 18 mm doors
        self.assertAlmostEqual(box.XMax, 3600, delta=1e-6)
        self.assertGreater(self.doc.getObject("Room_Upper1").Shape.BoundBox.ZMin, 1000)
        self.assertIn("window", self.doc.getObject("Room_Wall1").Openings)
        # Fewer walls: what is no longer needed goes.
        room.WallCabinetWalls = ""
        room.Proxy.generate(room)
        self.assertIsNone(self.doc.getObject("Room_Upper1"))
        CO.write_cut_list(self.doc)
        # A room from a sketch of its walls.
        sketch = self.doc.addObject("Part::Feature", "Outline")
        sketch.Shape = Part.makePolygon(
            [
                FreeCAD.Vector(*p)
                for p in ((0, 0, 0), (4000, 0, 0), (4000, 3000, 0), (0, 3000, 0), (0, 0, 0))
            ]
        )
        other = CO.make_room(self.doc, "Box")
        other.Base = sketch
        self.doc.recompute()
        self.assertEqual(len(other.Proxy.model(other).walls), 4)

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

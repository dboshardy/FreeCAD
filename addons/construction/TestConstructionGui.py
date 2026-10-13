# SPDX-License-Identifier: LGPL-2.1-or-later
# GUI tests of the Construction workbench (FreeCAD -t TestConstructionGui):
# commands, menus, panels, dragging.

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
    "Construction_Slab",
    "Construction_WallFrame",
    "Construction_FloorFrame",
    "Construction_GableRoof",
    "Construction_ShedRoof",
    "Construction_Stair",
    "Construction_Deck",
    "Construction_Shed",
    "Construction_Garage",
]


def process_events(ms=200):
    from PySide6 import QtTest  # not in FreeCAD's PySide shim

    QtTest.QTest.qWait(ms)  # waits in C++: no Python timer left at exit


class TestTutorialsViewer(unittest.TestCase):
    def test_help_viewer_check_answers(self):
        import ConstructionCommands

        self.assertIsInstance(ConstructionCommands.help_viewer_available(), bool)


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
            "Construction_Build",
            "Construction_Board",
            "Construction_BoardBetween",
            "Construction_Panel",
            "Construction_Edit",
            "Construction_BuildSteps",
            "Construction_ExportCSV",
            "Construction_Room",
            "Construction_Joint",
            "Construction_Align",
            "Construction_Move",
            "Construction_Region",
            "Construction_Library",
            "Construction_EndTable",
            "Construction_DiningTable",
            "Construction_Workbench",
            "Construction_Bookcase",
        ]:
            self.assertIn(name, registered)

    def test_tutorials_open_in_a_tab(self):
        from PySide6 import QtCore, QtWidgets

        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        FreeCADGui.runCommand("Construction_Tutorials")
        process_events()
        tab = next(w for w in mdi.subWindowList() if w.windowTitle() == "Construction tutorials")
        try:
            browser = tab.widget()
            text = browser.toPlainText()
            self.assertIn("Construction Workbench Tutorials", text)
            self.assertNotIn("](", text)  # rendered, not raw Markdown
            self.assertNotIn("SPDX", text)  # the licence comment stays hidden
            # Following a link to another tutorial stays in the tab.
            link = QtCore.QUrl("01-cabinets.md")
            browser.setSource(browser.source().resolved(link))
            self.assertIn("Tutorial 1: Cabinets", browser.toPlainText())
        finally:
            tab.close()

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

    def test_joint_from_selection(self):
        import ConstructionObjects as CO

        build = CO.make_build(self.doc)
        leg = "lumber.metric.hw.45x45"
        CO.add_board(build, "Leg 1", leg, 600, (0, 0, 0), "z", "x")
        CO.add_board(build, "Leg 2", leg, 600, (455, 0, 0), "z", "x")
        CO.add_board_between(build, "Leg 1", "Leg 2", "Apron 1", "lumber.metric.hw.20x95")
        self.doc.recompute()

        def face(x, z):
            return next(
                f"Face{i}"
                for i, f in enumerate(build.Shape.Faces, start=1)
                if abs(f.CenterOfMass.x - x) < 1 and abs(f.CenterOfMass.z - z) < 1
            )

        FreeCADGui.Selection.clearSelection()
        # The apron first: the command makes the leg the receiver (the apron's end goes in).
        FreeCADGui.Selection.addSelection(build, face(250, 600))
        FreeCADGui.Selection.addSelection(build, face(22.5, 0))
        self.assertTrue(FreeCADGui.isCommandActive("Construction_Joint"))
        offered, previewed = [], []
        saved = QtGui.QInputDialog.getItem, QtGui.QInputDialog.getText

        def get_item(parent, title, label, labels, *args):
            if not offered:  # the joint list
                offered.extend(labels)
                return "Mortise and tenon", True
            # Keep / apply to similar / undo, asked with the joint already in the model.
            previewed.append(len(build.Proxy.joint_rows(build)))
            return next(c for c in labels if c.startswith("Apply")), True

        QtGui.QInputDialog.getItem = get_item
        QtGui.QInputDialog.getText = lambda parent, title, label, mode, text: ("depth=20", True)
        try:
            FreeCADGui.runCommand("Construction_Joint")
        finally:
            QtGui.QInputDialog.getItem, QtGui.QInputDialog.getText = saved
        self.assertEqual(previewed, [1])
        self.assertIn("Pocket screws", offered)
        self.assertNotIn("Half lap", offered)  # only joints for an end on a face
        self.assertEqual(
            build.Proxy.joint_rows(build), [("Leg*", "Apron*", "joint.mortise_tenon", "depth=20")]
        )
        self.doc.recompute()
        self.assertNotIn("Invalid", build.State)
        # J on the same pair again changes that joint instead of adding one. Face numbers
        # change with the joint, so select the parts again.
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(build, face(250, 600))
        FreeCADGui.Selection.addSelection(build, face(22.5, 0))
        saved = QtGui.QInputDialog.getItem, QtGui.QInputDialog.getText
        QtGui.QInputDialog.getItem = lambda parent, title, label, labels, *a: ("Dowels, 8 mm", True)
        QtGui.QInputDialog.getText = lambda parent, title, label, mode, text: (text, True)
        try:
            FreeCADGui.runCommand("Construction_Joint")
        finally:
            QtGui.QInputDialog.getItem, QtGui.QInputDialog.getText = saved
        self.assertEqual(build.Proxy.joint_rows(build), [("Leg*", "Apron*", "joint.dowel", "")])

    def test_board_on_selected_face(self):
        import ConstructionObjects as CO

        build = CO.make_build(self.doc)
        CO.add_board(build, "Leg 1", "lumber.metric.hw.45x45", 600, (0, 0, 0), "z", "x")
        self.doc.recompute()
        top = next(
            f"Face{i}"
            for i, f in enumerate(build.Shape.Faces, start=1)
            if abs(f.CenterOfMass.z - 600) < 1e-6
        )
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(build, top)
        FreeCADGui.runCommand("Construction_Panel")
        self.doc.recompute()
        panel = build.Proxy.parts(build)[-1][1]
        self.assertEqual((panel.size, panel.pos), ((45, 45, 18), (0, 0, 600)))

    def test_align_snaps_a_face(self):
        import ConstructionObjects as CO

        build = CO.make_build(self.doc)
        CO.add_board(build, "Leg 1", "lumber.metric.hw.45x45", 600, (0, 0, 0), "z", "x")
        CO.add_board(build, "Rail", "lumber.metric.hw.20x95", 400, (100, 200, 300), "x", "y")
        self.doc.recompute()

        def face(x=None, y=None):
            for i, f in enumerate(build.Shape.Faces, start=1):
                c = f.CenterOfMass
                if (x is None or abs(c.x - x) < 1e-6) and (y is None or abs(c.y - y) < 1e-6):
                    return f"Face{i}"

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(build, face(x=45))  # the leg's +x face
        FreeCADGui.Selection.addSelection(build, face(x=100))  # the rail's -x end
        self.assertTrue(FreeCADGui.isCommandActive("Construction_Align"))
        FreeCADGui.runCommand("Construction_Align")
        rail = build.Proxy.parts(build)[1][1]
        self.assertEqual(rail.pos, (45, 200, 300))  # its end now against the leg


class TestPanels(unittest.TestCase):
    """Phase 5.2 editing panels: lists with dropdowns instead of typed strings."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("PanelTest")
        FreeCADGui.activateWorkbench("ConstructionWorkbench")
        self.warning = QtGui.QMessageBox.warning
        self.warned = []
        QtGui.QMessageBox.warning = lambda *a: self.warned.append(a[-1])

    def tearDown(self):
        QtGui.QMessageBox.warning = self.warning
        FreeCADGui.Control.closeDialog()
        FreeCAD.closeDocument(self.doc.Name)

    def test_wall_openings(self):
        import ConstructionObjects as CO
        import ConstructionPanels

        wall = CO.make_wall_frame(self.doc)
        before = wall.Openings
        panel = ConstructionPanels.edit_panel(wall)
        panel.editors[0].add_row(["window", 1200, 1000, 1500, 900])
        self.assertTrue(panel.accept())
        self.assertIn("window 1200x1000 @ 1500 sill 900", wall.Openings)
        panel = ConstructionPanels.edit_panel(wall)
        panel.editors[0].add_row(["door", 900, 2100, 99999, 0])  # past the wall's end
        self.assertFalse(panel.accept())
        self.assertTrue(self.warned)
        self.assertNotIn("99999", wall.Openings)
        self.assertNotEqual(wall.Openings, before)

    def test_build_joint_dropdown(self):
        import ConstructionObjects as CO
        import ConstructionPanels

        table = CO.make_end_table(self.doc)
        panel = ConstructionPanels.edit_panel(table)
        joints = panel.editors[1]
        row = next(r for r, j in enumerate(joints.rows()) if j[1] == "Top")
        combo = joints.table.cellWidget(row, 2)
        combo.setCurrentIndex(combo.findData("joint.z_clip"))
        self.assertTrue(panel.accept())
        self.assertIn("hardware.z_clip", table.Proxy.fasteners(table, None))

    def test_run_and_floor(self):
        import ConstructionObjects as CO
        import ConstructionPanels

        run = CO.make_cabinet_run("base", self.doc)
        panel = ConstructionPanels.edit_panel(run)
        panel.editors[0].set_rows([(600, "drawers"), (800, "gap"), (600, "")])
        self.assertTrue(panel.accept())
        self.assertEqual(run.Widths, "600 drawers, 800 gap, 600")
        floor = CO.make_floor_frame(self.doc)
        panel = ConstructionPanels.edit_panel(floor)
        panel.editors[0].set_rows([(1500,)])
        panel.editors[1].set_rows([(900, 1000, 1000, 300)])
        self.assertTrue(panel.accept())
        self.assertEqual((floor.Beams, floor.Openings), ("1500", "900x1000 @ 1000, 300"))

    def test_double_click_opens_panel(self):
        import ConstructionObjects as CO

        wall = CO.make_wall_frame(self.doc)
        self.assertTrue(wall.ViewObject.Proxy.doubleClicked(wall.ViewObject))
        self.assertIsNotNone(FreeCADGui.Control.activeDialog())


class TestRoomPanel(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("RoomTest")
        FreeCADGui.activateWorkbench("ConstructionWorkbench")

    def tearDown(self):
        FreeCADGui.Control.closeDialog()
        FreeCAD.closeDocument(self.doc.Name)

    def test_l_kitchen_from_one_panel(self):
        # Phase 5.2 exit (a): an L-shaped kitchen from one panel, no ids, no spreadsheet.
        import ConstructionObjects as CO
        import ConstructionPanels

        room = CO.make_room(self.doc)
        panel = ConstructionPanels.edit_panel(room)
        walls, openings, gaps, use = panel.editors
        walls.set_rows([(3600, "left"), (2400, "left")])
        openings.set_rows([(1, "window", 1200, 1000, 1200, 900)])
        gaps.set_rows([(2, "range", 900, 600)])
        use.set_rows([(1, "yes", "no"), (2, "yes", "no")])
        self.assertTrue(panel.accept())
        run1, run2 = self.doc.getObject("Room_Base1"), self.doc.getObject("Room_Base2")
        self.assertTrue(run1.Widths.startswith("1000 blind_left"))
        self.assertIn("600 gap", run2.Widths)
        CO.write_cut_list(self.doc)
        self.assertIsNotNone(self.doc.getObject("CutList"))


class TestShedPanel(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("ShedPanelTest")

    def tearDown(self):
        FreeCADGui.Control.closeDialog()
        FreeCAD.closeDocument(self.doc.Name)

    def test_window_from_panel(self):
        # Phase 5.2 exit (c): a window added to a shed wall from a panel.
        import ConstructionObjects as CO
        import ConstructionPanels

        shed = CO.make_shed(self.doc)
        panel = ConstructionPanels.edit_panel(shed)
        editor = panel.editors[0]
        self.assertEqual(editor.rows()[0][:2], ("front", "door"))  # the default door shows
        editor.add_row(["right", "window", 600, 600, 1000, 1200])
        self.assertTrue(panel.accept())
        model = shed.Proxy.model(shed)
        self.assertEqual([o.kind for o in model.wall_openings("right")], ["window"])
        self.assertEqual([o.kind for o in model.wall_openings("front")], ["door"])


class TestDrag(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("DragTest")
        FreeCADGui.activateWorkbench("ConstructionWorkbench")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def test_drag_snaps_to_a_face(self):
        # Phase 5.2 exit (d): a board dragged to a new position snaps to a face.
        import ConstructionDrag
        import ConstructionObjects as CO

        build = CO.make_build(self.doc)
        CO.add_board(build, "Leg 1", "lumber.metric.hw.45x45", 600, (0, 0, 0), "z", "x")
        CO.add_board(build, "Rail", "lumber.metric.hw.20x95", 400, (100, 200, 300), "x", "y")
        self.doc.recompute()
        # Grab the rail's top face (z = 395) and pull it 52 mm left, 13 mm back.
        drag = ConstructionDrag.DragPart(build, "Rail", 2, 395)
        drag.move_to((300, 210, 395))
        pos = drag.move_to((248, 223, 395))
        self.assertEqual(pos, (45, 215, 300))  # against the leg's face; y on the grid
        drag.finish()
        self.assertEqual(build.Proxy.drawn_parts(build)["Rail"].pos, (45, 215, 300))
        drag = ConstructionDrag.DragPart(build, "Rail", 2, 395)
        drag.move_to((0, 0, 395))
        drag.move_to((500, 500, 395))
        drag.cancel()  # Esc
        self.assertEqual(build.Proxy.drawn_parts(build)["Rail"].pos, (45, 215, 300))
        # The command starts the mouse drag from a selected face.
        face = next(
            f"Face{i}"
            for i, f in enumerate(build.Shape.Faces, start=1)
            if abs(f.CenterOfMass.z - 395) < 1e-6
        )
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(build, face)
        self.assertTrue(FreeCADGui.isCommandActive("Construction_Move"))
        # The mouse: two moves through the view, then Esc puts the rail back.
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewTop()
        view.fitAll()
        mouse = ConstructionDrag.start(build, "Rail", 2, 395)
        mouse.on_move({"Position": (200, 200)})
        mouse.on_move({"Position": (400, 300)})  # some 100 mm on screen
        self.assertNotEqual(build.Proxy.drawn_parts(build)["Rail"].pos, (45, 215, 300))
        mouse.on_key({"Key": "ESCAPE", "State": "DOWN"})
        self.assertEqual(mouse.callbacks, [])
        self.assertEqual(build.Proxy.drawn_parts(build)["Rail"].pos, (45, 215, 300))


class TestLibraryPanel(unittest.TestCase):
    def test_add_lumber(self):
        import tempfile

        import ConstructionObjects as CO
        import ConstructionPanels
        import Library

        saved = Library.user_dir
        folder = tempfile.mkdtemp()
        Library.user_dir = lambda: folder  # never the real user library
        CO._items = None
        try:
            panel = ConstructionPanels.LibraryPanel(Library.LUMBER)
            panel.editor.add_row(
                [
                    "lumber.mine.oak.25x150",
                    "Oak 25x150",
                    25,
                    150,
                    "mm",
                    "1800 2400",
                    12.5,
                    "m",
                    "metric",
                ]
            )
            self.assertTrue(panel.accept())
            self.assertEqual(CO.items()["lumber.mine.oak.25x150"]["price"], 12.5)
            csv = os.path.join(folder, "lumber.csv")
            panel.export_csv(csv)
            self.assertTrue(os.path.getsize(csv) > 0)
        finally:
            Library.user_dir = saved
            CO._items = None

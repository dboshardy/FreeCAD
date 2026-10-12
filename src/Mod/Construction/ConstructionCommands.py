# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: Construction workbench commands (design doc §5).

import fnmatch

import FreeCAD
import FreeCADGui

translate = FreeCAD.Qt.translate
QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP


class MakeCommand:
    """Creates a construction object with ConstructionObjects.<factory>(kind)."""

    def __init__(self, factory, kind, menu_text, tool_tip):
        self.factory, self.kind = factory, kind
        self.resources = {"MenuText": menu_text, "ToolTip": tool_tip}

    def GetResources(self):
        return self.resources

    def Activated(self):
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        doc.openTransaction(translate("Construction", "Create cabinet"))
        FreeCADGui.addModule("ConstructionObjects")
        FreeCADGui.doCommand(f"obj = ConstructionObjects.{self.factory}({self.kind!r})")
        doc.commitTransaction()
        FreeCADGui.doCommand("Gui.Selection.clearSelection()")
        FreeCADGui.doCommand("Gui.Selection.addSelection(obj)")


class MemberCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Member", "Member"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Member",
                "Creates lumber members along the selected straight edges or sketch lines "
                "(they follow later edits); with nothing selected, a free member",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        bases = []
        for sel in FreeCADGui.Selection.getSelectionEx():
            names = sel.SubElementNames or [
                f"Edge{i}" for i, _ in enumerate(sel.Object.Shape.Edges, start=1)
            ]
            for name in names:
                if name.startswith("Edge"):
                    edge = sel.Object.Shape.getElement(name)
                    if edge.Curve.TypeId == "Part::GeomLine":
                        bases.append((sel.Object.Name, name))
        doc.openTransaction(translate("Construction", "Create member"))
        FreeCADGui.addModule("ConstructionObjects")
        if not bases:
            FreeCADGui.doCommand("ConstructionObjects.make_member()")
        for obj_name, edge in bases:
            FreeCADGui.doCommand(
                "ConstructionObjects.make_member("
                f"(App.ActiveDocument.getObject({obj_name!r}), [{edge!r}]))"
            )
        doc.commitTransaction()


class FramingCommand:
    """Creates a framing object with ConstructionObjects.<factory>()."""

    def __init__(self, factory, menu_text, tool_tip):
        self.factory = factory
        self.resources = {"MenuText": menu_text, "ToolTip": tool_tip}

    def GetResources(self):
        return self.resources

    def Activated(self):
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        doc.openTransaction(translate("Construction", "Create framing"))
        FreeCADGui.addModule("ConstructionObjects")
        FreeCADGui.doCommand(f"ConstructionObjects.{self.factory}()")
        doc.commitTransaction()


class SheathingCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Sheathing", "Sheathing"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Sheathing",
                "Covers the selected wall, floor or roof framing with sheet goods, "
                "seams staggered; the cut list lays the panels out on sheets",
            ),
        }

    def IsActive(self):
        import ConstructionObjects

        return any(
            isinstance(getattr(o, "Proxy", None), ConstructionObjects.FramingFeature)
            for o in FreeCADGui.Selection.getSelection()
        )

    def Activated(self):
        import ConstructionObjects

        doc = FreeCAD.ActiveDocument
        doc.openTransaction(translate("Construction", "Create sheathing"))
        FreeCADGui.addModule("ConstructionObjects")
        for o in FreeCADGui.Selection.getSelection():
            if isinstance(getattr(o, "Proxy", None), ConstructionObjects.FramingFeature):
                FreeCADGui.doCommand(
                    f"ConstructionObjects.make_sheathing(App.ActiveDocument.getObject({o.Name!r}))"
                )
        doc.commitTransaction()


class WallFrameCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_WallFrame", "Wall Framing"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_WallFrame",
                "Creates a stud wall: plates, studs, and framed door and window openings; "
                "edit length, height, spacing and openings in the property view",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        doc.openTransaction(translate("Construction", "Create wall framing"))
        FreeCADGui.addModule("ConstructionObjects")
        FreeCADGui.doCommand("ConstructionObjects.make_wall_frame()")
        doc.commitTransaction()


class CheckCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Check", "Check"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Check",
                "Advisory checks against the rule set in preferences (spreadsheet 'Checks'). "
                "Not a building code compliance check",
            ),
        }

    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        import ConstructionObjects

        return bool(ConstructionObjects.construction_objects(FreeCAD.ActiveDocument))

    def Activated(self):
        FreeCADGui.addModule("ConstructionObjects")
        FreeCADGui.doCommand("ConstructionObjects.write_checks(App.ActiveDocument)")


class DrawingCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Drawing", "Drawing"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Drawing",
                "Makes an A3 drawing page of the selected construction objects: front, top "
                "and right views and the cut list",
            ),
        }

    def IsActive(self):
        import ConstructionObjects

        doc = FreeCAD.ActiveDocument
        return bool(doc and ConstructionObjects.construction_objects(doc))

    def Activated(self):
        import ConstructionObjects

        doc = FreeCAD.ActiveDocument
        selected = [
            o
            for o in FreeCADGui.Selection.getSelection()
            if o in ConstructionObjects.construction_objects(doc)
        ]
        names = [o.Name for o in selected or ConstructionObjects.construction_objects(doc)]
        doc.openTransaction(translate("Construction", "Create drawing"))
        FreeCADGui.addModule("ConstructionObjects")
        objects = ", ".join(f"App.ActiveDocument.getObject({n!r})" for n in names)
        FreeCADGui.doCommand(f"ConstructionObjects.make_drawing([{objects}])")
        doc.commitTransaction()


class TutorialsCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Tutorials", "Tutorials"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Tutorials", "Opens the Construction workbench tutorials"
            ),
        }

    def Activated(self):
        import os

        import Help

        here = os.path.dirname(os.path.abspath(__file__))
        for folder in (
            os.path.join(here, "Tutorials"),  # installed
            os.path.join(here, "..", "..", "..", "docs", "tutorials", "construction"),  # source
        ):
            index = os.path.join(folder, "README.md")
            if os.path.exists(index):
                Help.show(os.path.normpath(index))
                return
        FreeCAD.Console.PrintError("Construction tutorials not found\n")


class CutListCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_CutList", "Cut List"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_CutList",
                "Writes the cut list and sheet estimate of all construction objects "
                "to the spreadsheet 'CutList'",
            ),
        }

    def IsActive(self):
        if not FreeCAD.ActiveDocument:
            return False
        import ConstructionObjects

        return bool(ConstructionObjects.construction_objects(FreeCAD.ActiveDocument))

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        doc.openTransaction(translate("Construction", "Cut list"))
        FreeCADGui.addModule("ConstructionObjects")
        FreeCADGui.doCommand("ConstructionObjects.write_cut_list(App.ActiveDocument)")
        doc.commitTransaction()


def selected_build_parts():
    """(build, [part names]) from the selection: faces clicked on one build's
    solids, in selection order. (None, []) when no build is selected."""
    import ConstructionObjects

    build, names = None, []
    for sel in FreeCADGui.Selection.getSelectionEx():
        obj = sel.Object
        if not isinstance(getattr(obj, "Proxy", None), ConstructionObjects.BuildFeature):
            continue
        build = build or obj
        if obj != build:
            continue
        rows = obj.Proxy.part_rows(obj)
        for element in sel.SubElementNames:
            index = obj.Proxy.part_at(obj, element)
            if index is not None and rows[index][0] not in names:
                names.append(rows[index][0])
    return build, names


def selected_faces(build):
    """[(part name, axis, sign, plane coordinate)] of the faces selected on the
    build, in selection order, in the build's coordinates."""
    out = []
    rows = build.Proxy.part_rows(build)
    inverse = build.Placement.inverse()
    for sel in FreeCADGui.Selection.getSelectionEx():
        if sel.Object != build:
            continue
        for element in sel.SubElementNames:
            if not element.startswith("Face"):
                continue
            face = build.Shape.getElement(element)
            normal = inverse.Rotation.multVec(face.normalAt(0, 0))
            axis = max(range(3), key=lambda n: abs(normal[n]))
            plane = inverse.multVec(face.CenterOfMass)[axis]
            name = rows[build.Proxy.part_at(build, element)][0]
            out.append((name, axis, 1 if normal[axis] > 0 else -1, plane))
    return out


def selected_face(build):
    """(part name, axis, sign) of the one face selected on the build, or None."""
    faces = selected_faces(build)
    return faces[0][:3] if len(faces) == 1 else None


class BuildCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Build", "Build"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Build",
                "Creates a woodworking build: one object with a parts table and a joints "
                "table. Add parts with Board, Board Between and Panel; join them with Joint",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        doc.openTransaction(translate("Construction", "Create build"))
        FreeCADGui.addModule("ConstructionObjects")
        FreeCADGui.doCommand("build = ConstructionObjects.make_build()")
        doc.commitTransaction()
        FreeCADGui.doCommand("Gui.Selection.clearSelection()")
        FreeCADGui.doCommand("Gui.Selection.addSelection(build)")


class AddPartCommand:
    """Adds a part to the selected build with ConstructionObjects.<factory>."""

    def __init__(self, factory, menu_text, tool_tip, needs=0, panel=None):
        self.factory, self.needs, self.panel = factory, needs, panel
        self.resources = {"MenuText": menu_text, "ToolTip": tool_tip}

    def GetResources(self):
        return self.resources

    def IsActive(self):
        build, names = selected_build_parts()
        return build is not None and len(names) >= self.needs

    def Activated(self):
        build, names = selected_build_parts()
        args = "".join(f", {n!r}" for n in names[: self.needs])
        factory = self.factory
        face = selected_face(build) if self.panel is not None else None
        if face:  # lie on the selected face
            factory, args = "add_on_face", f", {face[0]!r}, {face[1]}, {face[2]}, {self.panel}"
        build.Document.openTransaction(translate("Construction", "Add part"))
        FreeCADGui.addModule("ConstructionObjects")
        FreeCADGui.doCommand(
            f"ConstructionObjects.{factory}(App.ActiveDocument.{build.Name}{args})"
        )
        FreeCADGui.doCommand("App.ActiveDocument.recompute()")
        build.Document.commitTransaction()


class JointCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Joint", "Joint"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Joint",
                "Joins two selected parts of a build: pick a joint from the library "
                "(the list follows how the parts meet), once or for every similar pair",
            ),
            "Accel": "J",
        }

    def IsActive(self):
        return len(selected_build_parts()[1]) == 2

    def Activated(self):
        from PySide import QtGui

        import Build
        import ConstructionObjects as CO
        import Joinery
        import Library

        build, (receiver, inserted) = selected_build_parts()
        parts = build.Proxy.drawn_parts(build)
        how = Joinery.meets(parts[receiver], parts[inserted])
        if how != "end_to_face" and Joinery.meets(parts[inserted], parts[receiver]) in (
            "end_to_face",
            "edge_to_face",
        ):
            receiver, inserted = inserted, receiver  # the part whose end goes in
            how = Joinery.meets(parts[receiver], parts[inserted])
        window = FreeCADGui.getMainWindow()
        if how is None:
            QtGui.QMessageBox.warning(
                window,
                translate("Construction", "Joint"),
                translate("Construction", "{} and {} do not touch.").format(receiver, inserted),
            )
            return
        joints = [j for j in Library.of_category(CO.items(), "joint") if how in j.get("meets", ())]
        labels = [j["name"] for j in joints]
        title = translate("Construction", "Joint: {} into {}").format(inserted, receiver)
        # A joint already joining these parts is changed, not doubled.
        existing = next(
            (
                (r, row)
                for r, row in enumerate(build.Proxy.joint_rows(build), start=2)
                if fnmatch.fnmatchcase(receiver, row[0])
                and fnmatch.fnmatchcase(inserted, row[1])
                or fnmatch.fnmatchcase(inserted, row[0])
                and fnmatch.fnmatchcase(receiver, row[1])
            ),
            None,
        )
        current = 0
        prompt = how.replace("_", " ")
        if existing:
            title = translate("Construction", "Change joint: {} / {}").format(*existing[1][:2])
            ids = [j["id"] for j in joints]
            current = ids.index(existing[1][2]) if existing[1][2] in ids else 0
            prompt = translate("Construction", "Now: {}").format(existing[1][2])
        label, ok = QtGui.QInputDialog.getItem(window, title, prompt, labels, current, False)
        if not ok:
            return
        preset = joints[labels.index(label)]
        sizes = ", ".join(
            f"{key}={preset[key]:g}"
            for key in ("depth", "thickness", "shoulder", "spacing", "edge", "gap")
            if isinstance(preset.get(key), (int, float)) and not isinstance(preset[key], bool)
        )
        opts, ok = QtGui.QInputDialog.getText(
            window,
            title,
            translate("Construction", "Options (sizes in mm; empty = the preset's):"),
            QtGui.QLineEdit.Normal,
            sizes,
        )
        if not ok:
            return
        opts = "" if opts.strip() == sizes else opts.strip()
        doc = build.Document
        name = f"App.ActiveDocument.{build.Name}"
        doc.openTransaction(translate("Construction", "Joint"))
        if existing:
            r, row = existing
            FreeCADGui.doCommand(
                f"{name}.Proxy.set_joint({name}, {r}, {row[0]!r}, {row[1]!r}, "
                f"{preset['id']!r}, {opts!r})"
            )
            FreeCADGui.doCommand("App.ActiveDocument.recompute()")
            if "Invalid" in build.State:
                doc.abortTransaction()
                doc.recompute()
                QtGui.QMessageBox.warning(
                    window, title, translate("Construction", "This joint does not fit these parts.")
                )
                return
            doc.commitTransaction()  # undo with Edit > Undo
            return
        FreeCADGui.doCommand(
            f"row = {name}.Proxy.add_joint({name}, {receiver!r}, {inserted!r}, "
            f"{preset['id']!r}, {opts!r})"
        )
        FreeCADGui.doCommand("App.ActiveDocument.recompute()")
        if "Invalid" in build.State:  # e.g. a mortise breaking out of the part
            doc.abortTransaction()
            doc.recompute()
            QtGui.QMessageBox.warning(
                window, title, translate("Construction", "This joint does not fit these parts.")
            )
            return
        # The joint is in the model now: the user sees it before keeping it.
        pattern = Build.similar(receiver), Build.similar(inserted)
        keep = translate("Construction", "Keep for this pair")
        similar = translate("Construction", "Apply to every similar pair ({} / {})").format(
            *pattern
        )
        undo = translate("Construction", "Undo")
        choices = [keep] + ([similar] if pattern != (receiver, inserted) else []) + [undo]
        choice, ok = QtGui.QInputDialog.getItem(
            window, title, translate("Construction", "Joint added:"), choices, 0, False
        )
        if not ok or choice == undo:
            doc.abortTransaction()
            doc.recompute()
            return
        if choice == similar:
            FreeCADGui.doCommand(
                f"{name}.Proxy.set_joint({name}, row, {pattern[0]!r}, {pattern[1]!r}, "
                f"{preset['id']!r}, {opts!r})"
            )
            FreeCADGui.doCommand("App.ActiveDocument.recompute()")
        doc.commitTransaction()


class AlignCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Align", "Align"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Align",
                "Moves a part of a build so that the second selected face lies in the plane "
                "of the first: against it, or flush with it",
            ),
        }

    def IsActive(self):
        build, _ = selected_build_parts()
        if build is None:
            return False
        faces = selected_faces(build)
        return len(faces) == 2 and faces[0][1] == faces[1][1] and faces[0][0] != faces[1][0]

    def Activated(self):
        build, _ = selected_build_parts()
        (_, axis, _, target), (part, _, _, plane) = selected_faces(build)
        build.Document.openTransaction(translate("Construction", "Align"))
        FreeCADGui.addModule("ConstructionObjects")
        FreeCADGui.doCommand(
            f"ConstructionObjects.move_part(App.ActiveDocument.{build.Name}, {part!r}, "
            f"{axis}, {target - plane:.6g})"
        )
        FreeCADGui.doCommand("App.ActiveDocument.recompute()")
        build.Document.commitTransaction()


class RegionCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Region", "Library Region"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Region",
                "Chooses which region's lumber and sheet sizes this document offers "
                "(metric, US or all); generic items are always offered",
            ),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        from PySide import QtGui

        import ConstructionObjects as CO

        doc = FreeCAD.ActiveDocument
        current = CO.document_region(doc)
        region, ok = QtGui.QInputDialog.getItem(
            FreeCADGui.getMainWindow(),
            translate("Construction", "Library Region"),
            translate("Construction", "Library items for this document:"),
            list(CO.REGIONS),
            list(CO.REGIONS).index(current) if current in CO.REGIONS else 0,
            False,
        )
        if ok:
            FreeCADGui.addModule("ConstructionObjects")
            FreeCADGui.doCommand(
                f"ConstructionObjects.set_document_region(App.ActiveDocument, {region!r})"
            )


class EditCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Edit", "Edit"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Edit",
                "Edits the selected build, wall, floor or cabinet run in a panel: parts, "
                "joints, openings, beams or cabinets as lists with dropdowns (or double-click it)",
            ),
        }

    def IsActive(self):
        import ConstructionPanels

        sel = FreeCADGui.Selection.getSelection()
        return len(sel) == 1 and ConstructionPanels.edit_panel(sel[0]) is not None

    def Activated(self):
        import ConstructionPanels

        ConstructionPanels.show(FreeCADGui.Selection.getSelection()[0])


class RoomCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Room", "Room"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Room",
                "Enters a measured room: walls, doors, windows and appliance gaps. Chooses the "
                "walls for base and wall cabinets; makes the cabinet runs and wall framing",
            ),
        }

    def Activated(self):
        import ConstructionPanels

        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        doc.openTransaction(translate("Construction", "Room"))
        FreeCADGui.addModule("ConstructionObjects")
        FreeCADGui.doCommand("room = ConstructionObjects.make_room()")
        doc.commitTransaction()
        ConstructionPanels.show(doc.Objects[-1])


class MoveCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_Move", "Move Part"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_Move",
                "Drags the part of a build whose face is selected, in the plane of that face; "
                "it snaps against or flush with other parts' faces, else to a 5 mm grid. "
                "Click to place, Esc to cancel",
            ),
        }

    def IsActive(self):
        build, _ = selected_build_parts()
        return build is not None and len(selected_faces(build)) == 1

    def Activated(self):
        import ConstructionDrag

        build, _ = selected_build_parts()
        ((part, axis, _, plane),) = selected_faces(build)
        FreeCADGui.Selection.clearSelection()
        ConstructionDrag.start(build, part, axis, plane)


EDIT_HINT = "; edit its sizes in the property view"
CABINET_COMMANDS = {
    "Construction_BaseCabinet": MakeCommand(
        "make_cabinet",
        "base",
        QT_TRANSLATE_NOOP("Construction_BaseCabinet", "Base Cabinet"),
        QT_TRANSLATE_NOOP(
            "Construction_BaseCabinet", "Creates a frameless base cabinet" + EDIT_HINT
        ),
    ),
    "Construction_WallCabinet": MakeCommand(
        "make_cabinet",
        "wall",
        QT_TRANSLATE_NOOP("Construction_WallCabinet", "Wall Cabinet"),
        QT_TRANSLATE_NOOP(
            "Construction_WallCabinet", "Creates a frameless wall cabinet" + EDIT_HINT
        ),
    ),
    "Construction_TallCabinet": MakeCommand(
        "make_cabinet",
        "tall",
        QT_TRANSLATE_NOOP("Construction_TallCabinet", "Tall Cabinet"),
        QT_TRANSLATE_NOOP(
            "Construction_TallCabinet", "Creates a frameless tall cabinet" + EDIT_HINT
        ),
    ),
    "Construction_SinkCabinet": MakeCommand(
        "make_cabinet",
        "sink",
        QT_TRANSLATE_NOOP("Construction_SinkCabinet", "Sink Cabinet"),
        QT_TRANSLATE_NOOP(
            "Construction_SinkCabinet",
            "Creates a sink base cabinet: open back, false front over doors" + EDIT_HINT,
        ),
    ),
    "Construction_CornerCabinet": MakeCommand(
        "make_cabinet",
        "corner",
        QT_TRANSLATE_NOOP("Construction_CornerCabinet", "Blind Corner Cabinet"),
        QT_TRANSLATE_NOOP(
            "Construction_CornerCabinet",
            "Creates a blind corner base cabinet; set BlindWidth to the depth of the "
            "meeting run plus handle clearance" + EDIT_HINT,
        ),
    ),
    "Construction_BaseRun": MakeCommand(
        "make_cabinet_run",
        "base",
        QT_TRANSLATE_NOOP("Construction_BaseRun", "Base Cabinet Run"),
        QT_TRANSLATE_NOOP(
            "Construction_BaseRun",
            "Fills a wall length with base cabinets and fillers" + EDIT_HINT,
        ),
    ),
    "Construction_WallRun": MakeCommand(
        "make_cabinet_run",
        "wall",
        QT_TRANSLATE_NOOP("Construction_WallRun", "Wall Cabinet Run"),
        QT_TRANSLATE_NOOP(
            "Construction_WallRun",
            "Fills a wall length with wall cabinets and fillers" + EDIT_HINT,
        ),
    ),
}

for name, command in CABINET_COMMANDS.items():
    FreeCADGui.addCommand(name, command)
FreeCADGui.addCommand("Construction_Member", MemberCommand())
FreeCADGui.addCommand("Construction_WallFrame", WallFrameCommand())
FreeCADGui.addCommand(
    "Construction_FloorFrame",
    FramingCommand(
        "make_floor_frame",
        QT_TRANSLATE_NOOP("Construction_FloorFrame", "Floor Framing"),
        QT_TRANSLATE_NOOP(
            "Construction_FloorFrame",
            "Creates a floor platform: rim joists and joists on centres",
        ),
    ),
)
FreeCADGui.addCommand(
    "Construction_ShedRoof",
    FramingCommand(
        "make_shed_roof",
        QT_TRANSLATE_NOOP("Construction_ShedRoof", "Shed Roof"),
        QT_TRANSLATE_NOOP(
            "Construction_ShedRoof",
            "Creates mono-pitch roof framing: rafters from a low wall over a high wall "
            "(HighWallRise says how much taller to frame it)",
        ),
    ),
)
FreeCADGui.addCommand(
    "Construction_GableRoof",
    FramingCommand(
        "make_gable_roof",
        QT_TRANSLATE_NOOP("Construction_GableRoof", "Gable Roof"),
        QT_TRANSLATE_NOOP(
            "Construction_GableRoof",
            "Creates gable roof framing: rafters with birdsmouth and plumb cuts, ridge board, "
            "ceiling joists as rafter ties",
        ),
    ),
)
FreeCADGui.addCommand("Construction_Sheathing", SheathingCommand())
FreeCADGui.addCommand(
    "Construction_Deck",
    FramingCommand(
        "make_deck",
        QT_TRANSLATE_NOOP("Construction_Deck", "Deck"),
        QT_TRANSLATE_NOOP(
            "Construction_Deck",
            "Creates a deck against a house: ledger, joists, rim, beam on posts, decking",
        ),
    ),
)
FreeCADGui.addCommand(
    "Construction_Stair",
    FramingCommand(
        "make_stair",
        QT_TRANSLATE_NOOP("Construction_Stair", "Stair"),
        QT_TRANSLATE_NOOP(
            "Construction_Stair",
            "Creates a straight stair on cut stringers: equal risers within the rule set's "
            "limit, treads from whole boards",
        ),
    ),
)
FreeCADGui.addCommand(
    "Construction_Shed",
    FramingCommand(
        "make_shed",
        QT_TRANSLATE_NOOP("Construction_Shed", "Gable Shed"),
        QT_TRANSLATE_NOOP(
            "Construction_Shed",
            "Creates a gable shed template: floor, walls with a door, roof, sheathing; "
            "edit sizes and door in the property view",
        ),
    ),
)
FreeCADGui.addCommand("Construction_CutList", CutListCommand())
FreeCADGui.addCommand("Construction_Check", CheckCommand())
FreeCADGui.addCommand("Construction_Drawing", DrawingCommand())
FreeCADGui.addCommand("Construction_Tutorials", TutorialsCommand())
FreeCADGui.addCommand("Construction_Build", BuildCommand())
FreeCADGui.addCommand(
    "Construction_Board",
    AddPartCommand(
        "add_board",
        QT_TRANSLATE_NOOP("Construction_Board", "Board"),
        QT_TRANSLATE_NOOP(
            "Construction_Board",
            "Adds a board of the build's BoardStock, lying on the selected face of a part "
            "(else at the origin); edit its row in the parts table",
        ),
        panel=False,
    ),
)
FreeCADGui.addCommand(
    "Construction_BoardBetween",
    AddPartCommand(
        "add_board_between",
        QT_TRANSLATE_NOOP("Construction_BoardBetween", "Board Between"),
        QT_TRANSLATE_NOOP(
            "Construction_BoardBetween",
            "Adds a board spanning the gap between two selected parts of a build",
        ),
        needs=2,
    ),
)
FreeCADGui.addCommand(
    "Construction_Panel",
    AddPartCommand(
        "add_panel",
        QT_TRANSLATE_NOOP("Construction_Panel", "Panel"),
        QT_TRANSLATE_NOOP(
            "Construction_Panel",
            "Adds a panel of the build's PanelStock covering the selected face of a part "
            "(else at the origin); edit its row in the parts table",
        ),
        panel=True,
    ),
)
FreeCADGui.addCommand("Construction_Joint", JointCommand())
FreeCADGui.addCommand("Construction_Move", MoveCommand())
FreeCADGui.addCommand("Construction_Room", RoomCommand())
FreeCADGui.addCommand("Construction_Edit", EditCommand())
FreeCADGui.addCommand("Construction_Region", RegionCommand())
FreeCADGui.addCommand("Construction_Align", AlignCommand())
FreeCADGui.addCommand(
    "Construction_DiningTable",
    FramingCommand(
        "make_dining_table",
        QT_TRANSLATE_NOOP("Construction_DiningTable", "Dining Table"),
        QT_TRANSLATE_NOOP(
            "Construction_DiningTable",
            "Creates a dining table build: legs, mortise-and-tenon aprons and a top glued "
            "up from boards on figure-8 fasteners; edit it in its tables",
        ),
    ),
)
FreeCADGui.addCommand(
    "Construction_Workbench",
    FramingCommand(
        "make_workbench",
        QT_TRANSLATE_NOOP("Construction_Workbench", "Workbench"),
        QT_TRANSLATE_NOOP(
            "Construction_Workbench",
            "Creates a softwood workbench build: legs, aprons, a lower shelf on stretchers "
            "and a top glued up from boards; edit it in its tables",
        ),
    ),
)
FreeCADGui.addCommand(
    "Construction_Bookcase",
    FramingCommand(
        "make_bookcase",
        QT_TRANSLATE_NOOP("Construction_Bookcase", "Bookcase"),
        QT_TRANSLATE_NOOP(
            "Construction_Bookcase",
            "Creates a bookcase build: sides, top, bottom and fixed shelves in dados, a "
            "kick board and a nailed back; edit it in its parts and joints tables",
        ),
    ),
)
FreeCADGui.addCommand(
    "Construction_EndTable",
    FramingCommand(
        "make_end_table",
        QT_TRANSLATE_NOOP("Construction_EndTable", "End Table"),
        QT_TRANSLATE_NOOP(
            "Construction_EndTable",
            "Creates an end table build: legs, mortise-and-tenon aprons, a top on "
            "figure-8 fasteners; edit it in its parts and joints tables",
        ),
    ),
)

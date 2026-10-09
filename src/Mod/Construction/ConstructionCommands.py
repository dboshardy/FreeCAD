# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: Construction workbench commands (design doc §5).

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

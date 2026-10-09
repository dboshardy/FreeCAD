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
FreeCADGui.addCommand("Construction_CutList", CutListCommand())

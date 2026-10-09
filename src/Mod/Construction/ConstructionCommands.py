# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: Construction workbench commands (design doc §5).

import FreeCAD
import FreeCADGui

translate = FreeCAD.Qt.translate
QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP


class BaseCabinetCommand:
    def GetResources(self):
        return {
            "MenuText": QT_TRANSLATE_NOOP("Construction_BaseCabinet", "Base Cabinet"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Construction_BaseCabinet",
                "Creates a parametric frameless base cabinet; edit its sizes in the property view",
            ),
        }

    def Activated(self):
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        doc.openTransaction(translate("Construction", "Base cabinet"))
        FreeCADGui.addModule("ConstructionObjects")
        FreeCADGui.doCommand("obj = ConstructionObjects.make_base_cabinet()")
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


FreeCADGui.addCommand("Construction_BaseCabinet", BaseCabinetCommand())
FreeCADGui.addCommand("Construction_CutList", CutListCommand())

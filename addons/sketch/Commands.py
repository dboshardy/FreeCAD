# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCAD
import FreeCADGui


def _selection():
    import SketchTools

    return SketchTools.selection_in(FreeCADGui.Selection.getSelectionEx())


def notify(title, text, warning=False):
    """Shows a message; tests replace this to avoid a modal dialog."""
    from PySide import QtWidgets

    box = QtWidgets.QMessageBox.warning if warning else QtWidgets.QMessageBox.information
    box(FreeCADGui.getMainWindow(), title, text)


def _fail(error):
    FreeCAD.Console.PrintError(f"{error}\n")
    notify("Sketch tools", str(error), warning=True)


class _Command:
    text, tip = "", ""

    def GetResources(self):
        return {"MenuText": self.text, "ToolTip": self.tip}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        try:
            self.run()
        except (ValueError, RuntimeError) as e:
            _fail(e)


class TangentCircle(_Command):
    text = "Tangent Circle"
    tip = "Adds a circle tangent to the selected one to three curves of a sketch"

    def run(self):
        import SketchTools

        sketch, edges, _ = _selection()
        sketch.Document.openTransaction("Tangent circle")
        try:
            SketchTools.tangent_circle(sketch, edges)
        except Exception:
            sketch.Document.abortTransaction()
            raise
        sketch.Document.commitTransaction()
        sketch.Document.recompute()


class Stretch(_Command):
    text = "Stretch"
    tip = "Moves the selected sketch points by a distance; constraints drag what is attached"

    def run(self):
        import SketchTools
        from PySide import QtWidgets

        sketch, _, points = _selection()
        if not points:
            raise ValueError("select the sketch points to stretch")
        text, ok = QtWidgets.QInputDialog.getText(
            FreeCADGui.getMainWindow(), "Stretch", "Move by dx, dy (mm):", text="10, 0"
        )
        if not ok:
            return
        vector = SketchTools.parse_vector(text)
        sketch.Document.openTransaction("Stretch")
        try:
            if SketchTools.stretch(sketch, points, vector) != 0:
                raise ValueError("the constraints do not allow this stretch")
        except Exception:
            sketch.Document.abortTransaction()
            raise
        sketch.Document.commitTransaction()
        sketch.Document.recompute()


class Diagnose(_Command):
    text = "Diagnose Conflicts"
    tip = "Names the constraint whose removal makes an over-constrained sketch solve"

    def run(self):
        import SketchTools

        sketch, _, _ = _selection()
        found = SketchTools.diagnose(sketch)
        if not found:
            clean = not (sketch.ConflictingConstraints or sketch.RedundantConstraints)
            message = "No conflicting or redundant constraints." if clean else (
                "Conflicting constraints, but no single removal fixes them: "
                f"{sorted(sketch.ConflictingConstraints)}"
            )
        else:
            message = "\n".join(text for *_, text in found)
            number = found[0][0]
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(sketch.Document.Name, sketch.Name, f"Constraint{number - 1}")
        notify("Diagnose conflicts", message)


class Regions(_Command):
    text = "Show Regions"
    tip = "Colours the closed regions of a sketch, nested loops included"

    def run(self):
        import SketchTools

        sketch, _, _ = _selection()
        SketchTools.show_regions(sketch)


COMMANDS = {
    "Sketch_TangentCircle": TangentCircle(),
    "Sketch_Stretch": Stretch(),
    "Sketch_Diagnose": Diagnose(),
    "Sketch_Regions": Regions(),
}

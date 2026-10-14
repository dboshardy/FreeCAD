# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCAD
import FreeCADGui


def notify(title, text, warning=False):
    """Shows a message; tests replace this to avoid a modal dialog."""
    from PySide import QtWidgets

    box = QtWidgets.QMessageBox.warning if warning else QtWidgets.QMessageBox.information
    box(FreeCADGui.getMainWindow(), title, text)


def ask_file():
    """Path of a JSON file, or "" ; tests replace this."""
    from PySide import QtWidgets

    path, _ = QtWidgets.QFileDialog.getOpenFileName(
        FreeCADGui.getMainWindow(), "Parameters file", "", "JSON (*.json)"
    )
    return path


def _sheet(doc):
    sheets = doc.findObjects("Spreadsheet::Sheet")
    if not sheets:
        return doc.addObject("Spreadsheet::Sheet", "Params")
    return doc.getObject("Params") or sheets[0]


def _selected_sketch():
    for o in FreeCADGui.Selection.getSelection():
        if o.isDerivedFrom("Sketcher::SketchObject"):
            return o
    raise ValueError("Select a sketch first")


def _selected_body():
    for o in FreeCADGui.Selection.getSelection():
        if o.isDerivedFrom("PartDesign::Body"):
            return o
    body = FreeCADGui.ActiveDocument.ActiveView.getActiveObject("pdbody") if FreeCADGui.ActiveDocument else None
    if body is None:
        raise ValueError("Select a Body first")
    return body


class _Command:
    text, tip = "", ""

    def GetResources(self):
        return {"MenuText": self.text, "ToolTip": self.tip}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        try:
            self.run()
        except (ValueError, RuntimeError, OSError) as e:
            FreeCAD.Console.PrintError(f"{e}\n")
            notify(self.text, str(e), warning=True)


class LoadParameters(_Command):
    text = "Parameters from JSON"
    tip = "Reads name: value pairs from a JSON file into the Params spreadsheet aliases"

    def run(self):
        import Parameters

        path = ask_file()
        if not path:
            return
        names = Parameters.load_json(_sheet(FreeCAD.ActiveDocument), path)
        FreeCAD.ActiveDocument.recompute()
        notify(self.text, "Set: " + ", ".join(names))


class Variants(_Command):
    text = "Variants"
    tip = "Edit and apply named sets of parameter values, suppression and properties"

    def run(self):
        import VariantDialog

        VariantDialog.show(FreeCAD.ActiveDocument, _sheet(FreeCAD.ActiveDocument))


class ThinWall(_Command):
    text = "Thin-wall Extrude"
    tip = "Extrudes the selected sketch profile as a wall of given thickness"

    def run(self):
        import Features

        Features.make_thin_wall(_selected_sketch())
        FreeCAD.ActiveDocument.recompute()


class Rib(_Command):
    text = "Rib"
    tip = "Thickens the selected open profile into a rib, fused to the body shape if one is selected too"

    def run(self):
        import Features

        sel = FreeCADGui.Selection.getSelection()
        base = next((o for o in sel if hasattr(o, "Shape") and not o.isDerivedFrom("Sketcher::SketchObject")), None)
        Features.make_rib(_selected_sketch(), base)
        FreeCAD.ActiveDocument.recompute()


class _Inspect(_Command):
    def shape(self):
        sel = FreeCADGui.Selection.getSelection()
        if not sel or not hasattr(sel[0], "Shape") or sel[0].Shape.isNull():
            raise ValueError("Select an object with a shape")
        return sel[0].Shape


class DraftAnalysis(_Inspect):
    text = "Draft Analysis"
    tip = "Reports the draft angle of each face against the Z direction"

    def run(self):
        import Inspect

        rows = Inspect.draft_analysis(self.shape(), (0, 0, 1))
        bad = [f"Face{i}: {a:.2f} deg" for i, a, ok in rows if not ok]
        notify(self.text, "Faces below 1 deg draft:\n" + "\n".join(bad) if bad else "All faces have draft")


class WallThickness(_Inspect):
    text = "Wall Thickness"
    tip = "Estimates the thinnest wall at sampled points of each face"

    def run(self):
        import Inspect

        rows = sorted(Inspect.wall_thickness(self.shape()), key=lambda r: r[1])[:10]
        notify(self.text, "Thinnest faces:\n" + "\n".join(f"Face{i}: {t:.3f} mm" for i, t in rows))


class Interference(_Command):
    text = "Interference Check"
    tip = "Lists selected objects whose solids overlap"

    def run(self):
        import Inspect

        shapes = {o.Label: o.Shape for o in FreeCADGui.Selection.getSelection() if hasattr(o, "Shape")}
        if len(shapes) < 2:
            raise ValueError("Select two or more objects")
        hits = Inspect.interference(shapes)
        notify(self.text, "\n".join(f"{a} / {b}: {v:.3f} mm^3" for a, b, v in hits) or "No interference")


class HistoryStrip(_Command):
    text = "History Strip"
    tip = "Shows the features of the Body in a row; click to move the marker, drag to reorder"

    def run(self):
        from PySide import QtCore, QtWidgets

        import Strip

        body = _selected_body()
        dock = QtWidgets.QDockWidget(f"History: {body.Label}", FreeCADGui.getMainWindow())
        dock.setObjectName("BodyToolsHistory")
        dock.setWidget(Strip.HistoryStrip(body))
        FreeCADGui.getMainWindow().addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)
        dock.show()


COMMANDS = {
    "BT_LoadParameters": LoadParameters(),
    "BT_Variants": Variants(),
    "BT_ThinWall": ThinWall(),
    "BT_Rib": Rib(),
    "BT_DraftAnalysis": DraftAnalysis(),
    "BT_WallThickness": WallThickness(),
    "BT_Interference": Interference(),
    "BT_HistoryStrip": HistoryStrip(),
}

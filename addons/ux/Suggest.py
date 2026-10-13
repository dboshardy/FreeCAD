# SPDX-License-Identifier: LGPL-2.1-or-later
"""Next-tool suggestions: after an object is created, the commands that usually follow.
Rule-based; no usage statistics are kept."""

RULES = {
    "Sketcher::SketchObject": ["PartDesign_Pad", "PartDesign_Pocket", "PartDesign_Revolution", "PartDesign_Groove", "PartDesign_AdditiveLoft"],
    "PartDesign::Pad": ["PartDesign_Fillet", "PartDesign_Chamfer", "Sketcher_NewSketch", "PartDesign_Hole", "PartDesign_Pocket"],
    "PartDesign::Pocket": ["PartDesign_Fillet", "PartDesign_Chamfer", "PartDesign_Hole", "Sketcher_NewSketch"],
    "PartDesign::Revolution": ["PartDesign_Fillet", "PartDesign_Chamfer", "Sketcher_NewSketch"],
    "PartDesign::Fillet": ["PartDesign_Chamfer", "PartDesign_Hole", "Sketcher_NewSketch"],
    "PartDesign::Body": ["Sketcher_NewSketch", "PartDesign_Plane"],
}


def after(type_id, limit=5):
    return RULES.get(type_id, [])[:limit]


_state = {"last": [], "observer": None}


def current():
    return list(_state["last"])


def label(cmd):
    import FreeCADGui as Gui

    return Gui.Command.get(cmd).getInfo()["menuText"].replace("&", "") if cmd in Gui.listCommands() else cmd


def run_nth(n):
    """Runs the n-th suggestion (1-based); False when there is none."""
    import FreeCADGui as Gui

    cmds = _state["last"]
    if 0 < n <= len(cmds):
        Gui.runCommand(cmds[n - 1])
        return True
    return False


def install():
    import FreeCAD

    class Observer:
        def slotCreatedObject(self, obj):
            if FreeCAD.ActiveDocument and not obj.Document.Restoring:
                _state["last"] = after(obj.TypeId)

    _state["observer"] = Observer()
    FreeCAD.addDocumentObserver(_state["observer"])

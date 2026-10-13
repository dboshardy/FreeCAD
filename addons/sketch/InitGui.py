# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCADGui

import Commands  # the command classes live in a module: InitGui.py runs without module globals

for name, command in Commands.COMMANDS.items():
    FreeCADGui.addCommand(name, command)


class SketchToolsWorkbench(FreeCADGui.Workbench):
    MenuText = "CADApp Sketch"
    ToolTip = "Sketcher additions: tangent circle, stretch, conflict diagnosis, regions"

    def Initialize(self):
        self.appendMenu("Sketch tools", list(Commands.COMMANDS))
        self.appendToolbar("Sketch tools", list(Commands.COMMANDS))

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(SketchToolsWorkbench())

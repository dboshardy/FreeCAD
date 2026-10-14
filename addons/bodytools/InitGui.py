# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCADGui

import Commands  # the command classes live in a module: InitGui.py runs without module globals

for name, command in Commands.COMMANDS.items():
    FreeCADGui.addCommand(name, command)


class BodyToolsWorkbench(FreeCADGui.Workbench):
    MenuText = "CADApp Body Tools"
    ToolTip = "Parameters, variants, thin-wall, rib, inspection, history strip"

    def Initialize(self):
        self.appendMenu("Body tools", list(Commands.COMMANDS))
        self.appendToolbar("Body tools", list(Commands.COMMANDS))

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(BodyToolsWorkbench())

# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCADGui


class TemplateWorkbench(FreeCADGui.Workbench):
    MenuText = "CADApp Template"
    ToolTip = "Template workbench: copy and rename for a new add-on"

    def Initialize(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(TemplateWorkbench())

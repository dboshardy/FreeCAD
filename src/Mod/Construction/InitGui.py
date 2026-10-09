# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: Construction workbench (design doc §5).


class ConstructionWorkbench(Workbench):
    MenuText = "Construction"
    ToolTip = "Plan cabinets and construction: parametric generators, cut lists"

    def Initialize(self):
        import ConstructionCommands  # registers the commands

        commands = [
            "Construction_BaseCabinet",
            "Construction_WallCabinet",
            "Construction_TallCabinet",
            "Construction_SinkCabinet",
            "Construction_CornerCabinet",
            "Construction_BaseRun",
            "Construction_WallRun",
            "Construction_Member",
            "Construction_WallFrame",
            "Construction_FloorFrame",
            "Construction_GableRoof",
            "Construction_Stair",
            "Construction_Sheathing",
            "Construction_Shed",
            "Construction_CutList",
            "Construction_Check",
            "Construction_Drawing",
        ]
        self.appendToolbar("Construction", commands)
        self.appendMenu("&Construction", commands)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(ConstructionWorkbench())

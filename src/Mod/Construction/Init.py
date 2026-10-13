# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: Construction workbench (design doc §5).

FreeCAD.__unit_test__ += ["TestConstruction", "TestConstructionApp"]

# Material cards of the library items: shown in the Material workbench as the library "Construction".
import FreeCAD
import Library

FreeCAD.ParamGet(
    "User parameter:BaseApp/Preferences/Mod/Material/Resources/Modules/Construction"
).SetString("ModuleDir", Library.MATERIALS_DIR)

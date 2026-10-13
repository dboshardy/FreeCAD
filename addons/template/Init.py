# SPDX-License-Identifier: LGPL-2.1-or-later
# Runs at FreeCAD start. Registers the tests with `FreeCAD -t` / `FreeCADCmd -t`.

import FreeCAD

FreeCAD.__unit_test__ += ["TestTemplate"]

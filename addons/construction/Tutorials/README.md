<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork (design doc §5 Phase 5, §6 help content).
-->

# Construction Workbench Tutorials

The Construction workbench plans cabinets, furniture and light timber
framing: you set sizes or place boards and joints, it generates every part, and it writes cut lists, sheet layouts, lumber
buying plans, hardware lists and advisory safety checks.

| Tutorial | You will |
|---|---|
| [1. Cabinets](01-cabinets.md) | Make base, wall, tall, sink and corner cabinets; fill a wall with a cabinet run; get the cut list, sheet layout and hardware |
| [2. Framing](02-framing.md) | Place lumber members, frame a wall with a door and a window, frame a floor and a gable roof, add sheathing |
| [3. Build a shed](03-shed.md) | Create a complete gable shed from the template, change it, and get everything needed to buy and cut it |
| [4. Libraries, settings and checks](04-libraries-and-checks.md) | Add your own lumber and sheet sizes, set the saw kerf, enter loads and design values, read the checks |
| [5. Build an end table](05-end-table.md) | Make a build from boards and panels, join them with mortise and tenon and tabletop fasteners, and compare with the End Table template |
| [6. Construction objects are FreeCAD objects](06-freecad-objects.md) | Use BIM tools and IFC export on members, stairs, slabs, guards and sheet layouts; read density from Material cards |

## Before you start

- Switch to the workbench: **View > Workbench > Construction**. All commands are
  on the **Construction** toolbar and menu; **Construction > Tutorials** opens
  these pages.
- Sizes are in millimetres. Imperial values work too: type `16 in` or `8 ft`
  into a length property and it is converted.
- Every generated object is parametric. Select it and change its properties in
  the **Property view**; the model regenerates.
- If a size cannot be built, the object is marked with an error in the **Tree
  view** and the **Report view** says why, for example "cabinet too shallow for
  drawer slides". Fix the property and the object rebuilds.

## Safety

The checks are advisory. They do not show compliance with any building code.
Verify your design against the code adopted where you build, and have it
reviewed by your building official or a qualified professional. See
[tutorial 4](04-libraries-and-checks.md).

## For tutorial authors

Two kinds of code blocks appear in these tutorials:

- ```` ```pycon ```` blocks use the workbench's standalone modules (`Build`,
  `Cabinet`, `Framing`, `CutList`, `Library`, `Sheathing`, `Shed`, `Checks`). They run
  without the application, and `TestConstruction.py` runs every one with
  `doctest`: the printed output must match exactly.
- ```` ```py ```` blocks are for the Python console inside the application
  (they use `FreeCAD` and the document). They are not run by the tests.

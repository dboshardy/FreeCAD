<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Phase 5.2 Gap Inventory — Construction Usability

Audit of Phase 5.2 target scope (`docs/DESIGN.md`, Phase 5.2). Status:
**Present**, **Partial**, **Missing**.

| Scope item | Status | Notes |
|---|---|---|
| 1. Parametric templates | Present | Template presets (`Build.PRESETS`: end table, dining table, workbench, bookcase) put their sizes and choices on the build as properties (group Template: lengths, counts, stock and joint dropdowns). Changing one regenerates the tables (`BuildFeature.regenerate`); rows edited or added by hand are kept (`Build.merge`) and edited ones marked `edited`. A size the template cannot build marks the build invalid with the reason. Survives save and reopen |
| 2. Task panels with dropdowns | Partial | `ConstructionPanels.py`: one list editor (text, number and dropdown columns) used for a build's parts (stock and axes as dropdowns) and joints (joint presets as a dropdown), a wall's openings (kind, width, height, position, sill), a floor's beams and openings and a cabinet run's cabinets (width and style, including `gap` for appliances). Opened by double-click or **Edit**; changes are one undo step and are refused with the reason when the object cannot be built. **Joint** (`J`) on two parts that are already joined changes that joint. Shed and stair still use the Property view (they have no lists) |
| 3. Room / footprint object | Present | **Room** (`Room.py`, `RoomFeature`): walls measured on the inside (length and turn, square corners) entered in its panel or taken from a sketch (`Base`); doors and windows and appliance gaps (range, dishwasher, fridge, other) per wall; the walls for base and wall cabinets chosen in the panel. Generate makes and updates: wall framing per wall (outside the measured line; through-wall and corner stud at outside corners, shortened at inside corners) and cabinet runs backed onto the walls: a run turning a corner ends in a blind corner cabinet and the next starts past its depth; base runs stop at doors and appliance gaps, wall runs also at windows and fridges; leftover space becomes fillers. Generated objects stay ordinary (edit their panels); objects no longer needed are removed. Not modelled: walls at other angles, pipes and other obstacles except as an `other` gap |
| 4. Shed template opened up | Present | Doors and windows on any wall (`Openings`, edited as a list in the shed's panel; position from the wall's left end seen from outside; empty = the centred front door, `none` = no openings). **RoofType** gable or shed: mono-pitch rafters low at the front, the back wall framed the roof's rise taller, gable studs and trapezoid sheathing on the side walls; checks report the high wall as framed |
| 5. Direct manipulation | Partial | **Move Part** (`ConstructionDrag.py`): select a face of a build's part and drag it in that face's plane; it snaps against or flush with other parts' faces within 15 mm (`Build.snap`), else to a 5 mm grid; click places, Esc cancels; one undo step. Assumes an orthographic view (FreeCAD's default). Openings in walls and cabinets in runs are moved in their panels, not dragged yet |

## Exit criteria status

| Criterion | Status |
|---|---|
| (a) L-shaped kitchen from one panel | Met: `TestConstructionGui.TestRoomPanel.test_l_kitchen_from_one_panel` (3600 and 2400 mm walls, a window, a 600 mm range gap; blind corner; cut list); checked visually |
| (b) End Table 50 mm taller and Z-clips with two property changes | Met: `TestConstructionApp.test_parametric_template` |
| (c) Window added to a shed wall from a panel | Met: `TestConstructionGui.TestShedPanel.test_window_from_panel`; checked visually |
| (d) Build part dragged, snapping to a face | Met: `TestConstructionGui.TestDrag.test_drag_snaps_to_a_face` (drag API and the mouse path with synthetic events) |

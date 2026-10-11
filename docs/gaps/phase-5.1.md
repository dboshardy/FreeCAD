<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Phase 5.1 Gap Inventory — Woodworking Assemblies & Joinery

Audit of Phase 5.1 target scope (`docs/DESIGN.md`, Phase 5.1) against this
repository. Status: **Present**, **Partial**, **Missing**. Code in
`src/Mod/Construction/`. Overlap with BIM, the Assembly workbench and the
Woodworking add-on is reviewed in `docs/gaps/phase-5.md`.

| Scope item | Status | Notes |
|---|---|---|
| One part model | Present | `Parts.Part` (name, role, size, position, grain, operations) for cabinets, framing, sheathing, joinery and builds |
| Single assembly object | Present | **Build** (`BuildFeature`, `Build.py`): parts and joints are rows of two linked spreadsheets; one solid per part, cut by joinery; a clicked face selects its part (`part_at`). Named Build in the UI to avoid the Assembly workbench's "assembly" |
| Board, Board Between, Panel | Partial | Commands add table rows. Board and Panel start at the origin; the user types the position in the table. Board Between spans the gap between two selected parts, thickness centred, flush with the top. No drag placement or snapping yet |
| Joint command (`J`) | Partial | Offers the library presets that fit how the parts meet (`Joinery.meets`: end/edge/face to face, crossing); makes the part whose end goes in the inserted part; Apply to similar turns `Leg 1` / `Apron 1` into `Leg*` / `Apron*`. No live preview; options are typed in the joints table |
| Joint geometry | Partial | Mortise and tenon (cheeks and shoulders cut, mortise in the receiver), housing / dado / rabbet, half lap. Dowels, pocket screws, screws, confirmat, biscuits and tabletop fasteners are counted and listed as operations but their holes are not modelled. Loose tenon, bridle and edge-to-edge (glue-up) presets missing. Two tenons meeting inside a leg are reported by the checks |
| Joint and hardware libraries | Present | `generic/joints.json` (category `joint`, with `meets`), hardware items for the presets, `metric/furniture_stock.json` (planed hardwood, leg blanks, edge-glued panels). All with `source` and `data_license`; user overrides as for other libraries |
| Outputs | Present | Cut list with an Operations column (parts lengthened by tenons), hardware list from joints, lumber plan and sheet layout, drawing with tags (`write_cut_list`, `make_drawing`), IFC export as an element assembly |
| Checks (tenon walls, edge distances, wood movement) | Partial | `Checks.build`: mortise wall thickness (rule `mortise_wall_min_mm`), cuts meeting inside a part (e.g. two tenons in one leg), solid wood wider than `wood_movement_width_mm` fixed rigidly (joint presets mark `allows_movement`). Fastener edge distances not checked: fastener positions are not modelled |
| Templates | Partial | End Table (`Build.end_table`, `make_end_table`, command **End Table**): sizes, stock, joint and top fastening as arguments. No optional shelf. Bookcase, workbench, table not started. Cabinets and the shed still generate their own objects (their hardware rules stay in `CutList.hardware`) |
| Tutorials | Present | `docs/tutorials/construction/05-end-table.md`, examples run as doctests |

## Exit criteria status

| Criterion | Status |
|---|---|
| 500 × 500 × 600 mm end table by hand: 4 legs, 4 aprons, top; mortise and tenon applied once and repeated with Apply to similar; figure-8 top fasteners | Met in `TestConstructionApp.test_end_table_by_hand_matches_template` (the Joint command's selection, filtering and Apply to similar in `TestConstructionGui.test_joint_from_selection`) |
| Cut list shows tenon-lengthened aprons (410 = 360 + 2 × 25) and mortise operations; hardware list counts the fasteners (8) | Met, same test; hand counts in tutorial 5 |
| The template's table matches | Met: same parts, cut list and volume |

## Verification

- `python3 src/Mod/Construction/TestConstruction.py` (standalone, includes the
  tutorial doctests), `FreeCADCmd -t TestConstructionApp`, `FreeCAD -t
  TestConstructionGui`: all pass.
- The end table's 3D view and drawing were exported and inspected: legs,
  aprons and top in place; tags 1 (apron), 2 (leg), 3 (top) match the cut list.
- Not yet followed by hand: tutorial 5's GUI steps in an interactive session.

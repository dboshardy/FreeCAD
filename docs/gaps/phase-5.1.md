<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Phase 5.1 Gap Inventory — Woodworking Assemblies & Joinery

Audit of Phase 5.1 target scope (`docs/DESIGN.md`, Phase 5.1) against this
repository. Status: **Present**, **Partial**, **Missing**. Code in
`addons/construction/`. Overlap with BIM, the Assembly workbench and the
Woodworking add-on is reviewed in `docs/gaps/phase-5.md`.

| Scope item | Status | Notes |
|---|---|---|
| One part model | Present | `Parts.Part` (name, role, size, position, grain, operations) for cabinets, framing, sheathing, joinery and builds |
| Single assembly object | Present | **Build** (`BuildFeature`, `Build.py`): parts and joints are rows of two linked spreadsheets; one solid per part, cut by joinery; a clicked face selects its part (`part_at`). Named Build in the UI to avoid the Assembly workbench's "assembly" |
| Board, Board Between, Panel | Present | Commands add table rows. With one face of a part selected, Board lies on it along the part's length and Panel covers it (`Build.on_face`); Board Between spans the gap between two parts. **Align** moves a part so its selected face lies against (or flush with) another part's face. No free dragging in the 3D view: positions are table cells, and FreeCAD's own drag tools move whole objects, not parts inside one |
| Joint command (`J`) | Present | Offers the library presets that fit how the parts meet (`Joinery.meets`); makes the part whose end goes in the inserted part; asks for options with the preset's sizes filled in; adds the joint so it shows in the model, then asks Keep / Apply to every similar pair (`Leg*` / `Apron*`) / Undo; a joint that does not fit is undone with a message |
| Joint geometry | Present | Mortise and tenon (cheeks and shoulders cut, mortise in the receiver), loose tenon (mortises in both parts, tenons counted as hardware), housing / dado / rabbet, half lap. Bridle (slot and tenon cheeks). Dowel, screw, confirmat and shelf-pin holes are modelled as cylinders (preset `hole`: diameter, depth into each part) at the fastener positions; pocket holes (angled), biscuit slots and tabletop fastener recesses are listed as operations only: modelling them changes no count or size; add them when CAM output needs them. Edge-to-edge glue-ups use the glue preset. Two tenons meeting inside a leg are reported by the checks |
| Joint and hardware libraries | Present | `generic/joints.json` (category `joint`, with `meets`), hardware items for the presets, `metric/furniture_stock.json` (planed hardwood, leg blanks, edge-glued panels). All with `source` and `data_license`; user overrides as for other libraries |
| Outputs | Present | Cut list with an Operations column (parts lengthened by tenons), hardware list from joints, lumber plan and sheet layout, drawing with tags (`write_cut_list`, `make_drawing`), IFC export as an element assembly |
| Checks (tenon walls, edge distances, wood movement) | Present | `Checks.build`: wall anchoring required for builds taller than `anchor_furniture_height_mm` and slender (`anchor_furniture_slenderness`; anchors added to the hardware list), wood movement measured across whole edge-glued glue-ups, mortise wall thickness (rule `mortise_wall_min_mm`), cuts meeting inside a part (e.g. two tenons in one leg), solid wood wider than `wood_movement_width_mm` fixed rigidly (joint presets mark `allows_movement`). holes leaving less than `hole_wall_min_mm` to a face or breaking through (fastener edge distances) |
| Templates | Present | General table (`Build.table`: sizes, stock, joint, top fastening, panel or glued-up board top, optional shelf on stretchers) with End Table, Dining Table and Workbench commands. Bookcase (`Build.bookcase`, command **Bookcase**): fixed shelves, top and bottom in dados (or any joint), kick board on pocket screws, back nailed on with its grain up. Cabinets and runs keep their size properties but go through the same pipeline: `Cabinet.joint_rows()` names library joints (carcass joint, hinges on the hanging side, shelf pins, drawer slides) and `Cabinet.joined()` applies them, so hardware and shop operations come from joinery; `CutList.hardware` only adds wall anchors (a safety rule, not a joint). The shed's framing already counts its fasteners through joinery with the fastening schedule |
| Tutorials | Present | `addons/construction/Tutorials/05-end-table.md`, examples run as doctests |

## Exit criteria status

| Criterion | Status |
|---|---|
| 500 × 500 × 600 mm end table by hand: 4 legs, 4 aprons, top; mortise and tenon applied once and repeated with Apply to similar; figure-8 top fasteners | Met in `TestConstructionApp.test_end_table_by_hand_matches_template` (the Joint command's selection, filtering and Apply to similar in `TestConstructionGui.test_joint_from_selection`) |
| Cut list shows tenon-lengthened aprons (410 = 360 + 2 × 25) and mortise operations; hardware list counts the fasteners (8) | Met, same test; hand counts in tutorial 5 |
| The template's table matches | Met: same parts, cut list and volume |

## Verification

- `python3 addons/construction/TestConstruction.py` (standalone, includes the
  tutorial doctests), `FreeCADCmd -t TestConstructionApp`, `FreeCAD -t
  TestConstructionGui`: all pass.
- The end table's 3D view and drawing were exported and inspected: legs,
  aprons and top in place; tags 1 (apron), 2 (leg), 3 (top) match the cut list.
- Not yet followed by hand: tutorial 5's GUI steps in an interactive session.

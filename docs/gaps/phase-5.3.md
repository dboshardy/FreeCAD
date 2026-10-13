<!--
SPDX-License-Identifier: LGPL-2.1-or-later
-->

# Phase 5.3 Gap Inventory: Roll Back Overlap with FreeCAD

Status of each row of `docs/DESIGN.md` §5.3 (2026-10-13). Tests: `FreeCADCmd -t TestConstruction`
(135, no document) and `-t TestConstructionApp` (32, in the application) pass.

| # | FreeCAD object | Status | What changed, and what stayed |
|---|---|---|---|
| 1 | `Arch_Structure` on a BIM rectangle profile | Done | `MemberFeature` subclasses BIM's `_Structure`; the line is the extrusion path (`Tool`), roll is `BaseRotation`, end-cut lengthening is `ToolOffsetFirst/Last`. Kept: library lumber size, angled end cuts (`StartCut`, `EndCut`), cut-list row. `Member.py` keeps only the frame and end-extension maths: framing generators draw their pieces as solids of one compound and need it. `Arch_Frame` (members along every edge of a wire) is not used yet. |
| 2 | `Arch_Stairs` | Done | The Stair object links an `Arch_Stairs` (shape, rise, steps, tread depth, width, nosing, landing, railings). `Framing.Stair` reads those values (`n_risers`, `tread_run`) and still produces treads from whole boards, cut stringers, newel posts, balusters, checks and cut-list parts. Limits: only straight flights with no landing or a landing `At center`; the last tread board is ripped when whole boards overshoot the run (not tracked); the Arch_Stairs is hidden, the Stair object shows a copy of its shape. |
| 3 | `BIM_Slab` (`Arch_Structure`, type Slab) | Done | `SlabFeature` and the garage's foundation own a BIM slab bound by expressions to their length, width, thickness and placement. Concrete is the shape volume of the slab plus the thickened edge. Kept: edge, concrete line in the cut list, foundation check. A shed switched to `Foundation = slab` gets its BIM slab on the change. |
| 4 | `Arch_Panel_Sheet` | Done | One panel sheet per sheet in group `SheetLayoutView`, holding the placed parts (tag = part name). The guillotine packer `CutList.layout_sheets` stays. `Arch_Nest` (true shape) is not wired in. |
| 5 | `Arch_Fence` | Done | One fence per guard side (four, a freestanding deck uses all) on a path, post and one-bay section computed from `Framing.Deck`. Guard parts, checks and hardware still come from the model, so quantities are unchanged (`TestConstruction.test_guards`). Stair guards are `Arch_Stairs` railings. The fence cannot clear its own shape when a side loses its guard, so the deck clears it. |
| 6 | `BIM_IfcQuantities` / shape volume | Done with 3 | The only BIM-backed concrete is the slab, now from its shape. `BIM_IfcQuantities` (a command that writes quantity properties) is not used. |
| 7 | Material workbench cards | Done | Items carry `material_card` (UUID) instead of `density_kg_m3`; 13 cards in `Resources/Materials/` are registered as the Material library "Construction" by `Init.py`. Only density existed (no appearance data); `Library.density_kg_m3(item)` reads it. |
| 8 | `Help.show` | Done, not seen in the GUI | `show_tutorials` uses `Help.show` when `Help.get_qtwebwidgets()` is true, else the text browser. Not run in an interactive session. |

## Exit criteria

| Criterion | Status |
|---|---|
| Each rolled-back object is created from the FreeCAD object | Met (tests above) |
| Shed and garage templates, cut list, hardware list, checks and tutorials give the same quantities as before | Met by the existing suites (every quantity test passes unchanged; the tutorial examples are doctests) |
| IFC export writes FreeCAD's BIM types | Partial: `TestConstructionApp.test_ifc_export` passes; the new objects are BIM objects, but no test checks each type's IFC class |
| Removed code is gone from the Construction workbench | Met for the rows above, except the generator-level maths kept as noted in rows 1 and 2 |

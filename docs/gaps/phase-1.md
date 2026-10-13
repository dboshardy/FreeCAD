<!--
SPDX-License-Identifier: LGPL-2.1-or-later
-->

# Phase 1 Gap Inventory: 2D Sketcher and Constraint Solver

Audit of the Phase 1 target scope (`docs/DESIGN.md` §5.1) against the source tree (2026-10-13,
`src/Mod/Sketcher`, PlaneGCS in `App/planegcs`). Status: **Present**, **Partial**, **Missing**.
Delivery: **add-on** (`addons/sketch/`, default) or **FreeCAD change** with the reason an add-on cannot do it (§4.2).

## Target scope

| # | Item | Status | Upstream | Delivery |
|---|---|---|---|---|
| 1.1 | Circle tangent to existing curves | Missing | Circle tools: centre, 3 rim points; auto-constraints add coincident or point-on-object, not tangency to chosen curves | Add-on: `Sketch_TangentCircle` (`SketchTools.tangent_circle`): 1 to 3 lines, circles or arcs. The curves are blocked while the solver places the circle (else it drags them), then released; first guesses are varied until the solver converges |
| 1.2 | Stretch | Missing | Move, Translate, Rotate, Scale act on whole selections | Add-on: `Sketch_Stretch` (`SketchTools.stretch`): moves chosen points by a vector and lets constraints drag what is attached; targets are computed first so a point dragged along by a constraint is not moved twice |
| 1.3 | Collinear as one constraint | Present | `Sketcher_ConstrainTangent` on two lines is collinear (command text "Tangent/Collinear Constraint"); checked: two free lines end up on one line | None; hotkey layer only |
| 1.4 | Curvature-continuous (G2) constraint | Missing | No such `ConstraintType` (`App/Constraint.h`) and no PlaneGCS constraint | **FreeCAD change** (solver): a new constraint type needs PlaneGCS error and gradient code and the Sketcher GUI. An add-on cannot add a constraint to the solver. Not done; upstream contribution to design |
| 1.5 | Pierce | Present | `Sketcher_Intersection` ("External Intersection": intersection of external geometry with the sketch plane) | None |
| 1.6 | Inference indicators (endpoint, midpoint, centre, intersection, tangent, alignment, extension) with a toggle per type | Partial | `DrawSketchHandler::seekAutoConstraint` suggests coincident, point on object, horizontal and vertical, tangent, and endpoint alignment (`seekAlignmentAutoConstraint`); no midpoint, centre, intersection or extension indicators, and one on/off switch for all | **FreeCAD change**: the draw tools are C++ handlers with no Python hook for snapping or overlays. Not done; would extend `seekAutoConstraint` with per-type preferences |
| 1.7 | Conflict diagnosis that suggests the constraint to remove | Partial | The sketch message lists the conflicting constraints ("Remove at least one of the following constraints") | Add-on: `Sketch_Diagnose` (`SketchTools.diagnose`): tries each suspect's removal on a throw-away copy, lists those that alone make the sketch solve, last added first, and selects the first in the view |
| 1.8 | Profile detection (closed regions, nested loops) with region highlight | Missing | PartDesign features build faces from sketches but nothing shows the regions | Add-on: `Sketch_Regions` (`SketchTools.regions`, `show_regions`): faces with holes per nesting level, coloured group; crossing or touching loops are refused |

Everything in the Upstream baseline paragraph (entities, editing, constraints, auto-constraints, on-view parameters, DXF) is
Present upstream; the add-on adds no hotkeys for it (the UX add-on's opt-in profile covers the Sketcher keys).

## Exit criteria

Tested in `addons/sketch/TestSketch.py` (`TestExitCriteria`) on the CADApp build and on stock FreeCAD 26.3:

| Criterion | Result |
|---|---|
| Fully constrain a 100-entity sketch | Met: 25 rectangles (100 lines, 300 constraints), `FullyConstrained` |
| Solver resolves in < 50 ms | Met: 17 to 19 ms per `solve()` (Linux arm64, container) |
| Dimension edits propagate | Met: changing one width moves the opposite side |
| Conflict dialog identifies the offending constraint | Met for single-constraint conflicts: the added contradicting dimension is named first. A conflict that needs several removals is reported without a suggestion |

## Not done

G2 constraint (1.4) and per-type inference indicators (1.6) need FreeCAD changes (solver; draw handlers); the design says such
changes go upstream as minimal PRs, which this repository does not submit. No solver fuzz tests (§10) were written.

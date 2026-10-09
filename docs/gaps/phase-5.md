<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Phase 5 Gap Inventory — Construction & Woodworking

Audit of Phase 5 target scope (`docs/DESIGN.md` §5) against this repository.
Status: **Present**, **Partial**, **Missing**. Fork code lives in `src/Mod/Construction/`
(build option `BUILD_CONSTRUCTION`, default on).

## Ordering exception

§5 says a phase starts only after the previous phase's exit criteria pass. Phase 5
was started (2026-10-08, owner's request) while Phases 0–4 are open, because it
does not depend on fork code from those phases:

| Phase 5 needs | Provided by | Fork phase it would otherwise wait for |
|---|---|---|
| Solids, placement, booleans | Upstream Part | 2 (UX alignment only) |
| Drawings of framing / shop drawings | Upstream TechDraw, BIM `BimTDView` | 3 |
| Build-sequence exploded views | Upstream Assembly exploded views | 4 |
| True-shape sheet nesting | Upstream `src/Mod/BIM/ArchNesting.py` | 11 (shared engine) |
| Span / deflection checks | Closed-form beam formulas (no FEA) | 10 (1D solver) |

Hotkey context layers (§13 rule 7) are not shipped as defaults; the Construction
workspace layer can be bound in `Hotkeys.json` (Phase 0 decision 0.6.10).

## 5.1 Material library

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.1.1 | Data-driven library, `source` + `data_license` per item (§9) | Partial | `Construction/Library.py`, `Resources/libraries/{US,metric}/*.json`; CI `check.py data`. User overrides in `<user data>/Construction/libraries/` |
| 5.1.2 | Dimensional lumber (US nominal / metric) | Partial | Upstream `BIM/Presets/profiles.csv` has "North America Lumber" profiles; no fork library entries or stock lengths yet |
| 5.1.3 | Engineered lumber (LVL, glulam, I-joist) | Missing | |
| 5.1.4 | Sheet goods (plywood, OSB, MDF, particleboard, HDF; US 4×8, metric) | Partial | Fork library: US 5 items, metric 6 items. No drywall / cement board yet |
| 5.1.5 | Hardwood stock, board-foot calc | Missing | |
| 5.1.6 | Steel shapes | Partial | Upstream `profiles.csv` (W, RHS, …) |
| 5.1.7 | Masonry, concrete, rebar | Partial | Upstream BIM rebar, structure; no fork library |
| 5.1.8 | Area materials (roofing, siding, insulation) | Missing | |
| 5.1.9 | Hardware (hinges, slides, shelf pins, connectors) | Missing | |
| 5.1.10 | Cost / SKU per item | Missing | Schema fields only (§9) |
| 5.1.11 | Region switch per document | Missing | All regions listed together in material choices |
| 5.1.12 | Library editor UI, CSV import/export | Missing | |

## 5.2 Structural members

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.2.1 | Member: profile along a path, material, grain, end cuts | Partial | Upstream `ArchStructure` (profile along path), `ArchFrame`; no end cuts (miter, birdsmouth, …), no grain |
| 5.2.2 | Sheet object: panel with thickness, edge banding, grain | Partial | Upstream `ArchPanel`; no edge banding / grain |

## 5.3 Joinery

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.3.1 | Joint types (butt … scarf) | Partial | Cabinet carcass uses butt joints implicitly; no joint objects |
| 5.3.2 | Fastener placement rules, hardware BOM | Missing | |

## 5.4 Generators

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.4.1 | Wall framing | Missing | Upstream `ArchWall` is a solid wall, not framing |
| 5.4.2 | Floor framing | Missing | |
| 5.4.3 | Roof framing, truss layout | Partial | Upstream `ArchRoof` (solid), `ArchTruss` (truss object) |
| 5.4.4 | Stairs | Partial | Upstream `ArchStairs` (straight, landing, curved); no rule checks |
| 5.4.5 | Decks | Missing | |
| 5.4.6 | Foundations | Partial | Upstream `ArchStructure` slabs/footings; no concrete-volume report |
| 5.4.7 | Sheathing / cladding layers | Partial | Upstream `ArchCovering`; no seam layout |
| 5.4.8 | Cabinets | Partial | `Construction_BaseCabinet`: frameless base cabinet on a plinth, butt-jointed carcass, adjustable shelves, full-overlay slab doors, all sizes as properties (`Construction/Cabinet.py`, `ConstructionObjects.py`). Missing: wall/tall/drawer/corner cabinets, face-frame, dado/rabbet/confirmat options, shaker doors, drawers, runs along a wall, toe-kick notch option |
| 5.4.9 | Furniture primitives | Missing | |
| 5.4.10 | Building elements (walls, doors, windows, levels, rooms) | Present | Upstream BIM |
| 5.4.11 | Templates (shed, garage, kitchen run, bookcase, workbench) | Missing | |

## 5.5 Analysis (advisory)

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.5.1 | Beam span / deflection (simple, cantilever, continuous) | Missing | |
| 5.5.2 | Rise/run, headroom, guardrail rule sets | Missing | |

## 5.6 Outputs

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.6.1 | BOM / purchase list by material and stock length, cost | Partial | `Construction_CutList`: sheets per material (area estimate, 15% waste). No stock lengths or cost |
| 5.6.2 | Cut list (dimensions, grain, labels) | Partial | `Construction_CutList` writes spreadsheet `CutList`: material, part, length (along grain), width, thickness, grain, qty. Missing: angles, edge banding, part labels |
| 5.6.3 | 1D stock optimization (kerf, waste/cost) | Missing | §3.2 lists OR-Tools; start with a stdlib heuristic |
| 5.6.4 | 2D sheet nesting (guillotine; true-shape) | Partial | True-shape: upstream `ArchNesting.py` + `ArchPanel` sheets. Guillotine for panel saws: Missing |
| 5.6.5 | Framing plans / elevations with member tags | Partial | Upstream TechDraw/BIM views; no member tags |
| 5.6.6 | Build-sequence views | Missing | |
| 5.6.7 | Export CSV/XLSX, PDF shop drawings, labels | Partial | Spreadsheet CSV export (upstream); no labels |

## Exit criteria status

| Criterion | Status |
|---|---|
| Gable shed from template; edit wall height and door width; framing regenerates | Not met (5.4.1, 5.4.3, 5.4.11) |
| BOM, optimized cut list, sheet nesting, framing drawings match hand count | Not met (5.6.1–5.6.5) |

## Verification

`python3 src/Mod/Construction/TestConstruction.py` (no FreeCAD needed) tests cabinet
geometry (outer size, no overlapping parts, door widths, shelves, invalid sizes),
cut-list grouping, sheet estimate, and the library. The FreeCAD object and
commands (`ConstructionObjects.py`, `ConstructionCommands.py`, `InitGui.py`) have
not been run in the app yet (no local build environment).

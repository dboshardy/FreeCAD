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
| 5.1.2 | Dimensional lumber (US nominal / metric) | Partial | Fork library: US 1x4–4x6 with PS 20 dressed sizes and stock lengths incl. precut studs (92-5/8", 104-5/8"); metric 38/45 mm sections, 70x70, 95x95, stock 2.4–6.0 m. No species grades or design values (user-supplied, §9) |
| 5.1.3 | Engineered lumber (LVL, glulam, I-joist) | Missing | |
| 5.1.4 | Sheet goods (plywood, OSB, MDF, particleboard, HDF; US 4×8, metric) | Partial | Fork library: US 5 items, metric 6 items. No drywall / cement board yet |
| 5.1.5 | Hardwood stock, board-foot calc | Missing | |
| 5.1.6 | Steel shapes | Partial | Upstream `profiles.csv` (W, RHS, …) |
| 5.1.7 | Masonry, concrete, rebar | Partial | Upstream BIM rebar, structure; no fork library |
| 5.1.8 | Area materials (roofing, siding, insulation) | Missing | |
| 5.1.9 | Hardware (hinges, slides, shelf pins, connectors) | Partial | `Resources/libraries/generic/hardware.json`: concealed hinge (count by door height), drawer slide pair, shelf pin; override by id in the user library. No connectors, joist hangers, anchors, fasteners |
| 5.1.10 | Cost / SKU per item | Missing | Schema fields only (§9) |
| 5.1.11 | Region switch per document | Missing | All regions listed together in material choices |
| 5.1.12 | Library editor UI, CSV import/export | Missing | |

## 5.2 Structural members

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.2.1 | Member: profile along a path, material, grain, end cuts | Partial | `Construction_Member` (`Member.py`, `MemberFeature`): lumber section along a linked straight edge (follows sketch edits) or Start/End points; Roll about its axis; grain along the length. Square end cuts only: no miter, bevel, birdsmouth, notches, holes |
| 5.2.2 | Sheet object: panel with thickness, edge banding, grain | Partial | Upstream `ArchPanel`; no edge banding / grain |

## 5.3 Joinery

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.3.1 | Joint types (butt … scarf) | Partial | Cabinet carcass uses butt joints implicitly; no joint objects |
| 5.3.2 | Fastener placement rules, hardware BOM | Partial | Cut list "Hardware" section: hinges per door by height, slide pairs per drawer by length, 4 shelf pins per shelf (`CutList.hardware`). No fastener placement or screw counts |

## 5.4 Generators

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.4.1 | Wall framing | Partial | `Construction_WallFrame` (`Framing.py`, `WallFrameFeature`): bottom plate (cut at doors), 1 or 2 top plates, studs on centres from the wall start, door and window rough openings with king and jack studs, header plies on edge, cripples above headers and below sills, rough sill. Plates longer than the stud lumber's longest stock are spliced over stud centres, upper top plate joints at least one bay from the lower. Openings typed as text. Missing: corners (3-stud, California), T-intersections, blocking rows, header sizing (header size is chosen by the user), following a sketch line |
| 5.4.2 | Floor framing | Missing | |
| 5.4.3 | Roof framing, truss layout | Partial | Upstream `ArchRoof` (solid), `ArchTruss` (truss object) |
| 5.4.4 | Stairs | Partial | Upstream `ArchStairs` (straight, landing, curved); no rule checks |
| 5.4.5 | Decks | Missing | |
| 5.4.6 | Foundations | Partial | Upstream `ArchStructure` slabs/footings; no concrete-volume report |
| 5.4.7 | Sheathing / cladding layers | Partial | Upstream `ArchCovering`; no seam layout |
| 5.4.8 | Cabinets | Partial | `Construction/Cabinet.py`, `ConstructionObjects.py`. Frameless base / wall / tall / sink cabinets (base: top stretchers + plinth; wall / tall: full top; wall cabinets created at 1400 mm; sink: front stretcher only, no back, false front over doors) and blind-corner cabinets (any kind; blind panel left or right, doors on the open width). Butt-jointed carcass, adjustable shelves, full-overlay fronts: doors, drawer bank, drawer over doors, false front over doors. Drawer boxes sized from slide clearances (side, height, rear), depth rounded down to 50 mm slide lengths. Runs along a wall (`Construction_BaseRun`, `Construction_WallRun`): given widths, or widths chosen from a standard list to leave the least filler, fillers left / right / both; per-cabinet styles in Widths (`1000 blind_left, 600 drawers, 800 sink, 600`), a blind corner at a run end keeps the filler off the corner side. Missing: diagonal and L-shaped corner cabinets, corner fillers between meeting runs, face-frame, dado/rabbet/confirmat options, shaker doors, drawer slides and hinges in the BOM, toe-kick notch option, per-cabinet sizes other than width inside a run |
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
| 5.6.1 | BOM / purchase list by material and stock length, cost | Partial | `Construction_CutList`: sheets per material from the panel-saw layout (% used); lumber boards per stock length from the cutting plan. No cost |
| 5.6.2 | Cut list (dimensions, grain, labels) | Partial | `Construction_CutList` writes spreadsheet `CutList`: material, part, length (along grain), width, thickness, grain, qty. Missing: angles, edge banding, part labels |
| 5.6.3 | 1D stock optimization (kerf, waste/cost) | Partial | `CutList.plan_lengths`: first-fit decreasing, each board shrunk to the shortest stock length that holds its cuts; kerf between pieces; spreadsheet `LumberPlan` (cuts and offcut per board). Heuristic; exact optimization (OR-Tools, §3.2) not added. No cost weighting |
| 5.6.4 | 2D sheet nesting (guillotine; true-shape) | Partial | Guillotine for panel saws: `CutList.layout_sheets` (kerf and trim from preferences `Mod/Construction/Kerf`, `/Trim`; grain parts stay along the sheet length; sheets without grain, e.g. MDF, allow rotation). Writes spreadsheet `SheetLayout` (part positions) and `SheetLayoutView` (flat drawing of the sheets). Multi-pass greedy, not optimal; prior art in `docs/prior-art/guillotine-sheet-layout.md`. True-shape: upstream `ArchNesting.py` |
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
geometry (outer size, no overlapping parts for every kind / front style, front and door coverage, drawer box sizes, invalid sizes), run layout and fillers,
cut-list grouping, sheet estimate, and the library. The FreeCAD object and
commands (`ConstructionObjects.py`, `ConstructionCommands.py`, `InitGui.py`) have
not been run in the app yet (no local build environment).

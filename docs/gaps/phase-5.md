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

## Standards and safety policy

Generators follow conventional practice, and `Construction_Check` reports
advisory checks. Nothing here certifies building-code compliance:

- Building codes and span tables (IRC/IBC, NDS, national codes) are copyrighted
  and differ by jurisdiction (§2, §12 R14), so none are embedded. The shipped
  rule set `rules.generic-example` holds example values from conventional
  practice and mechanics, labelled "verify for your jurisdiction". Users add
  their adopted values as their own rule set.
- Structural checks use beam mechanics with design values and loads the user
  supplies; without them the result is "not checked", never "ok".
- Every check output starts with the disclaimer in `Checks.DISCLAIMER`
  (verify with the local code; review by the building official or a
  qualified professional).
- Safety items are generated, not left to the user: wall and tall cabinets
  get wall anchors in the hardware list and a "required" check line.

## 5.1 Material library

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.1.1 | Data-driven library, `source` + `data_license` per item (§9) | Partial | `Construction/Library.py`, `Resources/libraries/{US,metric}/*.json`; CI `check.py data`. User overrides in `<user data>/Construction/libraries/` |
| 5.1.2 | Dimensional lumber (US nominal / metric) | Partial | Fork library: US 1x4–4x6 with PS 20 dressed sizes and stock lengths incl. precut studs (92-5/8", 104-5/8"); metric 38/45 mm sections, 70x70, 95x95, stock 2.4–6.0 m. No species grades or design values (user-supplied, §9) |
| 5.1.3 | Engineered lumber (LVL, glulam, I-joist) | Present | `metric/` and `US/engineered_lumber.json`: common LVL, glulam and I-joist sizes (I-joists as flange × depth rectangles), selectable wherever lumber is; design values from the maker go in the user library |
| 5.1.4 | Sheet goods (plywood, OSB, MDF, particleboard, HDF; US 4×8, metric) | Present | US plywood, OSB, MDF, drywall, cement board; metric plywood, MDF, OSB, edge-glued panels, gypsum and cement board. Particleboard / HDF: add by user library |
| 5.1.5 | Hardwood stock, board-foot calc | Present | `metric/furniture_stock.json` (planed hardwood, leg blanks, edge-glued panels); `CutList.board_feet` (nominal size when given) and `volume_m3`; the cut list gives m³ and board feet bought per lumber material |
| 5.1.6 | Steel shapes | Partial | Upstream `profiles.csv` (W, RHS, …) |
| 5.1.7 | Masonry, concrete, rebar | Partial | Upstream BIM rebar, structure; no fork library |
| 5.1.8 | Area materials (roofing, siding, insulation) | Partial | `generic/area_materials.json` (shingles, felt and synthetic underlayment, house wrap; coverage per unit and waste); **Covering** on Sheathing, **RoofCovering** / **WallCovering** on the shed; cut list Coverings section. No siding courses or insulation items shipped (add by user library) |
| 5.1.9 | Hardware (hinges, slides, shelf pins, connectors) | Partial | `Resources/libraries/generic/hardware.json`: concealed hinge, drawer slide pair, shelf pin, framing nail, joist hanger, deck screw, wall anchor, dowel, pocket screw, wood and confirmat screws, biscuit, tabletop fasteners; override by id in the user library. Counted through joint presets (`generic/joints.json`: hinges by door height, slides by depth, pins per shelf end) |
| 5.1.10 | Cost / SKU per item | Present | Optional `price` / `price_per` (each, m, board foot, m³) per item, `sku` free field; cut list Cost column and Total cost (counts unpriced lines). No prices shipped (they vary by supplier) |
| 5.1.11 | Region switch per document | Present | **Library Region** command stores the region in the document (`Meta`); library choices narrow to it plus generic items; preference `Region` for new documents |
| 5.1.12 | Library editor UI, CSV import/export | Missing | |

## 5.2 Structural members

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.2.1 | Member: profile along a path, material, grain, end cuts | Partial | `Construction_Member` (`Member.py`, `MemberFeature`): lumber section along a linked straight edge (follows sketch edits) or Start/End points; Roll about its axis; grain along the length. Square end cuts only: no miter, bevel, birdsmouth, notches, holes |
| 5.2.2 | Sheet object: panel with thickness, edge banding, grain | Partial | Upstream `ArchPanel`; no edge banding / grain |

## 5.3 Joinery

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.3.1 | Joint types (butt … scarf) | Partial | `Joinery.py` for every construction object: contact detection between axis-aligned parts, housings (dado, groove, rabbet, housed end), half laps, fastened joints, matched by part-name rules. Used by framing so far. Missing: mortise and tenon, dovetail, box joint, miter, scarf; cabinets not yet on joinery; joints between separate objects |
| 5.3.2 | Fastener placement rules, hardware BOM | Partial | Fastening schedules as library data (`fastening.generic-example`, preference `Mod/Construction/FasteningSchedule`): walls (studs, plates, kings, jacks, headers, cripples, sills), floors (rims), decks (joist hangers at the ledger, rim nails, beam nails, deck screws) counted into the cut list's Hardware. Rafters, stairs and joints between objects not counted |

## 5.4 Generators

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.4.1 | Wall framing | Partial | `Construction_WallFrame` (`Framing.py`, `WallFrameFeature`): bottom plate (cut at doors), 1 or 2 top plates, studs on centres from the wall start, door and window rough openings with king and jack studs, header plies on edge, cripples above headers and below sills, rough sill. Plates longer than the stud lumber's longest stock are spliced over stud centres, upper top plate joints at least one bay from the lower. Openings typed as text. Corner studs where another wall butts (`CornerStart` / `CornerEnd`; the shed uses them). Missing: California corners, T-intersections, blocking rows, header sizing (header size is chosen by the user), following a sketch line |
| 5.4.2 | Floor framing | Present | `Construction_FloorFrame` (`Framing.Floor`): rim joists (spliced over joists to fit stock) and joists on centres; dropped beams (`Beams`, plies) with joists butt-joined over them, on posts (`PostHeight`) with footings counted as concrete; rows of blocking per span; openings (`Openings`, e.g. stairwells) framed with doubled trimmers, doubled headers and tail joists, cut out of the subfloor. Checks: joists over their longest span, each beam between posts. Missing: lapped joists over beams, cantilevered floors |
| 5.4.3 | Roof framing, truss layout | Partial | `Construction_GableRoof` (`Framing.GableRoof`): common rafters with plumb ridge and tail cuts and birdsmouth seats, ridge board (spliced over rafter pairs), ceiling joists as rafter ties with ends cut to the slope (default on), gable studs over the end walls (tops cut to the roof, stopped under the ridge; end ceiling joists moved inside). Mono-pitch roofs: `Construction_ShedRoof` (`Framing.ShedRoof`): rafters birdsmouthed on a low and a high wall, plumb tails, the high wall's extra height reported (`HighWallRise`), sheathing on the slope, checks (rafters, birdsmouth). Missing: hip, shed, gambrel, rake overhangs, collar ties, fascia, trusses (upstream `ArchTruss` remains) |
| 5.4.4 | Stairs | Partial | `Construction_Stair` (`Framing.Stair`): straight stair, fewest equal risers within the rule set's `stair_riser_max_mm`, treads from whole boards (run = boards + gaps − nosing), cut stringers dropped by the tread thickness, stringer count from a maximum spacing; guards on open sides (newel posts, handrail at the set height above the nosings, balusters the same on every tread so they come in few lengths, clear gaps within the set maximum), or a wall handrail. Checked by exporting a drawing and inspecting it. Upstream `ArchStairs` (landings, curved) remains. Missing: landings, winders, open risers, rail returns and brackets |
| 5.4.5 | Decks | Partial | `Construction_Deck` (`Framing.Deck`): attached (ledger) or freestanding (two beams), joists on centres, rims, dropped multi-ply beams with cantilever, posts within a maximum spacing, blocking rows, decking boards (joints over joists, staggered); footings counted as concrete (`FootingSize`, `FootingDepth`); checks for joists and beams (mechanics), ledger attachment, footings and guards required. Stairs to grade: add a **Stair** object. Missing: generated guards on the deck, multi-level decks |
| 5.4.6 | Foundations | Partial | Upstream `ArchStructure` slabs/footings. Post footings of decks and floors counted as concrete in the cut list (Concrete section). No slab or strip footing generator |
| 5.4.7 | Sheathing / cladding layers | Partial | `Construction_Sheathing` (`Sheathing.py`): sheet goods on floor (long side across joists), wall (upright, openings cut out) and both roof slopes, seams staggered when a row needs more than one sheet; laid out on sheets with no edge trim (factory edges), whole sheets counted as whole. Missing: seam-over-framing alignment, siding, roofing, membranes |
| 5.4.8 | Cabinets | Partial | `Construction/Cabinet.py`, `ConstructionObjects.py`. Frameless base / wall / tall / sink cabinets (base: top stretchers + plinth; wall / tall: full top; wall cabinets created at 1400 mm; sink: front stretcher only, no back, false front over doors) and blind-corner cabinets (any kind; blind panel left or right, doors on the open width). Carcass joint chosen from the joint library (**CarcassJoint**: confirmat by default, dowels, pocket screws, biscuits, dado, ...), adjustable shelves, full-overlay fronts: doors, drawer bank, drawer over doors, false front over doors. Drawer boxes sized from slide clearances (side, height, rear), depth rounded down to 50 mm slide lengths. Runs along a wall (`Construction_BaseRun`, `Construction_WallRun`): given widths, or widths chosen from a standard list to leave the least filler, fillers left / right / both; per-cabinet styles in Widths (`1000 blind_left, 600 drawers, 800 sink, 600`), a blind corner at a run end keeps the filler off the corner side. Missing: diagonal and L-shaped corner cabinets, corner fillers between meeting runs, face-frame, back fastening, shaker doors, toe-kick notch option, per-cabinet sizes other than width inside a run |
| 5.4.9 | Furniture primitives | Present | Phase 5.1 builds: Board, Board Between, Panel, joints from the library (`docs/gaps/phase-5.1.md`) |
| 5.4.10 | Building elements (walls, doors, windows, levels, rooms) | Present | Upstream BIM |
| 5.4.11 | Templates (shed, garage, kitchen run, bookcase, workbench) | Partial | `Construction_Shed` (`Shed.py`, `ShedFeature`): gable shed from one object — floor platform, front wall with a centred door, back and side walls, gable roof with ceiling joists, sheathing on floor, walls (side sheathing wraps the corners), gable ends (panels clipped to the gable outline) and roof; every size, spacing, lumber and sheet is a property and everything regenerates. Missing: garage / kitchen / bookcase / workbench templates |

## 5.5 Analysis (advisory)

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.5.1 | Beam span / deflection (simple, cantilever, continuous) | Partial | `Checks.beam` (simply supported): headers (`HeaderLoad` kN/m), floor joists rim to rim (`FloorLoad` kPa, span/360), rafters on plan (`RoofLoad` kPa, span/240); plus birdsmouth depth, ridge depth vs. plumb cut, rafter ties. All need user design values (Fb, E) and loads, otherwise "not checked". No cantilever / continuous |
| 5.5.2 | Rise/run, headroom, guardrail rule sets | Partial | Rule set framework (`Checks.py`, library category `rule_set`, preference `Mod/Construction/RuleSet`); shipped `rules.generic-example` covers stud spacing, stud slenderness (l/d), header deflection limit, cabinets needing wall anchors. Stairs: riser max, tread min, comfort rule 2R + T (Blondel), equal risers, stringer throat, handrail and guards "required" by rise / riser count; headroom not checked |

## 5.6 Outputs

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.6.1 | BOM / purchase list by material and stock length, cost | Partial | `Construction_CutList`: sheets per material from the panel-saw layout (% used); lumber boards per stock length from the cutting plan. No cost |
| 5.6.2 | Cut list (dimensions, grain, labels) | Partial | `Construction_CutList` writes spreadsheet `CutList`: material, part, length (along grain), width, thickness, grain, qty. Missing: angles, edge banding, part labels |
| 5.6.3 | 1D stock optimization (kerf, waste/cost) | Partial | `CutList.plan_lengths`: first-fit decreasing, each board shrunk to the shortest stock length that holds its cuts; kerf between pieces; spreadsheet `LumberPlan` (cuts and offcut per board). Heuristic; exact optimization (OR-Tools, §3.2) not added. No cost weighting |
| 5.6.4 | 2D sheet nesting (guillotine; true-shape) | Partial | Guillotine for panel saws: `CutList.layout_sheets` (kerf and trim from preferences `Mod/Construction/Kerf`, `/Trim`; grain parts stay along the sheet length; sheets without grain, e.g. MDF, allow rotation). Writes spreadsheet `SheetLayout` (part positions) and `SheetLayoutView` (flat drawing of the sheets). Multi-pass greedy, not optimal; prior art in `docs/prior-art/guillotine-sheet-layout.md`. True-shape: upstream `ArchNesting.py` |
| 5.6.5 | Framing plans / elevations with member tags | Partial | `Construction_Drawing` (`make_drawing`): A3 page with a projection group (front, top, right, automatic scale) of the selected construction objects and member tags: one balloon per cut-list row of framing members on the front view, at the instance nearest the viewer, numbered like the cut list's Tag column, bubbles in a column beside the view; a second A3 page with the cut list table. Title block filled in. Checked by exporting the shed's page to SVG and inspecting it. Shed `ShowSheathing` hides sheathing for framing drawings. Missing: section views, dimensions, tags on the top and side views |
| 5.6.6 | Build-sequence views | Missing | |
| 5.6.7 | Export CSV/XLSX, PDF shop drawings, labels | Partial | Spreadsheet CSV export (upstream); no labels |

## 5.7 Tutorials

| # | Item | Status | Where / notes |
|---|---|---|---|
| 5.7.1 | Tutorials with examples for each feature | Present | `docs/tutorials/construction/`: 1 cabinets and runs, 2 framing (members, walls, floors, roofs, sheathing, lumber plan), 3 shed end to end, 4 libraries, settings and checks |
| 5.7.2 | Examples kept true | Present | Every `pycon` block runs under doctest in `TestConstruction.TestTutorials`. GUI steps are written from the code and not yet followed in a running app |
| 5.7.3 | Shown in the in-app help | Partial | Installed with the workbench (`Mod/Construction/Tutorials`); **Construction > Tutorials** opens the index through upstream `Help.show` (rendering follows the Help preferences). Not yet tried in a running app |

## Upstream and add-on overlap (reviewed 2026-10-10)

What FreeCAD already provides, and what Construction does with it:

| Existing tool | Provides | Construction |
|---|---|---|
| BIM workbench | Walls, Structure members with profiles (`Presets/profiles.csv`), Stairs, Roof, Truss, Frame, Panel / PanelCut / PanelSheet, `ArchNesting`, Schedule, IFC export | No stud layout, joinery or cut-length optimisation there, so the generators stay. Construction objects carry an `IfcType` (wall, slab, roof, stair, member, covering, furnishing element, element assembly), so BIM's IFC export writes them as typed elements (`TestConstructionApp.test_ifc_export`). Sheathing links its framing as `Host`, not `Base`, so the export keeps both. |
| Assembly workbench | Kinematic joints (fixed, revolute, ...) between parts | Different meaning of "joint". Phase 5.1's woodworking object must not be called "Assembly" in the UI. |
| TechDraw, Spreadsheet | Drawings, tables | Used directly. |
| Woodworking add-on (MIT, dprojects/Woodworking, not in this tree) | Cabinet start-up dialog, dowels and screws placed by hand, drilling (holes, countersinks, counterbores, pocket holes), mortise and tenon from a sketch pattern, cut list and BOM export (and export for cutlistoptimizer.com), edge banding | Reviewed, not incorporated. It is a 67k-line GUI tool: every operation turns the selected `Part::Box` into a PartDesign Body and adds pockets chosen by hand, with the logic inside Qt dialogs. There is no data model of joints, no contact detection, no rule or hardware libraries and no sheet layout. That conflicts with the single assembly object of Phase 5.1, so no code is taken. Ideas used: the hardware presets it offers (dowels 8 x 35, wood screws, confirmat screws 7 x 40/50/70) become library entries, and pocket-hole parameters (angle, penetration) become joint presets. Users can still install the add-on from the Addon Manager alongside the workbench. |

## Exit criteria status

| Criterion | Status |
|---|---|
| Gable shed from template; edit wall height and door width; framing regenerates | Met: `TestShed.test_editing_regenerates` (geometry) and, in the app, `TestConstructionApp.test_edit_regenerates` (the Shed object rebuilds) |
| BOM, optimized cut list, sheet nesting, framing drawings match hand count | Partial: framing quantities (`TestShed.test_hand_count`) and sheathing sheets (`test_sheathing_hand_count`) match hand counts; lumber plan places every piece. Framing drawings with member tags matching the cut list (`Construction_Drawing`; `TestConstructionApp.test_drawing`, page inspected visually) (5.6.5) |

## Verification

- `python3 src/Mod/Construction/TestConstruction.py` (no application needed):
  geometry, layouts, checks, library, and every tutorial example (doctest).
- In the application (local macOS build): `FreeCADCmd -t TestConstruction`,
  `FreeCADCmd -t TestConstructionApp` (every object builds a valid solid, edits
  regenerate, bad sizes mark objects invalid, members follow edges,
  spreadsheets and the drawing page are written), and
  `FreeCAD -t TestConstructionGui` (commands registered and runnable from the
  workbench, Tools menu entries, palette, radial menu, hotkey strip, a context
  hotkey running its command). All pass.
- Not yet followed by hand: the tutorials' GUI steps in an interactive session.

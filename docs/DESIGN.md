<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: design document added by the CADApp fork.
-->

# Parametric CAD/Construction Application — Design Document

Working name: `CADApp` (placeholder; final name required before first public release, §11).

**Strategy: fork of FreeCAD.** The application is a fork of FreeCAD (LGPL-2.1-or-later), rebranded, with the construction module, context-hotkey UX, and the gaps listed per phase added on top. See `SURVEY.md` for the reuse analysis.

Implement phase by phase. Do not start a phase until the previous phase's exit criteria pass. Feature lists in each phase are the **target spec**; much of it already exists upstream. Every phase from 1 onward starts with an audit (§5.0).

**Inherited-feature rule:** features implemented upstream stay enabled by default. Do not disable or remove them. Where an inherited feature conflicts with this document (§1 network rule, §12 risk register), record the conflict in `docs/inherited-conflicts.md` and isolate it behind a compile/runtime flag that defaults to **on**, so it can be removed later if required.

---

## 1. Decisions

| Item | Decision |
|---|---|
| Platform | Desktop: Windows, macOS, Linux |
| Base | Fork of FreeCAD, starting from the latest stable release tag (1.1.x at time of writing) |
| Native file format | FreeCAD `.FCStd` (inherited; keeps compatibility with upstream) |
| Geometry kernel | OpenCascade Technology (OCCT), LGPL 2.1 + exception; version follows upstream |
| Modules in scope | Parametric solid/surface/direct/freeform modeling, 2D drafting, drawings, assemblies, sheet metal, structural frames, construction module, rendering, simulation (FEA), CAM, generative design. Electronics/PCB deferred (Phase 13 placeholder). |
| Material standards | US imperial and metric, region-switchable per document |
| App license | LGPL-2.1-or-later, matching upstream, so changes can be contributed back and upstream merges stay simple. New files use the same license. Binaries that link Apache-2.0 libraries are distributed under LGPL-3.0 terms (permitted by "or later"). GPL programs (CalculiX GPL-2.0-only, Gmsh, LibreDWG) run only as separate executables, never linked. GPL-only source (SolveSpace, QCAD, OpenCutList, Dune 3D, Bonsai, Fasteners add-on) is reference only and must not be copied into the fork. |
| Dependencies | Open source only. No commercial SDKs. Functionality normally provided by commercial SDKs is implemented in-house or via open-source libraries. |
| Network | Code added by the fork makes no network requests (no accounts, cloud, telemetry, update checks, marketplace). Inherited upstream network features (Addon Manager online fetching, online Help) remain enabled per the inherited-feature rule and are listed in `docs/inherited-conflicts.md`. |

---

## 2. IP Constraints

- Clean-room implementation. No code, icons, UI layouts, help text, sample files, or tutorials copied from SolidWorks, SketchUp, Fusion 360, or other commercial CAD.
- No reverse engineering of proprietary native formats (.sldprt, .sldasm, .f3d, .f3z, .skp, Parasolid .x_t). Interoperate via neutral and open formats (STEP, IGES, STL, OBJ, 3MF, glTF, COLLADA .dae, DXF, DWG via LibreDWG, IFC). Users of other apps export to these formats.
- Fork compliance: keep all upstream copyright and license notices; keep full git history; mark fork-modified files in their headers; include upstream `LICENSE` files.
- Rebrand completely: new product name, icons, splash, About dialog, installer names, window titles. No FreeCAD logo (registered trademark of the FreeCAD Project Association). The word "FreeCAD" may be used only in factual statements ("based on FreeCAD", "opens .FCStd files"). Include a non-affiliation statement.
- All dependencies must carry licenses compatible with LGPL-2.1-or-later as described in §1. Ship a `THIRD_PARTY_LICENSES` file listing each dependency, version, and license.
- Use generic names for features. Avoid vendor trademarks (e.g., "Push/Pull", "Press Pull", "T-Splines", "SmartMates", "FeatureManager", "Toolbox"). Names used in this document are generic.
- Default hotkeys defined in §8 are original to this app.
- Building-code span tables (IRC, AWC/NDS) are copyrighted. Do not embed them. Compute spans from beam mechanics using user-supplied or public-domain design values; label code checks as advisory.
- No freedom-to-operate (patent) analysis has been performed. Obtain one from patent counsel before the 1.0 release. Specific risks and required mitigations are in §12; they are binding implementation constraints.

---

## 3. Technology Stack

### 3.1 Inherited from upstream (do not replace)
| Layer | Component | License |
|---|---|---|
| Language | C++ core, Python 3 workbenches/scripting | — |
| Build | CMake (follow upstream build docs) | — |
| UI | Qt | LGPL |
| Viewport | Coin3D (Open Inventor) + Pivy | BSD-3 / ISC |
| Kernel | OCCT | LGPL-2.1 + exception |
| 2D constraint solver | PlaneGCS (Sketcher) | LGPL-2.1-or-later |
| Assembly solver | OndselSolver | LGPL-2.1-or-later |
| FEM meshing | Netgen, Gmsh (external exe), SMESH | LGPL / GPL (external) / LGPL |
| FEA solvers | CalculiX (GPL-2.0-only), Elmer — external executables | GPL (external) |
| CAM geometry | OpenCAMLib | LGPL-2.1 |
| IFC | IfcOpenShell | LGPL-3.0-or-later |
| DWG | LibreDWG external converter (GPL-3.0-or-later, external) | — |
| Linear algebra / misc | Eigen, Boost, Xerces-C, VTK (FEM post) | MPL-2.0 / BSL / Apache-2.0 / BSD |

### 3.2 Added by this fork
| Purpose | Component | License | Phase |
|---|---|---|---|
| 1D stock optimization | OR-Tools (CP-SAT) | Apache-2.0 | 5 |
| Rectangular sheet nesting | libnest2d | LGPL-3.0 | 5, 11 |
| 2D polygon ops / true-shape nesting | Clipper2 + in-house no-fit-polygon | Boost | 5, 11 |
| Mesh booleans | Manifold | Apache-2.0 | 6 |
| Subdivision freeform | OpenSubdiv (license to verify, §12) or in-house Catmull–Clark | — | 6 |
| Photoreal rendering | Cycles | Apache-2.0 | 9 |
| Topology optimization | In-house SIMP (Eigen) | — | 12 |

Rule: add a dependency only after verifying its license against §1 and recording it in `THIRD_PARTY_LICENSES`.

---

## 4. Fork Architecture

### 4.1 Repository layout (upstream)
```
src/Base/     units, quantities, exceptions, persistence
src/App/      document, document objects, properties, expressions, transactions
src/Gui/      main window, commands, shortcuts, 3D view, NaviCube, task panels
src/Mod/<X>/  workbenches (Sketcher, PartDesign, Part, TechDraw, Assembly, BIM, Draft, FEM, CAM, Mesh, Surface, Spreadsheet, Measure, Material, ...)
```

### 4.2 Where fork code goes
| Change type | Location | Rule |
|---|---|---|
| New feature area | New workbench: `src/Mod/Construction/`, `src/Mod/Generative/`, `src/Mod/Render/`, `src/Mod/Freeform/` | Preferred. No upstream conflicts. |
| UX system (hotkey engine, heads-up panel, radial menu, command palette) | `src/Gui/` | Core patch. Keep isolated in new files; minimal hooks into existing files. |
| Fix/extension of an existing workbench | That workbench | Prefer generic changes suitable for upstream contribution. |
| Branding | `src/Gui/Icons`, installer, resources | Isolated branding layer; one config file for name/strings. |

Every change to an upstream file carries a `// FORK:` (C++) or `# FORK:` (Python) marker comment at the change site, to support merges.

### 4.3 Inherited models (use, do not redesign)
- Document model: `App::Document`, `DocumentObject`, properties, dependency graph, recompute, transactions/undo.
- Parameters and expressions: Spreadsheet, expressions engine, VarSets.
- Topological naming: upstream implementation (FreeCAD 1.0+).
- Units: `Base::Quantity` and unit schemas. Verify feet-inch-fraction input (`3' 4-1/2"`); add parser support if missing.
- File format: `.FCStd` (ZIP: `Document.xml`, `GuiDocument.xml`, BREP files, thumbnails).

### 4.4 Upstream sync
- Remote `upstream` = FreeCAD repository. Fork `main` tracks the chosen stable release tag; merge each new upstream stable release within 30 days of its publication.
- Upstream any generic bug fix or improvement to reduce divergence.
- CI runs upstream's test suite plus fork tests on every merge.

---

## 5. Build Phases

### 5.0 Audit step (applies to Phases 1–13)
1. Inventory upstream functionality against the phase's target scope.
2. Write `docs/gaps/phase-N.md`: each target item marked Present / Partial / Missing, with the upstream file or command implementing it.
3. Implement only Partial/Missing items; Present items get UX alignment (hotkey context layer, §8) only.
4. Exit criteria are tested regardless of whether the feature was inherited or built.

### Phase 0 — Fork Setup, Rebrand, Compliance, Core UX
**Target scope**
- Fork repository; `upstream` remote; branch from latest stable tag; reproducible builds and installers on Windows, macOS, Linux in CI (MSI, DMG, AppImage/Flatpak); upstream test suite passing.
- Rebrand per §2: name, icons, splash, About (credits FreeCAD, non-affiliation statement), window titles, installer metadata, user data directory name (must not collide with upstream installs).
- Compliance files: `LICENSE` (upstream), `THIRD_PARTY_LICENSES`, `CONTRIBUTING.md` (clean-room attestation, §12 R20), `LEGAL.md`, SPDX headers on new files, license and reserved-term CI checks (§12 R21).
- Network rule (§1): static CI check for network APIs (`QNetworkAccessManager`, `urllib`, `requests`, `http.client`, sockets) in fork-added code. Inventory inherited network features (Addon Manager, online Help, others found) into `docs/inherited-conflicts.md`; leave them enabled.
- DWG: inherited converter options (LibreDWG, ODA File Converter, QCAD Pro) remain as upstream provides them; the fork bundles only LibreDWG and ships no commercial converter.
- Inherited risk-register conflicts (§12): NaviCube (R1) and CAM Adaptive (R3) stay enabled by default; isolate each behind a flag defaulting to on; record in `docs/inherited-conflicts.md`.
- Core UX layer in `src/Gui/` (§6, §8): context-layered hotkey engine, heads-up hotkey strip, next-tool suggestions, command palette, radial menu, inline value entry framework. Build on upstream's command and shortcut system; audit it first.

**Exit criteria**: Branded build installs side-by-side with upstream FreeCAD on all 3 OS; upstream tests pass; fork-added code passes the network-API check; `docs/inherited-conflicts.md` lists all inherited conflicts with their flags (default on); hotkey context layers switch with the active tool; remap a hotkey; command palette finds any registered command.

---

### Phase 1 — 2D Sketcher & Constraint Solver
**Upstream baseline (verify in audit)**: Sketcher workbench (PlaneGCS): geometric and dimensional constraints, DOF/constraint-state display, on-view parameters, Dimension tool, offset/scale/rotate/move, continuous trim (1.0); text in sketch (upcoming upstream 26.3).

**Known gaps**: Inference-snapping UX and indicators, conflict diagnosis with suggested removal, hotkey context layers. Confirm via audit.

**Target scope**
- Sketch on plane, face, or construction plane; sketch-on-sketch reference projection.
- Entities: point, line, centerline, polyline, rectangle (2-point, 3-point, center), parallelogram, polygon (inscribed/circumscribed, N sides), circle (center, 2-point, 3-point, tangent), arc (3-point, center, tangent), ellipse, elliptical arc, parabola, conic, spline (fit-point and control-point), slot (straight, center, arc), fillet, chamfer, text (TrueType fonts → curves), point patterns.
- Construction geometry toggle.
- Editing: trim, extend, split, offset (with chain selection), mirror, move, rotate, scale, copy, linear pattern, circular pattern, stretch, break, join.
- Geometric constraints: coincident, collinear, parallel, perpendicular, tangent, curvature-continuous (G2), horizontal, vertical, equal, symmetric, concentric, midpoint, fix, point-on-curve, pierce.
- Dimensional constraints: linear, horizontal, vertical, aligned, radius, diameter, angle, arc length, driving vs. driven (reference).
- Auto-constraint inference while drawing (snap to endpoints, midpoints, centers, intersections, tangents, horizontal/vertical alignment, extensions) with visual indicators; toggle per inference type.
- Solver: degree-of-freedom display, color-coded constraint state (under/fully/over-defined, conflicting), conflict diagnosis with suggested constraint to remove, drag of under-defined geometry.
- Inline numeric entry while drawing (length/angle fields, Tab to cycle).
- Project/include/intersect 3D edges into sketch.
- Sketch profile detection (closed regions, nested loops) with region highlight.
- Import DXF into sketch.

**Exit criteria**: Fully constrain a 100-entity sketch; solver resolves in <50 ms; dimension edits propagate; conflict dialog identifies the offending constraint.

---

### Phase 2 — Parametric Part Modeling
**Upstream baseline (verify in audit)**: PartDesign (pad/pocket/revolution/groove/loft/sweep/helix/hole with thread tables/fillet/chamfer/draft/thickness/patterns/boolean/datums), Part workbench, Spreadsheet + expressions, VarSets, topological naming fixes (1.0), Measure, transparent previews and draggers (1.1).

**Known gaps**: Variants UI (upstream uses spreadsheet configuration tables), emboss/wrap, wall-thickness check, timeline view. Hole/thread table data provenance under §12 R13.

**Target scope**
- Feature history tree (model browser) + horizontal timeline; history marker (drag to roll back); reorder by drag with dependency validation; suppress/unsuppress; rename; group into folders; edit feature in place.
- Topological naming implementation (§4.3).
- Construction geometry: planes (offset, angle, 3-point, normal-to-curve, midplane, tangent), axes, points, coordinate systems.
- Solid features:
  - Extrude: blind, symmetric, two-sided, to next, to face/body, through all; draft angle; thin-wall; operations new body / join / cut / intersect.
  - Revolve, sweep (path, guide rails, twist, orientation options), loft (profiles, rails, centerline, tangency conditions), helix/coil, rib, web.
  - Hole tool: simple, counterbore, countersink, tapped, clearance, pipe threads; ISO metric and UTS size tables (data sourcing per §12 R13); cosmetic and modeled threads.
  - Fillet (constant, variable, face, full-round, setback), chamfer (distance, distance-angle, two-distance), shell, draft, thicken, emboss/deboss, wrap, split body, combine (boolean), move/copy body, scale body, mirror, linear/circular/curve-driven/sketch-driven/fill patterns, pattern of features/faces/bodies.
- Multi-body parts.
- Parameters: user parameters table, expressions referencing feature dimensions, units-aware; equation editor; global variables; link to external parameter file (CSV/JSON).
- Variants (multiple configurations of one part): per-variant parameter values, suppression states, and properties; tabular editor; spreadsheet import/export.
- Materials (physical): density, appearance assignment; mass properties (mass, volume, area, center of mass, moments of inertia).
- Inspection: measure (distance, angle, radius, area, min distance), section view (planar, multiple planes), draft analysis, curvature/zebra analysis, interference check, wall-thickness check.
- Custom properties (part number, description, material, vendor) for BOMs.

**Exit criteria**: Build a 30-feature bracket driven by 5 parameters; change any parameter and all features rebuild without broken references; reorder/suppress works; mass properties match analytic values within 1e-6 relative.

---

### Phase 3 — 2D Drafting & Engineering Drawings
**Upstream baseline (verify in audit)**: TechDraw (views, sections, details, dimensions, hatching, GD&T annotations, weld symbols, PDF/SVG/DXF export); Draft workbench (2D drafting, layers, DXF).

**Known gaps**: Model/paper space and xrefs, drafting standard presets, auto-ballooning, associative cut-list tables, DWG export limited by LibreDWG (≤R2004).

**Target scope**
- Standalone 2D drafting workspace (no 3D required): all Phase 1 entities plus layers, line types, line weights, colors, blocks/symbols, hatching, xrefs, model/paper space, viewports, snaps, polar/ortho tracking, object snap overrides.
- Drawings from 3D: sheet sizes (ANSI A–E, ISO A4–A0, custom), sheet templates, title blocks with property-linked fields, multiple sheets.
- View types: base/standard, projected (first/third angle), auxiliary, section (full, half, offset, aligned), detail, broken, break-out, crop, exploded (from assemblies), isometric.
- Hidden-line removal, tangent edge display options, shaded views.
- Annotation: dimensions (linear, ordinate, baseline, chain, angular, radial, diameter, chamfer, arc length), auto-dimension, model-dimension import, tolerances (±, limits, fits ISO 286), GD&T feature control frames and datums (ASME Y14.5 / ISO 1101 symbols), surface finish, weld symbols, notes, leaders, balloons (auto-balloon), centerlines/center marks, revision tables, hole tables, BOM tables, cut-list tables.
- Associativity: drawing updates on model change; dangling annotation detection.
- Dimension/drafting standards: ANSI, ISO, DIN, JIS presets; editable style manager.
- Export: PDF (vector), DXF, DWG, SVG, PNG; print with scale.

**Exit criteria**: Produce a 3-view + section + detail drawing of the Phase 2 bracket with GD&T; change model; drawing updates; PDF/DXF output opens in third-party viewers.

---

### Phase 4 — Assemblies
**Upstream baseline (verify in audit)**: Assembly workbench with OndselSolver: grounding, joints, exploded views, BOM.

**Known gaps**: Motion study with video export, interference/clearance detection, large-assembly mode, standard parts library (Fasteners add-on is GPL-2.0 and cannot be merged; build with sourced data per §12 R13).

**Target scope**
- Insert components (internal/external files), in-context part creation, sub-assemblies, flexible sub-assemblies.
- Top-down design: reference geometry across components, skeleton/master-sketch layout parts, external reference management (lock/break).
- Joints/mates: rigid, revolute, slider, cylindrical, pin-slot, planar, ball, coincident, concentric, distance, angle, tangent, parallel, perpendicular, limits, gear, rack-pinion, screw, cam, belt/chain path, width/symmetric.
- Assembly solver with DOF display and over-constraint diagnosis; drag to move under-constrained parts.
- Ground/fix, component patterns (linear, circular, feature-driven), mirror components.
- Interference/clearance detection, hole alignment check.
- Exploded views with step sequencing and trail lines; animate explode.
- Motion study: drive joints by value/time, contact, collision detection, motion animation export (video).
- Standard parts library: fasteners (bolts, screws, nuts, washers, pins), bearings; parametric generation by size; dimensional data sourced per §12 R13.
- Large-assembly mode: lightweight loading, LOD, instancing, display simplification.
- BOM: indented/flattened, quantity rollup, custom columns, export CSV/XLSX.
- Component replacement, collect project (copy a document and all referenced files to a folder or archive).

**Exit criteria**: 500-component assembly loads in <10 s on reference hardware; 4-bar linkage animates; BOM exports correctly.

---

### Phase 5 — Construction & Woodworking Module
**Upstream baseline (verify in audit)**: BIM workbench (walls, windows, doors, structural members with profiles, stairs, roofs, spaces, schedules, native IFC); Woodworking add-on (MIT: cabinets, dowels, drilling, cut lists) may be incorporated with credit.

**Known gaps**: Primary differentiator. Framing generators, member/joinery model, region-switchable material libraries, 1D/2D cut optimization, framing drawings, build sequences. Implement as `src/Mod/Construction/`, building on BIM objects where possible so IFC export works.

**Target scope**

**5.1 Material library** (data-driven; see §9)
- Dimensional lumber: US nominal (1x, 2x, 4x, 6x sizes; actual dimensions; stock lengths 8–20 ft) and metric (e.g., 38×89, 45×95, 45×145, etc.; stock lengths 2.4–6.0 m).
- Engineered lumber: LVL, glulam, I-joists (generic profiles, user-extendable).
- Sheet goods: plywood, OSB, MDF, particleboard, drywall, cement board; US 4×8 ft and metric 1220×2440 / 1200×2400 mm; thickness lists.
- Hardwood stock (S4S, rough with board-foot calc).
- Steel: studs/track, angle, channel, tube, I/W-beams (public standard dimensions).
- Masonry/concrete: CMU, brick, concrete (poured volume), rebar.
- Roofing, siding, insulation, membranes (area-based materials).
- Hardware: hinges, drawer slides, shelf pins, connectors, joist hangers, anchors, fasteners (generic, user-extendable).
- Per-material: actual dimensions, grain direction, density, cost (user price table), supplier SKU field.
- Region switch per document (US / metric); user libraries and overrides.

**5.2 Structural members**
- "Member" object: extruded profile along a path with material, grain orientation, end cuts (square, miter, bevel, compound, birdsmouth, plumb/seat), notches, holes.
- Sheet object: panel with thickness, edge banding, grain.

**5.3 Joinery** (parametric, applied between members)
- Butt, miter, lap, half-lap, dado, rabbet, groove, mortise-and-tenon, bridle, dovetail (through, half-blind), box/finger, dowel, biscuit, pocket screw, domino-style loose tenon, scarf.
- Fastener placement rules (spacing, edge distance) with automatic hardware BOM entries.

**5.4 Generators** (parametric, editable after creation, produce members/sheets)
- Wall framing: length, height, stud spacing (16"/24" OC or 400/600 mm), plates (single/double), openings (door/window with header sizing input, king/jack/cripple studs, sills), corners (3-stud, California), T-intersections, blocking rows.
- Floor framing: joists, rim/band, blocking/bridging, beams, posts, openings.
- Roof framing: gable, hip, shed, gambrel; rafters, ridge, collar ties, ceiling joists, overhangs, fascia; truss layout (common, scissor, attic) as members or placeholders.
- Stairs: total rise/run, rise/tread rules (configurable limits), stringers, treads, risers, landings, railings.
- Decks: ledger, joists, beams, posts, footings, decking boards with gap, railings.
- Foundations: slab, strip footing, pier/post footings, block wall; concrete volume.
- Sheathing/cladding layers: auto-cover walls/roofs with sheet goods, show seams, cut openings.
- Cabinets: frameless (32 mm system) and face-frame; base, wall, tall, drawer bank, corner; carcass construction options (dado/rabbet/butt/confirmat), back type, toe kick, doors (slab, shaker/frame-and-panel), drawers (box construction, slide clearance rules), shelves (fixed/adjustable), face frames; run layout along a wall with fillers.
- Furniture primitives: tables, shelving units, workbenches (templates).
- Building elements: walls (multi-layer assemblies), doors, windows, openings, floors/levels, rooms with area calc, roofs.
- Templates: sheds (gable/lean-to/gambrel), garage, small house shell, kitchen cabinet run, bookcase, workbench.

**5.5 Analysis (advisory)**
- Beam span/deflection checks from mechanics (simply supported, cantilever, continuous) using user-supplied design values; L/360-style limit selectable.
- Rise/run, headroom, guardrail height checks against user-configurable rule sets.
- No embedded copyrighted code tables (§2).

**5.6 Outputs**
- BOM / purchase list: groups by material and stock length; quantities, cost total.
- Cut list: per part, with dimensions, angles, grain, edge banding, part labels.
- 1D stock optimization: optimal cuts from stock lengths with kerf, minimize waste/cost.
- 2D sheet nesting: rectangular (guillotine) for panel saw; true-shape for CNC (shares Phase 11 engine), grain constraints, kerf, labels.
- Framing plans/elevations (auto-generated drawing views with member tags).
- Step-by-step build sequence views (assembly order, exploded per step).
- Export: CSV/XLSX, PDF shop drawings, labels (printable).

**Exit criteria**: Generate a 10×12 ft (3×3.6 m) gable shed from template; edit wall height and door width; framing regenerates; BOM, optimized cut list, sheet nesting, and framing drawings produce correct quantities (validated against hand count).

---

### Phase 6 — Direct, Surface, Mesh & Freeform Modeling
**Upstream baseline (verify in audit)**: Part and Surface workbenches (OCCT surfacing), Mesh/MeshPart (repair, mesh-to-shape), Part defeaturing.

**Known gaps**: Direct face editing, quick-modeling draw-and-pull mode, subdivision freeform, Manifold mesh booleans.

**Target scope**
- Direct editing (history-free or as features in history): face drag/offset (inference-driven "draw and pull" workflow for quick massing), move/rotate face, replace face, delete face (heal), resize fillet, make faces coplanar/concentric. Direct edits act only on faces the user selects; geometric relationships are kept only when the user explicitly selects or defines them. No automatic detection/maintenance of face relationships during edits (§12 R2).
- Quick-modeling mode: draw shapes on faces, pull regions into solids, inference snapping (on-axis, parallel, perpendicular, on-face), groups/components with instance editing, tape-measure guides, follow-path.
- Surface modeling: extrude, revolve, sweep, loft, boundary/patch, ruled, offset, fill (G0/G1/G2), extend, trim, untrim, knit/stitch, thicken to solid, surface from mesh.
- Curve tools: 3D sketch, projected/composite/intersection curves, helix, spiral, curve through points, isocurve.
- Freeform: subdivision-surface modeling (Catmull–Clark cage), edit vertices/edges/faces, crease, insert edge loop, bridge, symmetry, convert to B-rep. No T-junction local refinement; conversion methods restricted per §12 R4.
- Mesh: import/repair (holes, normals, self-intersections), decimate, remesh, smooth, mesh boolean, mesh section to sketch, mesh-to-B-rep (planar/prismatic and faceted).
- Analysis: curvature combs, zebra, draft, deviation.

**Exit criteria**: Model a shell-style enclosure with G2 blend surfaces; convert a subdivision model to a valid closed solid; repair an STL and convert to solid.

---

### Phase 7 — Sheet Metal, Structural Frames, Molds, Advanced Parts
**Upstream baseline (verify in audit)**: SheetMetal add-on (LGPL-2.1 per its release notes; verify LICENSE before merging): flanges, bends, unfold to DXF/SVG, K-factor tables.

**Known gaps**: Merge or depend on SheetMetal after license check; structural frames tool with cut list; mold tools.

**Target scope**
- Sheet metal: base flange/tab, edge flange, miter flange, contour flange, hem, jog, sketched bend, lofted bend, corner relief/closures, forming tools, unfold/refold, flat pattern with bend table/K-factor/bend deduction, flat pattern export DXF, bend lines on drawings, convert solid to sheet metal.
- Structural frames: sketch-path-based profile insertion (standard and custom profiles), trim/extend between members, end caps, gussets, cut list with lengths and angles, weld beads (cosmetic).
- Mold tools: parting line, parting surface, shut-off surfaces, core/cavity split, draft and undercut analysis.
- Advanced: multi-body to assembly, derived/linked parts, part mirror, library features (reusable parametric feature sets with insertion references).

**Exit criteria**: Sheet-metal enclosure flattens with correct flat length per K-factor; frame cut list matches geometry.

---

### Phase 8 — Data Management, Interop, Automation
**Upstream baseline (verify in audit)**: STEP/IGES/BREP/STL/OBJ/DXF import/export, IFC, Python API, macros and recorder, headless `FreeCADCmd`.

**Known gaps**: Local version history and vault, plugin permissions sandbox, local-only plugin install (Phase 0), headless CLI rebrand. Audit glTF/3MF/COLLADA coverage.

**Target scope**
- Local version history per file (snapshots, diff of parameters/feature tree, restore); branching/merge of feature trees for single-user workflows.
- Project vault: file references, where-used, rename/move with reference repair, revision states (WIP/released), part numbering schemes.
- Full import/export: STEP AP203/214/242 (with PMI where feasible), IGES, STL, 3MF, OBJ, glTF, COLLADA .dae, FBX (via Assimp), DXF/DWG (LibreDWG), SVG, PDF, IFC (IfcOpenShell), XLSX/CSV for BOM/parameters.
- Scripting: full Python API mirroring command set; macro recorder; script-defined features (custom parametric features in history); headless batch mode (CLI) for conversion/BOM generation.
- Plugin SDK (C++ and Python), plugin manager installing from local files/folders only, sandboxed plugin permissions.

**Exit criteria**: Round-trip STEP preserves solids and colors; IFC export of shed opens in a BIM viewer; macro replays recorded session.

---

### Phase 9 — Visualization & Rendering
**Upstream baseline (verify in audit)**: Material workbench and appearance system (1.0); no built-in photoreal renderer.

**Known gaps**: Cycles integration as `src/Mod/Render/`; PBR viewport upgrades; CC0 appearance library.

**Target scope**
- Real-time viewport upgrades: PBR materials, environment lighting (HDRI), shadows, ambient occlusion, section caps, ground plane/reflections.
- Appearance library (all textures and HDRIs CC0 or original, §12 R15) (woods with grain mapping aligned to member grain direction, metals, plastics, glass, paint, concrete), decals, texture mapping (planar/box/cylindrical/UV).
- Photoreal render: Cycles/OSPRay backend; CPU + GPU; progressive and final; denoising; cameras (DOF, FOV), lighting (sun position by location/date/time, area/point/spot), turntable and walkthrough animation, render queue.
- Output: PNG/EXR images, MP4 video.

**Exit criteria**: Render a cabinet run at 1920×1080 with HDRI lighting and wood grain aligned to part grain.

---

### Phase 10 — Simulation (FEA) & Advanced Motion
**Upstream baseline (verify in audit)**: FEM workbench: CalculiX/Elmer/other external solvers, Gmsh/Netgen meshing, result post-processing.

**Known gaps**: Orthotropic wood presets, fast 1D frame solver for construction checks, report export, UX alignment.

**Target scope**
- Pre-processing: study manager, material properties (isotropic and orthotropic for wood), fixtures (fixed, pinned, roller, frictionless), loads (force, pressure, gravity, torque, remote, bearing), contacts (bonded, no-penetration, friction), connectors (bolt, spring, pin), mesh controls (Netgen; local refinement), mesh quality report.
- Analysis types: linear static, modal (frequency), buckling, thermal (steady/transient), basic nonlinear (geometric), drop/impact (later), fatigue (later).
- Beam/frame analysis for structural members (fast 1D solver) — used by Phase 5 for framing checks.
- Solver bridge to CalculiX (external process); job queue; progress/cancel.
- Post-processing: stress (von Mises, principal), displacement, strain, factor of safety, deformed shape animation, probes, section plots, reports (PDF/HTML).
- Advanced motion: rigid-body dynamics with forces, springs, dampers, gravity; reaction-force output for FEA load transfer.

**Exit criteria**: Cantilever beam results within 2% of analytic deflection/stress; modal frequencies of a plate within 3% of reference.

---

### Phase 11 — CAM
**Upstream baseline (verify in audit)**: CAM workbench: profile, pocket, drilling, engrave, V-carve, surface/waterline (OpenCAMLib), simulator, post-processors, new tool library (1.1). Adaptive operation present and enabled (inherited; §12 R3).

**Known gaps**: Nesting, construction-part→CNC automation, laser/plasma cutting operations (audit), setup sheets.

**Target scope**
- Setups: machine type (3-axis router/mill, lathe, laser/plasma/waterjet; 3+2 and 4/5-axis later), stock definition, work coordinate system, fixtures.
- Tool library: end mills, ball, bull, V-bit, drills, chamfer, engraving, surfacing; feeds/speeds calculator by material; user-extendable; import/export.
- 2D toolpaths: facing, contour/profile (with tabs, ramps, lead-in/out, multiple depths), pocket, trochoidal clearing, offset clearing with corner arc smoothing and feed reduction (constant-engagement clearing only after §12 R3 clearance), slot, drill/peck/bore/tap, chamfer, engraving, V-carve, thread milling.
- 3D toolpaths: roughing (offset/trochoidal), parallel, contour/waterline, scallop, pencil, spiral, radial, rest machining.
- Lathe: facing, turning, grooving, threading, parting.
- Cutting (laser/plasma/waterjet): kerf compensation, pierce points, lead-ins, common-line cutting.
- Nesting: true-shape nesting of parts on sheets (shared with Phase 5); part labels; remnant tracking.
- Construction integration: auto-generate CNC toolpaths for cabinet parts (shelf-pin holes, dadoes, profile cuts) from Phase 5 parts.
- Simulation: stock removal simulation, gouge and collision detection (tool, holder), cycle-time estimate.
- Post-processors: scriptable post engine (Python/JS); stock posts for Grbl, LinuxCNC, and generic dialects labeled "Fanuc-compatible", "Haas-compatible", "Mach3/4-compatible" (nominative use only, §12 R16); G-code editor/viewer.
- Setup sheets (PDF/HTML).

**Exit criteria**: Cabinet side panel → nested sheet → toolpaths → G-code; simulation shows no gouges; G-code runs in a reference simulator (e.g., CAMotics) matching geometry.

---

### Phase 12 — Generative Design / Topology Optimization
**Upstream baseline (verify in audit)**: None built in. External `beso` add-on (LGPL-3.0, BESO + CalculiX) is reference only.

**Known gaps**: Entire phase, as `src/Mod/Generative/`.

**Target scope**
- Inputs: design space, preserve regions, obstacle regions, loads/constraints (from Phase 10), material, objectives (min mass, max stiffness), constraints (stress, displacement, mass target), manufacturing constraints (symmetry, min member size, draw direction, overhang limit for AM, 2.5-axis milling).
- Solver: density-based topology optimization (SIMP) on voxel/tet mesh; GPU acceleration optional.
- Parameter sweeps over optimization inputs with a results table (mass, stress, displacement). Workflow scope restricted per §12 R6.
- Output: smoothed mesh → subdivision/B-rep conversion (Phase 6) → editable body.

**Exit criteria**: Bracket optimization reduces mass ≥40% under stress limit; result converts to valid solid and re-validates in FEA.

---

### Phase 13 — Electronics / PCB (DEFERRED — do not implement)
**Upstream baseline (verify in audit)**: KiCad interop add-ons exist (license not verified).

**Known gaps**: Deferred.

Scope, depth (full PCB tool vs. interop with an external open-source ECAD tool), and approach are undecided. The list below is a placeholder only. Earlier phases must not take dependencies on it.

**Placeholder scope**
- Schematic capture: symbols, multi-sheet, hierarchical, net labels, buses, ERC.
- Component library: symbol + footprint + 3D model linkage; library editor; import KiCad libraries (file-format interop).
- PCB layout: board outline from mechanical sketch, layers (2–16), footprint placement, interactive and push-and-shove routing, vias, copper pours, DRC with rule sets, differential pairs (later).
- ECAD–MCAD sync: PCB as 3D body in assemblies; enclosure ↔ board outline associativity; component height checks.
- Outputs: Gerber RS-274X, Excellon drill, pick-and-place, BOM, PCB 3D STEP export.

**Exit criteria**: 2-layer board designed from schematic passes DRC; Gerbers validate in a third-party viewer; board fits generated enclosure in assembly.

---

## 6. Cross-Cutting UI Requirements (core built in Phase 0; applied to every workbench in later phases)

- Workspaces: Design, Sketch, Drafting, Drawing, Assembly, Construction, Render, Simulate, Manufacture, Generative, Electronics. Map onto upstream workbenches; each shows only relevant toolbars.
- Contextual heads-up panel: when a command runs, a compact input panel appears near the cursor with fields, options, and current context hotkeys.
- Radial menu on right-drag: 8 context-dependent commands, user-configurable.
- Inline value entry: typing a number during any drag/draw sets the active dimension.
- Live preview for every feature before commit.
- Model browser: search/filter, isolate, hide/show, color by status (OK/warning/error).
- Error panel listing rebuild errors with "go to feature" and suggested repair.
- Measurement always available (no command interruption).
- Accessibility: full keyboard navigation, scalable UI (100–300%), high-contrast theme, screen-reader labels on panels.
- Localization-ready strings (English first).
- First-run tutorial and searchable help (original content).

---

## 7. Performance Targets (reference hardware: 8-core CPU, 16 GB RAM, mid-range GPU)

| Operation | Target |
|---|---|
| App cold start | < 3 s |
| Sketch solve (100 entities) | < 50 ms |
| Parameter change rebuild (30-feature part) | < 1 s |
| Viewport | 60 fps at 1M triangles |
| Open 500-component assembly | < 10 s |
| Autosave | non-blocking, every 5 min (configurable) |

Recompute runs off the UI thread; UI remains responsive and recompute is cancelable.

---

## 8. Hotkey System Specification

### 8.1 Engine
- Layered resolution: **Command-context layer** (active tool) → **Workspace layer** → **Global layer**. First match wins.
- Each binding: `{key_chord, command_id, context_predicate, priority}`.
- Contexts include: active workspace, active command, selection type (edge/face/body/sketch entity/component), edit mode.
- Heads-up hotkey strip: shows the context layer's bindings for the active tool at the bottom of the viewport; toggle with `F1`.
- "Next tool" suggestions: after a command completes, the strip shows 3–5 commonly following commands with single-key bindings (e.g., after closing a sketch: Extrude, Revolve, Sweep). Suggestions are rule-based by default; optional local usage statistics re-rank them (stored locally, never transmitted).
- Remapping UI with search, conflict detection per layer, reset to default, profile import/export (JSON).
- Chords and sequences supported (e.g., `G` then `H`).

### 8.2 Default Global Layer
| Key | Command |
|---|---|
| `Space` | Command palette |
| `Esc` | Cancel / exit command / clear selection |
| `Enter` | Confirm / repeat last command (when idle) |
| `Ctrl+Z` / `Ctrl+Y` (`Cmd` on macOS) | Undo / Redo |
| `Ctrl+S` | Save |
| `Delete` | Delete selection |
| `F` | Zoom to fit / selection |
| `M` | Measure |
| `H` | Hide selected; `Shift+H` show all; `Alt+H` isolate |
| `X` | Section view toggle |
| `1–7` (numpad or top row with modifier) | Standard views (front, back, left, right, top, bottom, iso) |
| `5` | Toggle perspective/orthographic |
| `Q` | Quick sketch on selected face/plane |
| `W` | Cycle display mode |
| `` ` `` | Cycle workspace |

### 8.3 Default Sketch Layer (active in sketch)
| Key | Command |
|---|---|
| `L` | Line |
| `R` | Rectangle (Tab cycles 2-point/center/3-point) |
| `C` | Circle |
| `A` | Arc |
| `P` | Polygon |
| `S` | Spline |
| `O` | Offset |
| `T` | Trim |
| `D` | Dimension (type inferred from selection) |
| `G` | Construction toggle |
| `K` | Constraint menu (radial) |
| `Shift+M` | Mirror |
| `F2` | Finish sketch |

### 8.4 In-Command Context Layers (examples; each tool defines its own)
**Line tool active**
| Key | Action |
|---|---|
| `Tab` | Cycle length/angle input fields |
| `A` | Switch to tangent arc from current endpoint |
| `G` | Toggle construction for next segment |
| `H` / `V` | Lock horizontal / vertical |
| `Shift` (hold) | Suppress inference |
| `Backspace` | Undo last segment |
| `Enter` | End chain |

**Extrude active**
| Key | Action |
|---|---|
| `Tab` | Cycle distance/taper fields |
| `F` | Flip direction |
| `S` | Symmetric |
| `B` | Two-sided |
| `T` | Extent: to object |
| `J` / `U` / `I` / `N` | Join / Cut / Intersect / New body |
| `W` | Thin-wall toggle |

**Fillet active**
| Key | Action |
|---|---|
| `Tab` | Radius field |
| `E` | Add edge chain (tangent propagation) |
| `V` | Variable radius mode |
| `C` | Switch to Chamfer keeping selection |

**Member placement (Construction workspace)**
| Key | Action |
|---|---|
| `R` | Rotate profile 90° |
| `O` | Cycle insertion alignment (9-point) |
| `M` | Cycle material size (from current library) |
| `Shift+L` | Length input |
| `E` | End-cut options |
| `A` | Array along path at spacing |

**Wall framing generator**
| Key | Action |
|---|---|
| `D` / `N` | Insert door / window opening |
| `S` | Cycle stud spacing |
| `P` | Toggle double top plate |
| `C` | Corner type |

Assembly, Drawing, CAM, and Simulation layers follow the same pattern; each command spec must include its context layer table.

---

## 9. Construction Library Data Format

- Location: `src/Mod/Construction/Resources/libraries/{region}/*.json` + user overrides in user data folder.
- Schema (per item):
```json
{
  "id": "lumber.us.2x4",
  "category": "dimensional_lumber",
  "region": "US",
  "name": "2x4",
  "nominal": {"w": 2, "h": 4, "unit": "in"},
  "actual": {"w": 38.1, "h": 88.9, "unit": "mm"},
  "stock_lengths_mm": [2438.4, 3048, 3657.6, 4267.2, 4876.8],
  "grain_axis": "length",
  "density_kg_m3": 450,
  "species_options": ["SPF", "DF-L", "SYP"],
  "design_values": null,
  "price": {"per": "piece", "by_length": {}},
  "sku": null,
  "source": "e.g., US DOC Voluntary Product Standard PS 20 (public domain)",
  "data_license": "public-domain"
}
```
- `design_values` populated only by the user or from public-domain sources.
- `source` and `data_license` are required for every shipped entry (all libraries: construction, fasteners, threads, fits, steel shapes). CI rejects entries without them or with a license not on the allowlist (public-domain, CC0, CC-BY, GPL-compatible).
- Library editor UI: add/edit/duplicate items, import/export CSV, price list import.

---

## 10. Testing Strategy

- Upstream test suite (C++ gtest and Python `TestApp`) must pass on every merge.
- Unit tests per new module; tolerance assertions for geometry.
- Golden-model regression suite: reference `.FCStd` files rebuilt each CI run; compare volume, area, topology counts, and bounding box.
- Topological-naming stress tests (inherited implementation): scripted upstream edits on 50+ models, assert references resolve.
- Constraint solver fuzz tests.
- Construction module: BOM/cut-list snapshot tests for each template.
- Simulation/CAM: analytic benchmark comparisons (exit criteria values).
- Viewport image-diff tests.
- File format migration tests for every schema version.
- Performance benchmarks tracked in CI (§7).
- Network-isolation test (Phase 0) on every CI run.

---

## 11. Open Questions

1. **Product name** — required before first public release; trademark search per §12 R17.
2. **Upstream contribution policy** — which fork changes to submit upstream (recommended: generic fixes and the hotkey engine if accepted).
3. **Reference hardware** for performance targets — confirm or adjust §7.
4. **Construction rule sets**: which jurisdiction defaults (e.g., US IRC-derived limits entered by user vs. EU) should ship as editable presets?
5. **Localization**: languages beyond English, and when.
6. **Electronics (Phase 13)**: deferred; scope and approach to be decided later.

---

## 12. Legal Risk Register

Not legal advice. This register identifies risks and design-arounds; it does not eliminate liability. Patent status must be confirmed by patent counsel (FTO) before 1.0. Patent expiry dates below are from public sources and may be affected by term adjustments, continuations, and foreign counterparts.

### 12.1 Patent risks

| ID | Area (doc location) | Potential claimant / basis | Required mitigation |
|---|---|---|---|
| R1 | Clickable cube orientation widget (upstream NaviCube; Phase 0) | Autodesk: US 7,782,319 (filed Mar 2007, cube orientation indicator/controller) and continuation US 9,043,707 (listed active) | Upstream ships a clickable NaviCube (`src/Gui/NaviCube.cpp`). Inherited: stays enabled by default, isolated behind a flag (default on). Counsel reviews before 1.0; if required, disable and fall back to a display-only axis triad + standard-view buttons + hotkeys. Fork code must not add new cube-widget functionality. |
| R2 | Direct editing with automatic face-relationship detection (Phase 6) | Siemens (Synchronous Technology / "Live Rules", patent filings from 2008) | Edits apply only to user-selected faces. Relationships maintained only when explicitly user-defined. No automatic relationship-inference engine. FTO before adding any. |
| R3 | Constant-engagement / adaptive clearing toolpaths (Phase 11) | Celeritive (VoluMill; EP 2 681 683 B1 granted 2020), and other CAM vendors | Upstream ships CAM "Adaptive" (constant-engagement clearing). Inherited: stays enabled by default, isolated behind a flag (default on). Counsel reviews before 1.0. Fork code adds no new constant-engagement algorithms without FTO clearance. |
| R4 | Subdivision/freeform and conversion to B-rep (Phase 6) | Autodesk (acquired T-Splines 2011). Core T-spline patent US 7,274,364 expired 2024; later related patents (e.g., US 9,269,189, trim-free T-spline conversion) may be active | Catmull–Clark only (1978). No T-junctions/local knot refinement. Conversion: regular faces → bicubic B-spline patches; extraordinary vertices via methods published ≥20 years ago (cite source in code comments). FTO before release. |
| R5 | Topological naming (§4.3) | Dassault, PTC, Siemens hold patents on persistent naming | Base implementation on OCCT `TNaming`/OCAF and academic methods published before 2005 (e.g., Chen & Hoffmann 1995; Kripac 1997). Record prior-art references in `docs/prior-art/`. FTO. |
| R6 | Generative design workflow (Phase 12) | Autodesk and others hold patents on generative-design workflows (multi-outcome generation, exploration UIs) | Limit to density-based SIMP (Bendsøe 1989; Sigmund 2001 published code) and plain parameter sweeps with a results table. No automated multi-solver outcome generation or outcome-exploration UI modeled on commercial products. FTO. |
| R7 | Construction generators: wall/floor/roof framing, trusses, cabinets, stair calculators, sheet nesting (Phase 5, 11) | Framing/truss software vendors, cabinet/millwork software vendors | FTO search (CPC G06F30/13, G06F30/12, E04B, B27). Rules data-driven, user-editable, derived from conventional carpentry practice. Nesting via published algorithms (bottom-left fill, no-fit polygon, guillotine heuristics). |
| R8 | Face pulling + inference snapping (Phase 6) | Trimble: US 6,628,279 (Push/Pull) expired 2021; later patents on specific inference behaviors may exist | Implement from the expired patent's disclosure and general practice. Include inference engine in FTO scope. |
| R9 | Radial (marking) menus (§6) | Autodesk/Alias (1990s patents, expired) | Low risk. Use generic term "radial menu". |
| R10 | Automatic assembly-constraint inference (Phase 4, if added) | Dassault, others | Not in current scope. Joints are created only by explicit user action. FTO before adding inference. |

### 12.2 Copyright risks

| ID | Area | Potential claimant / basis | Required mitigation |
|---|---|---|---|
| R11 | UI layout, icons, dialogs, help text, tutorials, sample models | All CAD vendors | Original assets only. No competitor screenshots, models, or tutorial files in the repo, tests, or docs. Golden test models created from scratch. |
| R12 | Default hotkeys (§8) | Vendors whose keymaps overlap (single-letter mnemonics) | Shortcuts are functional; risk low (Lotus v. Borland, 1st Cir. 1995, held a menu command hierarchy uncopyrightable; not binding in all circuits). Document mnemonic derivation per key. Do not ship keymap profiles named after or replicating a competitor's full keymap. |
| R13 | Standards data: fastener/thread/hole tables, ISO 286 fits, steel shapes, GD&T and weld symbols, drafting conventions | ISO, ASME, ANSI, DIN, AWS, AISC (copyright in documents; EU sui generis database right on substantial extraction) | Source values from public-domain publications (e.g., US government standards) or openly licensed datasets; record `source` and `data_license` per entry (§9). Draw all symbols originally. Copy no standard text, figures, or table layouts. Allow users to import their own licensed tables. |
| R14 | Building code values (Phase 5) | ICC, AWC | Already constrained (§2). Ship rule presets as generic examples labeled "user must verify for jurisdiction"; no copied code text or tables. |
| R15 | Textures, HDRIs, fonts, icons | Asset owners | CC0, SIL OFL, or original only. Maintain `assets/MANIFEST.json` with source + license per file; CI check. |
| R18 | Open-source license compliance | Copyright holders of dependencies | Verify each dependency's exact license/version against §1 linkage rules before adding. Preserve copyright headers (e.g., PlaneGCS/FreeCAD). SPDX headers on all files (REUSE spec). Provide corresponding source with releases. |
| R19 | AI-generated code reproducing third-party code | Copyright holders of matched code | Run snippet-match scanning (e.g., ScanCode Toolkit) in CI; reject matches to code with incompatible or unknown licenses. |
| R20 | Contributor knowledge of competitor internals | Vendors via EULA (anti-reverse-engineering clauses) | Specs derive from this document and public literature only. Contributors must not decompile or inspect competitor binaries/files. Require DCO sign-off with a clean-room attestation in `CONTRIBUTING.md`. |

### 12.3 Trademark risks

| ID | Area | Potential claimant / basis | Required mitigation |
|---|---|---|---|
| R16 | Third-party names in UI/docs (DWG, Fanuc, Haas, Mach3/4, SketchUp, SolidWorks, Fusion 360, KiCad) | Mark owners | Nominative use only ("opens .dwg files", "Fanuc-compatible post"). No logos. No "certified"/"TrustedDWG"/"RealDWG" claims. Non-affiliation statement in README and About dialog. No competitor names in feature names. |
| R17 | Product name, logo | FreeCAD Project Association (FreeCAD logo registered in Benelux; claims rights over commercial use of name and logo); other mark holders | Rebrand fully (§2). Trademark clearance (USPTO, EUIPO, WIPO) for the new name. Use "FreeCAD" only factually ("based on FreeCAD"), no logo. |
| R21 | Feature names | Vendors | Reserved-term list (do not use as feature/command names): Push/Pull, Press Pull, Follow Me, Hole Wizard, Pack and Go, Rollback Bar, Smart Dimension, SmartMates, Design Table, Configurations (as a feature name), Toolbox, Weldments, FeatureManager, ViewCube, Adaptive Clearing, Dynamic Milling, VoluMill, T-Splines, Live Rules, Synchronous. CI check greps fork-added UI strings for these terms; inherited upstream strings are listed in `docs/inherited-conflicts.md`, not renamed. |

### 12.3a Fork-specific risks

| ID | Area | Basis | Required mitigation |
|---|---|---|---|
| R22 | Inherited upstream features | Upstream features were not reviewed against this register | Phase 0: check every upstream workbench and command against R1–R21; record conflicts in `docs/inherited-conflicts.md` and isolate behind flags defaulting to on (do not disable). Repeat for each upstream merge (diff of new commands/UI strings). |
| R23 | License mixing | LGPL-2.1-or-later fork with Apache-2.0, LGPL-3.0, GPL components | Follow §1 linkage rules; CI dependency-license check; GPL programs only as external executables; no GPL-only source copied in. |

### 12.4 Process requirements

1. FTO opinion from patent counsel before 1.0, covering R1–R10 and any later feature that implements a named technique from a commercial product.
2. `docs/prior-art/`: for each algorithm with patent exposure, publication references with dates and the source the implementation follows.
3. `docs/patent-watch.md`: tracked patents, expected expiry, status; review quarterly.
4. Every feature with patent exposure is isolated behind a compile-time and runtime flag so it can be removed in a patch release if a claim is made.
5. Defensive publication: publish design notes for original techniques (hotkey context engine, construction generators) to establish prior art.
6. `LEGAL.md`: claim/takedown contact address, feature-disable steps, release process.

---

## 13. Rules for Implementation Agents (Claude Code)

1. Read this document, `SURVEY.md`, and the phase's `docs/gaps/phase-N.md` before writing code.
2. Run the §5.0 audit before implementing a phase. Do not reimplement Present items.
3. Place code per §4.2. New workbenches over core patches. Mark upstream-file edits with `FORK:` comments.
4. Do not copy code from GPL-only projects, commercial software, or unlicensed sources. Cite prior art for algorithms with patent exposure in `docs/prior-art/` (§12.4).
5. No network access in fork-added code (§1). Never disable or remove inherited upstream features; record conflicts in `docs/inherited-conflicts.md`. No new dependency without the license check (§3.2).
6. Every shipped data entry has `source` and `data_license` (§9).
7. Each command defines its hotkey context layer (§8.4).
8. Keep upstream tests passing; add tests for every new feature; meet phase exit criteria before moving on.

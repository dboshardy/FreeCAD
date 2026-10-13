<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: design document added by the CADApp fork.
-->

# Parametric CAD/Construction on FreeCAD — Design Document

Working name: `CADApp` (placeholder for the add-on suite; final names required before first public release, §11).

**Strategy: FreeCAD is the base application** (decision 2026-10-12; replaces the earlier rebranded fork). Users run stock FreeCAD. Everything this document adds is delivered as:
- **Add-ons** (plugins) by default: separate workbenches or modules, installed into stock FreeCAD from the Addon Manager or a local folder, that use FreeCAD's Python and C++ APIs without modifying FreeCAD's code. This includes extensions of existing workbenches wherever an add-on can provide them (new commands, objects, panels, posts, exporters).
- **Changes to FreeCAD's code** only when an add-on cannot deliver the feature: the functionality needs a hook FreeCAD does not expose (e.g., per-tool hotkey context), or an add-on would be measurably too slow. Such changes go upstream as pull requests to FreeCAD, kept to the minimal hook, with the feature itself in an add-on where possible. The reason is recorded in the phase's gap document.

No fork of FreeCAD is shipped. See `SURVEY.md` for the reuse analysis, §4.5 for the migration of work already done in this repository's fork, and §14 for a summary of what has been added and how.

Implement phase by phase. Do not start a phase until the previous phase's exit criteria pass. Each phase's **Upstream baseline** names what FreeCAD already provides (checked against the source tree 2026-10-12); its **Target scope** lists only what upstream lacks or covers partially, each item delivered as an add-on or an upstream contribution (§4.2). Every phase from 1 onward starts with an audit (§5.0) to confirm both.

**FreeCAD as is:** add-ons use FreeCAD's features as they are and never patch, disable or replace them. Behaviour FreeCAD should change is proposed upstream.

**Reuse rule:** never reimplement something FreeCAD already provides (a workbench, command, document object, module or bundled library). Before adding code, check that the capability does not already exist: search the source tree (`src/Mod/*`, `src/Gui`, `src/App`, `src/3rdParty`) for its commands, objects and properties, and record the result (what exists, where, and why it falls short) in the phase's gap document. Where upstream covers part of a need, build on its objects (take them as input, subclass, or add properties) and implement only the missing part. A separate implementation needs a written reason in the gap document, such as a constraint upstream cannot meet (e.g., guillotine cuts for a panel saw).

---

## 1. Decisions

| Item | Decision |
|---|---|
| Platform | Desktop: Windows, macOS, Linux |
| Base | Stock FreeCAD, latest stable release (1.1.x at time of writing); add-ons support it and the development version |
| Delivery | Add-ons (Addon Manager `package.xml`, installable from a local folder) and upstream pull requests; no fork, no rebranded build |
| Native file format | FreeCAD `.FCStd` |
| Geometry kernel | OpenCascade Technology (OCCT) as shipped with FreeCAD |
| Modules in scope | Parametric solid/surface/direct/freeform modeling, 2D drafting, drawings, assemblies, sheet metal, structural frames, construction module, rendering, simulation (FEA), CAM, generative design. Electronics/PCB deferred (Phase 13 placeholder). |
| Material standards | US imperial and metric, region-switchable per document |
| License | LGPL-2.1-or-later for add-ons and upstream contributions, matching FreeCAD, so add-on code can move upstream. Add-ons with compiled parts that link Apache-2.0 libraries are distributed under LGPL-3.0 terms (permitted by "or later"). GPL programs (CalculiX GPL-2.0-only, Gmsh, LibreDWG) run only as separate executables, never linked. GPL-only source (SolveSpace, QCAD, OpenCutList, Dune 3D, Bonsai, Fasteners add-on) is reference only and must not be copied into add-ons or contributions. |
| Dependencies | Open source only. No commercial SDKs. Prefer what FreeCAD already bundles; an add-on declares any extra dependency in its `package.xml`. |
| Network | Add-on code makes no network requests (no accounts, cloud, telemetry, update checks, marketplace). FreeCAD's own network features (Addon Manager, online Help) are FreeCAD's and left as they are. |

---

## 2. IP Constraints

- Clean-room implementation. No code, icons, UI layouts, help text, sample files, or tutorials copied from SolidWorks, SketchUp, Fusion 360, or other commercial CAD.
- No reverse engineering of proprietary native formats (.sldprt, .sldasm, .f3d, .f3z, .skp, Parasolid .x_t). Interoperate via neutral and open formats (STEP, IGES, STL, OBJ, 3MF, glTF, COLLADA .dae, DXF, DWG via LibreDWG, IFC). Users of other apps export to these formats.
- Add-on compliance: each add-on carries its `LICENSE`, SPDX headers on every file, and keeps copyright notices of any code it takes from FreeCAD. Upstream contributions follow FreeCAD's contribution guidelines and license.
- Naming: add-ons get their own names and icons. No FreeCAD logo (registered trademark of the FreeCAD Project Association). "FreeCAD" appears only in factual statements ("an add-on for FreeCAD", "opens .FCStd files"), with a non-affiliation statement in each add-on's README.
- All dependencies must carry licenses compatible with LGPL-2.1-or-later as described in §1. Each add-on ships a `THIRD_PARTY_LICENSES` file listing the dependencies it adds, with version and license.
- Use generic names for features. Avoid vendor trademarks (e.g., "Push/Pull", "Press Pull", "T-Splines", "SmartMates", "FeatureManager", "Toolbox"). Names used in this document are generic.
- Default hotkeys defined in §8 are original to this project.
- Building-code span tables (IRC, AWC/NDS) are copyrighted. Do not embed them. Compute spans from beam mechanics using user-supplied or public-domain design values; label code checks as advisory.
- No freedom-to-operate (patent) analysis has been performed. Obtain one from patent counsel before the 1.0 release. Specific risks and required mitigations are in §12; they are binding implementation constraints.

---

## 3. Technology Stack

### 3.1 Provided by FreeCAD (do not replace)
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

### 3.2 Added by add-ons
| Purpose | Component | License | Phase |
|---|---|---|---|
| 1D stock optimization | OR-Tools (CP-SAT) | Apache-2.0 | 5 |
| Subdivision freeform | OpenSubdiv (license to verify, §12) or in-house Catmull–Clark | — | 6 |
| Photoreal rendering | Cycles | Apache-2.0 | 9 |
| Topology optimization | In-house SIMP (Eigen) | — | 12 |

Rule: add a dependency only after verifying its license against §1, declaring it in the add-on's `package.xml` and recording it in the add-on's `THIRD_PARTY_LICENSES`. A dependency FreeCAD itself should carry is proposed upstream. Not added because upstream covers them: sheet nesting (guillotine layout in-house, true-shape via BIM `Arch_Nest`) and mesh booleans (Mesh workbench).

---

## 4. Architecture: FreeCAD plus Add-ons

### 4.1 FreeCAD layout (for reference and upstream contributions)
```
src/Base/     units, quantities, exceptions, persistence
src/App/      document, document objects, properties, expressions, transactions
src/Gui/      main window, commands, shortcuts, 3D view, NaviCube, task panels
src/Mod/<X>/  workbenches (Sketcher, PartDesign, Part, TechDraw, Assembly, BIM, Draft, FEM, CAM, Mesh, Surface, Spreadsheet, Measure, Material, ...)
```

### 4.2 Where new code goes
| Change type | Delivery | Rule |
|---|---|---|
| New feature area (construction and woodworking, rendering, generative design, freeform) | An add-on per area: its own repository with a workbench (`InitGui.py`), `package.xml`, tests, `LICENSE` | Default. Pure Python where possible, using FreeCAD's Python API; compiled parts built against FreeCAD's released libraries. |
| Extension of an existing FreeCAD workbench (a new command, object, TechDraw view, CAM operation or post, exporter) | Add-on that adds commands and objects alongside the workbench, using its Python API | Default. Never patch the workbench's files from an add-on. |
| Feature an add-on cannot provide (needs a hook FreeCAD does not expose, e.g. a new Sketcher constraint inside the PlaneGCS solver, per-tool hotkey context) or that is measurably too slow as an add-on | Upstream pull request to FreeCAD, limited to the minimal hook or the performance-critical part; the rest in an add-on | Exception. Record in the gap document why an add-on cannot do it (missing API, or the measured cost). Fixes of FreeCAD bugs found along the way also go upstream. |
| Core UX (context hotkeys, heads-up strip, command palette, radial menu, inline value entry) | Add-on (Qt event filters, docks and dialogs from Python); upstream PR only for the hooks an add-on lacks (active tool handler as context, context layers ahead of Qt shortcuts) | Palette, radial menu and strip need no FreeCAD change. |
| Branding | None | Users run FreeCAD; add-ons have their own names and icons only. |

### 4.3 FreeCAD models (use, do not redesign)
- Document model: `App::Document`, `DocumentObject`, properties, dependency graph, recompute, transactions/undo.
- Parameters and expressions: Spreadsheet, expressions engine, VarSets.
- Topological naming: upstream implementation (FreeCAD 1.0+).
- Units: `Base::Quantity` and unit schemas. Verify feet-inch-fraction input (`3' 4-1/2"`); if missing, add parser support upstream.
- File format: `.FCStd` (ZIP: `Document.xml`, `GuiDocument.xml`, BREP files, thumbnails). Add-on objects are `FeaturePython` objects saved in it; a document opened without the add-on keeps their shapes.

### 4.4 Supported FreeCAD versions
- Add-ons support the latest FreeCAD stable release and are tested against the development version; each `package.xml` states the minimum version.
- Each new FreeCAD stable release is tested within 30 days of its publication.
- CI installs stock FreeCAD (AppImage, conda or the release DMG/installer) and runs each add-on's tests in it, headless and with the GUI.
- Generic fixes found while building add-ons go upstream rather than into workarounds.

### 4.5 Migration from the fork
Work done before 2026-10-12 lives in this repository's FreeCAD fork. Moving it:

| Fork work | Destination |
|---|---|
| `src/Mod/Construction/` (Construction workbench, libraries, tests) and `docs/tutorials/construction/` | Construction add-on (`addons/construction/`, done 2026-10-13), unchanged in substance; pure Python already. Its tests run in the add-on install. Phase 5.3 rollback applied first |
| `src/Gui/Hotkeys/` and the hooks in `Command.cpp`, `Control.cpp`, `ToolHandler.cpp`, `ShortcutManager.cpp`, `MainWindow.cpp`, `CommandStd.cpp`, `Workbench.cpp` | Rewritten as a UX add-on (command palette, radial menu, hotkey strip, workspace and task-dialog contexts from Python). Only the per-tool context hook (tool handler start/finish, context layers ahead of Qt shortcuts) is proposed upstream as a minimal PR |
| Branding (`src/Main`, `branding/`), installers, `src/App/Fork/FeatureFlags.*`, `src/Ext/freecad/fork_features.py`, the feature-flag sites in FreeCAD files (NaviCube, CAM Adaptive, BIM/Help/download network features), `docs/inherited-conflicts.md` | Retired: FreeCAD is shipped by the FreeCAD project, so its features are not ours to flag |
| `tools/fork/check.py` (network, reserved terms, data licences, SPDX headers, dependencies) | Kept as add-on CI checks; the fork-path and upstream-base checks are dropped |

---

## 5. Build Phases

### 5.0 Audit step (applies to Phases 1–13)
1. Inventory upstream functionality against the phase's target scope.
2. Write `docs/gaps/phase-N.md`: each target item marked Present / Partial / Missing, with the upstream file or command implementing it.
3. Implement only Partial/Missing items; Present items get UX alignment (hotkey context layer, §8) only.
4. Mark each Partial/Missing item **add-on** (default) or **FreeCAD change**, the latter with the reason an add-on cannot do it (§4.2).
5. Exit criteria are tested regardless of whether the feature came from FreeCAD or was built.

### Phase 0 — Add-on Infrastructure, Compliance, Core UX
Done in the fork before 2026-10-12 (branded build, feature flags, hotkey engine in `src/Gui`); migrated per §4.5.

**Target scope**
- Add-on template: repository layout, `package.xml` (Addon Manager metadata, minimum FreeCAD version, dependencies), workbench registration, test runner; installs from a local folder and from the Addon Manager.
- CI per add-on: install stock FreeCAD stable and development builds on Windows, macOS and Linux; run the add-on's tests headless and with the GUI.
- Compliance files per add-on: `LICENSE`, `THIRD_PARTY_LICENSES`, `CONTRIBUTING.md` (clean-room attestation, §12 R20), `LEGAL.md`, SPDX headers, license and reserved-term CI checks (§12 R21).
- Network rule (§1): static CI check for network APIs (`QNetworkAccessManager`, `urllib`, `requests`, `http.client`, sockets) in add-on code.
- Core UX (§6, §8) as a UX add-on: context-layered hotkeys (workspace and task-dialog contexts from Python), heads-up hotkey strip, next-tool suggestions, command palette, radial menu, inline value entry. Build on FreeCAD's command and shortcut system; audit it first. Per-tool context (inside a Sketcher tool) needs a FreeCAD hook: proposed upstream as a minimal PR.

**Exit criteria**: The Construction and UX add-ons install into stock FreeCAD on all 3 OS from a local folder and pass their tests there; add-on code passes the network-API check; workspace-level hotkey layers switch with the workbench and task dialog; remap a hotkey; command palette finds any registered command; the per-tool context hook is proposed upstream.

---

### Phase 1 — 2D Sketcher & Constraint Solver
**Upstream baseline**: Sketcher workbench (PlaneGCS). Sketch on planes and faces (map, reorient), external geometry, projection, intersection, carbon copy, merge and mirror sketches. Entities: point, line, polyline, rectangle (corner, center, 3-point), square, triangle to octagon and regular polygon, circle (center, 3-point), arc (center, 3-point), ellipse, arcs of ellipse, hyperbola and parabola, B-splines (control points, interpolation, periodic), slot, arc slot, fillet, chamfer, text. Construction toggle. Editing: trim, extend, split, offset, symmetry (mirror), translate, rotate, scale, copy, rectangular array, join curves. Constraints: coincident (including concentric), point on object, horizontal, vertical, parallel, perpendicular, tangent, equal, symmetric, block, lock, distance (including arc length), horizontal/vertical distance, radius, diameter, angle, Snell's law; driving/reference toggle; Dimension tool. Autoconstraints while drawing, on-view parameters (inline numeric entry), DOF and constraint-state colors, selection of conflicting, redundant and malformed constraints, dragging under-defined geometry. DXF into sketches via Draft import and Draft_Draft2Sketch.

**Known gaps**: listed below; hotkey context layers (§8).

**Target scope**
- Circle tangent to existing curves; stretch.
- Constraints: collinear (as one constraint), curvature-continuous (G2), pierce.
- Inference indicators while drawing (endpoint, midpoint, center, intersection, tangent, alignment, extension) with a toggle per inference type.
- Conflict diagnosis that suggests the constraint to remove.
- Sketch profile detection (closed regions, nested loops) with region highlight.

**Exit criteria**: Fully constrain a 100-entity sketch; solver resolves in <50 ms; dimension edits propagate; conflict dialog identifies the offending constraint.

---

### Phase 2 — Parametric Part Modeling
**Upstream baseline**: PartDesign: body, datum planes/lines/points, coordinate systems, shape binders; pad and pocket (length, two lengths, symmetric, up to face/shape, through all, taper angle), revolution, groove, additive/subtractive loft, pipe (sweep) and helix, primitives; hole (counterbore, countersink, counterdrill; ISO metric, UNC/UNF/UNEF, NPT, BSP; cosmetic and modeled threads); fillet, chamfer (distance, two distances, distance-angle), draft, thickness (shell), boolean, defeaturing; mirrored, linear, polar, path, point, scaled and multi-transform patterns; clone; tip (roll back), move feature in tree, suppress (`Suppressed`), rename, groups; transparent previews and draggers (1.1). Part workbench: multi-body, extrude, revolve, loft, sweep, offset, thickness, mirror, booleans, slice, link arrays. Spreadsheet, expressions, VarSets, CSV import. Topological naming (1.0). Material workbench (density, appearance). Measure: distance, angle, length, area, radius, diameter, position, center of mass, mass properties. Part section and section cut. Dynamic properties for custom fields.

**Known gaps**: listed below. Hole/thread table data provenance under §12 R13.

**Target scope**
- Horizontal timeline view with a draggable history marker; dependency check when reordering.
- Thin-wall extrude; rib and web.
- Fillet: variable radius, face, full-round and setback (PartDesign).
- Emboss/deboss and wrap.
- Fill pattern; patterns of bodies inside PartDesign.
- Parameters linked to an external JSON file.
- Variants (multiple configurations of one part): per-variant parameter values, suppression states and properties in a tabular editor, over upstream's spreadsheet configuration tables.
- Inspection: draft analysis, curvature/zebra analysis, interference check, wall-thickness check.

**Exit criteria**: Build a 30-feature bracket driven by 5 parameters; change any parameter and all features rebuild without broken references; reorder/suppress works; mass properties match analytic values within 1e-6 relative.

---

### Phase 3 — 2D Drafting & Engineering Drawings
**Upstream baseline**: TechDraw: ASME and ISO templates with fillable title-block fields, multiple pages; views, projection groups (first/third angle), section and complex (offset, aligned) section, detail, broken view, clip group (crop), axonometric views, Arch/BIM section views, Draft views, spreadsheet tables, hidden lines and smooth/seam edge display, shaded views; dimensions (length, horizontal, vertical, angle, 3-point angle, radius, diameter, area, extent, chain, coordinate/ordinate, chamfer, arc length, axonometric), tolerances and ISO 286 hole/shaft fits, dimension repair, balloons, leaders, rich text, symbols, weld and surface-finish symbols, center lines and marks, cosmetic geometry, hatching; associative updates; export PDF, SVG, DXF; print. Draft workbench: 2D drafting with layers and layer manager, line styles and colors, annotation style editor, hatching, snaps (endpoint, midpoint, center, intersection, perpendicular, parallel, extension, angle, grid, ortho), working planes, text, labels, dimensions, arrays, DXF/DWG (LibreDWG ≤ R2004 export).

**Known gaps**: listed below; DWG export limited by LibreDWG (≤R2004).

**Target scope**
- Standalone 2D drafting: blocks/symbol library, xrefs, model/paper space with viewports, polar tracking, object snap overrides.
- View types: auxiliary, half section, break-out; exploded views from assemblies placed on drawings.
- Annotation: auto-dimension, model-dimension import, GD&T feature control frames and datums drawn originally (§12 R13), auto-balloon, associative revision, hole, BOM and cut-list tables.
- Dangling annotation detection.
- Drafting standard presets beyond ASME/ISO (DIN, JIS) in an editable style manager.
- Export PNG.

**Exit criteria**: Produce a 3-view + section + detail drawing of the Phase 2 bracket with GD&T; change model; drawing updates; PDF/DXF output opens in third-party viewers.

---

### Phase 4 — Assemblies
**Upstream baseline**: Assembly workbench with OndselSolver: insert components (internal and external files, links), new part in the assembly, sub-assemblies; joints fixed, revolute, cylindrical, slider, ball, distance, angle, parallel, perpendicular, rigid group, gears, gear-belt, belt, rack-pinion, screw, with limits; grounding; DOF display and selection of conflicting, redundant and malformed joints; dragging; exploded views; simulation (driving joints over time); BOM (spreadsheet, CSV export); `.asmt` export. Part link arrays (linear, polar, path, point) for component patterns; shape binders for references across parts.

**Known gaps**: listed below. The Fasteners add-on is GPL-2.0 and cannot be merged; build the parts library with data sourced per §12 R13.

**Target scope**
- Flexible sub-assemblies; skeleton/master-sketch layout parts; external reference management (lock/break).
- Joints: pin-slot, planar, tangent, cam, width/symmetric.
- Mirror components.
- Interference/clearance detection, hole alignment check.
- Exploded views: trail lines, animated explode.
- Motion: contact and collision detection, animation export to video.
- Standard parts library: fasteners (bolts, screws, nuts, washers, pins), bearings; parametric by size.
- Large-assembly mode: lightweight loading, LOD, display simplification.
- BOM: indented view, custom columns, XLSX export.
- Component replacement; collect project (copy a document and all referenced files to a folder or archive).

**Exit criteria**: 500-component assembly loads in <10 s on reference hardware; 4-bar linkage animates; BOM exports correctly.

---

### Phase 5 — Construction & Woodworking Module
**Upstream baseline**: BIM workbench: walls (multi-material), windows, doors, slabs, levels, buildings, sites, spaces (rooms with areas), roofs, stairs, structural members, beams and columns with steel profiles (`Presets/profiles.csv`), rebar, trusses (`Arch_Truss`), frames, fences, panels with thickness and sheet cut layouts (`Arch_Panel`, `Arch_Panel_Sheet`), true-shape nesting (`Arch_Nest`), materials and multi-materials, schedules, reports, quantities, native IFC import/export. TechDraw and Spreadsheet for drawings and tables. The Woodworking add-on (MIT, not in tree) was reviewed and not incorporated (`docs/gaps/phase-5.md`).

**Known gaps**: Primary differentiator. Framing generators, member/joinery model, region-switchable material libraries, 1D/2D cut optimization, framing drawings, build sequences. Delivered as the Construction add-on (developed so far in `addons/construction/` of the fork, §4.5), building on BIM objects so IFC export works.

**Target scope**

**5.1 Material library** (data-driven; see §9)
- Dimensional lumber: US nominal (1x, 2x, 4x, 6x sizes; actual dimensions; stock lengths 8–20 ft) and metric (e.g., 38×89, 45×95, 45×145, etc.; stock lengths 2.4–6.0 m).
- Engineered lumber: LVL, glulam, I-joists (generic profiles, user-extendable).
- Sheet goods: plywood, OSB, MDF, particleboard, drywall, cement board; US 4×8 ft and metric 1220×2440 / 1200×2400 mm; thickness lists.
- Hardwood stock (S4S, rough with board-foot calc).
- Light-gauge steel studs and track (structural steel shapes come from BIM's profiles).
- Masonry/concrete: CMU, brick, concrete (poured volume); rebar is BIM's.
- Roofing, siding, insulation, membranes (area-based materials).
- Hardware: hinges, drawer slides, shelf pins, connectors, joist hangers, anchors, fasteners (generic, user-extendable).
- Per-material: actual dimensions, grain direction, a link to a Material workbench card (density, appearance), cost (user price table), supplier SKU field.
- Region switch per document (US / metric); user libraries and overrides.

**5.2 Structural members**
- "Member" object: extruded profile along a path with material, grain orientation, end cuts (square, miter, bevel, compound, birdsmouth, plumb/seat), notches, holes.
- Sheet parts: edge banding and grain on panels (BIM's `Arch_Panel` provides panels with thickness).

**5.3 Joinery** (parametric, applied between members)
- Butt, miter, lap, half-lap, dado, rabbet, groove, mortise-and-tenon, bridle, dovetail (through, half-blind), box/finger, dowel, biscuit, pocket screw, domino-style loose tenon, scarf.
- Fastener placement rules (spacing, edge distance) with automatic hardware BOM entries.

**5.4 Generators** (parametric, editable after creation, produce members/sheets)
- Wall framing: length, height, stud spacing (16"/24" OC or 400/600 mm), plates (single/double), openings (door/window with header sizing input, king/jack/cripple studs, sills), corners (3-stud, California), T-intersections, blocking rows.
- Floor framing: joists, rim/band, blocking/bridging, beams, posts, openings.
- Roof framing: gable, hip, shed, gambrel; rafters, ridge, collar ties, ceiling joists, overhangs, fascia. Trusses: BIM's `Arch_Truss`.
- Stairs: total rise/run, rise/tread rules (configurable limits), stringers, treads, risers, landings, railings.
- Decks: ledger, joists, beams, posts, footings, decking boards with gap, railings.
- Foundations: slab, strip footing, pier/post footings, block wall; concrete volume.
- Sheathing/cladding layers: auto-cover walls/roofs with sheet goods, show seams, cut openings.
- Cabinets: frameless (32 mm system) and face-frame; base, wall, tall, drawer bank, corner; carcass construction options (dado/rabbet/butt/confirmat), back type, toe kick, doors (slab, shaker/frame-and-panel), drawers (box construction, slide clearance rules), shelves (fixed/adjustable), face frames; run layout along a wall with fillers.
- Furniture primitives: tables, shelving units, workbenches (templates).
- Templates: sheds (gable/lean-to/gambrel), garage, kitchen cabinet run, bookcase, workbench. Building elements (walls, doors, windows, levels, rooms, roofs) and house shells are BIM's.

**5.5 Analysis (advisory)**
- Beam span/deflection checks from mechanics (simply supported, cantilever, continuous) using user-supplied design values; L/360-style limit selectable.
- Rise/run, headroom, guardrail height checks against user-configurable rule sets.
- No embedded copyrighted code tables (§2).
- **Jurisdiction safety rule sets** (decision 2026-10-11; after the other Phase 5 gaps): shipped only from public-domain or openly licensed sources, every value verified against the official text and cited by clause in the warning it raises: UK Approved Document K (stairs, ramps, guarding; Open Government Licence), US OSHA 29 CFR 1910 Subpart D (walking-working surfaces; workplaces), US 16 CFR 1261 (clothing storage unit tip-over; anchoring), US HUD 24 CFR 3280 (manufactured homes: stairs, egress, structural minimums). A per-document rule-set chooser; new checks the sets need (headroom, stair pitch, guard and window-guard rules, egress). Structural capacity still needs user design values and loads (design values and load standards are copyrighted; clear-wood handbook values are not design values). Every check stays advisory and never states code compliance.

**5.6 Outputs**
- BOM / purchase list: groups by material and stock length; quantities, cost total.
- Cut list: per part, with dimensions, angles, grain, edge banding, part labels.
- 1D stock optimization: optimal cuts from stock lengths with kerf, minimize waste/cost.
- 2D sheet layout: rectangular (guillotine) for the panel saw, with grain constraints, kerf, labels. True-shape nesting: BIM's `Arch_Nest`.
- Framing plans/elevations (auto-generated drawing views with member tags).
- Step-by-step build sequence views (assembly order, exploded per step).
- Export: CSV/XLSX, PDF shop drawings, labels (printable).

**5.7 Tutorials**
- Step-by-step tutorials with examples for every generator and output: cabinets and runs, members, wall/floor/roof framing, sheathing, the shed template, libraries, settings and checks (`addons/construction/Tutorials/`).
- Examples that use the standalone modules are runnable and tested (doctest), so documented results stay true.

**Exit criteria**: Generate a 10×12 ft (3×3.6 m) gable shed from template; edit wall height and door width; framing regenerates; BOM, optimized cut list, sheet nesting, and framing drawings produce correct quantities (validated against hand count).

Phase 5 work that repeats FreeCAD features (review 2026-10-12) is rolled back in Phase 5.3.

---

### Phase 5.1 — Woodworking Assemblies & Joinery
**Upstream baseline**: None for woodworking joinery. The Assembly workbench's joints position parts for motion, not joinery. The Woodworking add-on (MIT, not in tree) was reviewed 2026-10-10 and not incorporated: its joints are hand-placed PartDesign pockets inside Qt dialogs, with no joint model to build on (see `docs/gaps/phase-5.md`). Builds on Phase 5 (`addons/construction/`: `Parts.py`, libraries, `Joinery.py`, cut list, drawings, checks) and BIM's IFC export.

**Known gaps**: General woodworking design: free-form boards and panels, user-selected joints and hardware, furniture templates. Phase 5 generators (cabinets, shed) are special-purpose.

**Target scope**
- One part model for all construction and woodworking (boards, panels, members; material, grain, role), shared by every generator.
- **Woodworking assembly** (decision 2026-10-10), named **Build** in the UI so it is not confused with the Assembly workbench: one FreeCAD object holds a parts table and a joints table; the user picks parts by selecting solids inside it. Joints modify both parts (tenon lengthens one, mortise pockets the other) without document dependency cycles. Phase 5 generators (cabinets, shed, framing) produce assemblies; their parts and joints stay editable. IFC export writes a Build as an `IfcElementAssembly` (as Construction objects already carry `IfcType`).
- **Board** (stock from the lumber/hardwood library or custom size; length; placement), **Board between** (span two selected faces with a setback), **Panel** (sheet goods or glued-up panel; size; grain).
- **Joint** command (hotkey `J`): select two parts; the joint types offered follow how they meet (end-to-face, face-to-face, crossing, edge-to-edge, panel-on-frame): mortise and tenon, loose tenon, dowels, pocket screws, screws, biscuits, housing/dado/rabbet, half lap, bridle, glue, tabletop fasteners (figure-8, Z-clip, buttons, slotted screws). Presets from a joint library (sizes relative to stock); hardware chosen from the hardware library; live preview; **Apply to similar** for repeated joints.
- Joint and hardware libraries are data (`source`, `data_license`, user overrides), like Phase 5 libraries.
- Outputs reuse Phase 5: cut list with operations (e.g. mortise sizes) and parts lengthened by joinery, hardware list, sheet/lumber layout, drawings with tags.
- Checks (advisory): tenon wall thickness, fastener edge distances, wood movement of solid tops against the chosen fastening.
- Templates as assemblies: end table first (height, top size, overhang, leg and apron sizes, joinery choice, top attachment, optional shelf), then bookcase, workbench, table; cabinets and the shed migrate onto assemblies.
- Tutorials with tested examples (§5.7 pattern): building an end table from the template and by hand.

**Exit criteria**: Build a 500 × 500 × 600 mm end table by hand (4 legs, 4 aprons, top) with mortise-and-tenon apron joints applied once and repeated with Apply to similar, and figure-8 top fasteners; cut list shows tenon-lengthened aprons and mortise operations, hardware list counts the fasteners; the same table from the template matches.

---

### Phase 5.2 — Construction Usability: Measure, Generate, Iterate
**Upstream baseline**: FreeCAD task panels (`Gui::TaskView`), Draft/Sketcher snapping, `Gui::Selection`, Coin draggers (`SoTransformManip`); inline value entry only in Sketcher (on-view parameters). Builds on Phases 5 and 5.1.

**Known gaps** (review 2026-10-11): generators produce correct outputs, but going from a measured space to a design, and iterating on it, needs typed strings (openings, widths, beams), spreadsheet cells (build parts and joints) and library ids. Templates stop being parametric once created. There is no room or footprint input, and parts cannot be moved in the 3D view.

**Target scope** (in priority order)
1. **Parametric templates**: a template's sizes and choices (height, top size, overhang, stock, joint, top fastening, shelf; bookcase shelves, ...) are properties of the build; changing one regenerates its rows. Rows the user edited by hand are kept as overrides (marked in the table) and survive regeneration.
2. **Task panels with dropdowns**: editing panels for builds (parts list, joints list with joint-type and hardware dropdowns from the library, stock dropdowns), walls (openings as a list: kind, width, height, position, sill), floors (beams, openings) and cabinet runs (per-cabinet width and style, appliance gaps). Selecting a joint (or the two parts it joins) and changing its type is one action.
3. **Room / footprint object**: enter measured walls as a list (length, angle, height) or from a closed sketch, with openings (doors, windows) and obstacles (appliance gaps, pipes). Generates wall framing that meets at the corners, and cabinet runs along chosen walls that turn corners (blind or corner cabinets) and leave gaps for appliances and openings.
4. **Shed template opened up**: doors and windows per wall as a list; roof type gable or mono-pitch; the walls' openings editable like any wall.
5. **Direct manipulation**: drag parts of a build, openings in a wall and cabinets in a run in the 3D view with snapping (faces, edges, grid); the drag writes back to the table or property.

**Exit criteria**: (a) A user measures an L-shaped kitchen (3600 and 2400 mm walls, a window, a 600 mm range gap), enters it in one panel, and gets two cabinet runs meeting at a blind corner with the gap and the cut list, without typing library ids or editing a spreadsheet. (b) The End Table is made 50 mm taller and switched from figure-8 to Z-clip fasteners with two property changes. (c) A window is added to a shed wall from a panel. (d) A board in a build is dragged to a new position and snaps to a face.

---

### Phase 5.3 — Roll Back Overlap with FreeCAD
**Upstream baseline**: BIM workbench objects checked against the source 2026-10-12: `Arch_Structure` / `BIM_Beam` / `Arch_Frame`, `Arch_Stairs`, `Arch_Panel` / `Arch_Panel_Sheet` / `Arch_Nest`, `Arch_Covering`, `Arch_Fence`, `BIM_Slab`, `Arch_Schedule`, `BIM_IfcQuantities`; Assembly exploded views; Material workbench cards; Help module.

**Known gaps**: Phases 5–5.2 implemented some features in the Construction workbench that FreeCAD already provides (before the reuse rule). Under the reuse rule, that code is removed and the Construction add-on builds on the FreeCAD feature, keeping only what FreeCAD lacks. Do this before migrating the workbench into the Construction add-on (§4.5), and before the remaining Phase 5 gaps.

**Target scope** (in order; each row: remove the code, use the FreeCAD feature, re-add only the construction-specific part on top of it)

| # | Roll back (Construction code) | Replace with (FreeCAD) | Keep, on top of the FreeCAD object |
|---|---|---|---|
| 1 | `MemberFeature`, `make_member` and the member geometry in `Member.py` (sweep of a section along an edge or two points, roll) | `Arch_Structure` / `BIM_Beam` on the edge or sketch, with the section from a BIM profile; `Arch_Frame` for members along every edge of a wire | Lumber library sizes as profiles, angled end cuts (`StartCut`, `EndCut`) as properties added to the structure, grain, cut-list rows and checks read from the structure |
| 2 | `Framing.Stair`, `Framing.LandingStair` geometry (risers, treads, stringers, landing, handrails) and `StairFeature` | `Arch_Stairs` (risers, tread depth, nosing, stringers, landings, winders, railings, Blondel ratio) | Read an `Arch_Stairs`: treads cut from whole boards, cut-stringer layout and count, balusters and guard counts, advisory stair checks, cut-list parts |
| 3 | Slab geometry (`Framing.Slab.boxes`, `SlabFeature` solids) and its volume | `BIM_Slab` for the slab; volumes from the shape or `BIM_IfcQuantities` | Thickened edge (an addition to the slab), concrete in the cut list, the foundation check; the garage template creates a BIM slab |
| 4 | The flat layout drawing of sheets (`SheetLayout`, `SheetLayoutView` written by `_write_sheet_layouts`) | `Arch_Panel_Sheet` objects holding the placed panels (tags, grain, sheet outline), drawable with TechDraw; `Arch_Nest` for true-shape nesting | The guillotine packer `CutList.layout_sheets` (FreeCAD's nesters do not keep cuts edge to edge for a panel saw), kerf and trim |
| 5 | Deck guard posts, rails and balusters as Construction members (`Framing.Deck._guards`) | `Arch_Fence` along the deck's open sides (posts and sections on a path) | Guard height and baluster gap from the rule set, posts bolted through the framing, the guard checks and hardware |
| 6 | Concrete and covering totals computed in the cut list for BIM-backed objects | `BIM_IfcQuantities` / shape volume and area of the BIM objects | Cut list grouping by size, lumber buying plan, costs |
| 7 | Material data duplicated in library items (density, appearance) | Material workbench cards linked from each library item | Section sizes, stock lengths, prices, region |
| 8 | `show_tutorials` (Markdown in a `QTextBrowser` tab) | `Help.show` of FreeCAD's Help module (official FreeCAD builds include Qt WebEngine) | A fallback to the text browser only when `Help.get_qtwebwidgets()` is false |

Not rolled back (no FreeCAD equivalent, or FreeCAD's is a different job): Sheathing (structural panels with joints on the framing; finishes and siding courses use `Arch_Covering`), build sequence pages (Builds are not Assembly objects; revisit if Builds become Assembly-compatible), joinery and Builds, wall/floor/roof/deck framing, cabinets, fastening and hardware, lumber plan, checks, templates, region switch, library editor. `Arch_Roof` has no rafters; `Arch_Truss` is not reimplemented; drawings and IFC export already use TechDraw and BIM.

**Exit criteria**: Each rolled-back object is created from the FreeCAD object (an `Arch_Structure`, `Arch_Stairs`, `BIM_Slab`, `Arch_Fence`, `Arch_Panel_Sheet`); the shed and garage templates, cut list, hardware list, checks and tutorials give the same quantities as before the rollback (snapshot tests); IFC export writes them as FreeCAD's BIM types; the removed code is gone from the Construction workbench.

---

### Phase 6 — Direct, Surface, Mesh & Freeform Modeling
**Upstream baseline**: Part: extrude, revolve, loft, sweep, ruled surface, offset (3D and 2D), thickness, make face/solid, shape builder, section and cross-sections, projection on surface, curve networks, helix and spiral primitives, defeaturing, refine. Surface workbench: filling (G0/G1/G2 boundary patches), sections, curve-network surfaces, extend face, blend curve, curve on mesh, cut. Mesh/MeshPart: import, evaluate and repair (fill holes, normals, components, self-intersections), decimate, remesh (Gmsh), smoothing, booleans (union, intersection, difference), cut/trim/split, cross-sections, segmentation, curvature, flatten; mesh to shape (faceted; BIM `Arch_MeshToShape` for planar). Reverse Engineering: approximate plane, cylinder, sphere, B-spline surface from points or meshes. Inspection: deviation of shapes and meshes from a reference. Draft workbench: 3D wires and B-splines.

**Known gaps**: listed below.

**Target scope**
- Direct editing (history-free or as features in history): face drag/offset (inference-driven "draw and pull" workflow for quick massing), move/rotate face, replace face, delete face (heal), resize fillet, make faces coplanar/concentric. Direct edits act only on faces the user selects; geometric relationships are kept only when the user explicitly selects or defines them. No automatic detection/maintenance of face relationships during edits (§12 R2).
- Quick-modeling mode: draw shapes on faces, pull regions into solids, inference snapping (on-axis, parallel, perpendicular, on-face), groups/components with instance editing, tape-measure guides, follow-path.
- Surfaces: untrim; isocurves.
- Freeform: subdivision-surface modeling (Catmull–Clark cage), edit vertices/edges/faces, crease, insert edge loop, bridge, symmetry, convert to B-rep. No T-junction local refinement; conversion methods restricted per §12 R4.
- Mesh: section to sketch; mesh to prismatic B-rep (fitted planes and cylinders joined into a solid).
- Analysis: curvature combs on surfaces, zebra, draft.

**Exit criteria**: Model a shell-style enclosure with G2 blend surfaces; convert a subdivision model to a valid closed solid; repair an STL and convert to solid.

---

### Phase 7 — Sheet Metal, Structural Frames, Molds, Advanced Parts
**Upstream baseline**: Not in tree: the SheetMetal add-on (LGPL-2.1 per its release notes; verify LICENSE before merging) provides flanges, bends, unfold to DXF/SVG, K-factor tables. In tree: BIM structure, beams and columns along sketch paths with standard and custom profiles (`Arch_Structure`, `BIM_Beam`, `Arch_StructuresFromSelection`, `Arch_Frame`); App links, PartDesign sub-shape binders and clones (derived/linked parts); Part mirror.

**Known gaps**: listed below.

**Target scope**
- Sheet metal: merge or depend on the SheetMetal add-on after the license check; then fill its gaps against: base flange/tab, edge, miter and contour flanges, hem, jog, sketched and lofted bends, corner relief/closures, forming tools, unfold/refold, flat pattern with bend table/K-factor/bend deduction and DXF export, bend lines on drawings, convert solid to sheet metal.
- Structural frames: trim/extend between members, end caps, gussets, cut list with lengths and angles, weld beads (cosmetic).
- Mold tools: parting line, parting surface, shut-off surfaces, core/cavity split, draft and undercut analysis.
- Multi-body to assembly; library features (reusable parametric feature sets with insertion references).

**Exit criteria**: Sheet-metal enclosure flattens with correct flat length per K-factor; frame cut list matches geometry.

---

### Phase 8 — Data Management, Interop, Automation
**Upstream baseline**: Import/export: STEP (with colors, STEPZ), IGES, BREP, STL, OBJ, PLY, OFF, AMF, 3MF, glTF, COLLADA .dae, 3DS (import), DXF and DWG (LibreDWG), SVG, IFC and IFC-JSON (IfcOpenShell), OpenSCAD, JT (import), point clouds, CSV and XLSX (spreadsheet import); PDF and SVG from TechDraw. Python API over every command, macro recorder, FeaturePython (script-defined parametric features), headless `FreeCADCmd`, C++ and Python module system, Addon Manager.

**Known gaps**: listed below. Version history, vault and batch commands as an add-on; exporters and Addon Manager changes as upstream PRs.

**Target scope**
- Local version history per file (snapshots, diff of parameters/feature tree, restore); branching/merge of feature trees for single-user workflows.
- Project vault: file references, where-used, rename/move with reference repair, revision states (WIP/released), part numbering schemes.
- Export: STEP AP242 with PMI where feasible, FBX (via Assimp), XLSX for BOM and parameters.
- Headless batch commands for conversion and BOM generation.
- Plugin installs from local files/folders only, sandboxed plugin permissions.

**Exit criteria**: Round-trip STEP preserves solids and colors; IFC export of shed opens in a BIM viewer; macro replays recorded session.

---

### Phase 9 — Visualization & Rendering
**Upstream baseline**: Material workbench and appearance system (1.0) with appearance and pattern material cards; texture mapping of an image onto the view (`Std_TextureMapping`); clipping planes; no built-in photoreal renderer.

**Known gaps**: listed below.

**Target scope**
- Real-time viewport upgrades: PBR materials, environment lighting (HDRI), shadows, ambient occlusion, section caps, ground plane/reflections.
- Appearance library (all textures and HDRIs CC0 or original, §12 R15) (woods with grain mapping aligned to member grain direction, metals, plastics, glass, paint, concrete), decals, per-object texture mapping (planar/box/cylindrical/UV).
- Photoreal render: Cycles/OSPRay backend; CPU + GPU; progressive and final; denoising; cameras (DOF, FOV), lighting (sun position by location/date/time, area/point/spot), turntable and walkthrough animation, render queue.
- Output: PNG/EXR images, MP4 video.

**Exit criteria**: Render a cabinet run at 1920×1080 with HDRI lighting and wood grain aligned to part grain.

---

### Phase 10 — Simulation (FEA) & Advanced Motion
**Upstream baseline**: FEM workbench: analysis container; solvers CalculiX, Elmer, Mystran, Z88 (external), solver control and run; materials (solid, fluid, reinforced, nonlinear mechanical; isotropic); constraints fixed, displacement, plane rotation, contact, tie, spring, rigid body, transform; loads force, pressure, self weight, centrifugal, bearing, gear, pulley, heat flux, temperature, body heat source and electromagnetic loads; beam and shell elements (1D/2D section geometry); meshing with Netgen and Gmsh (regions, boundary layers, groups, transfinite); CalculiX analysis types static, frequency, buckling, thermomechanical, electromagnetic, with geometric nonlinearity; post-processing pipelines with von Mises, principal stress, displacement and strain, clip, cut, contours, warp (deformed shape), glyphs, data along a line and at a point (probes), section print (reaction forces), linearized stresses.

**Known gaps**: listed below.

**Target scope**
- Study manager; orthotropic wood material presets; torque and remote loads; bolt and pin connectors; mesh quality report.
- Analysis types: drop/impact (later), fatigue (later).
- Fast 1D beam/frame solver for structural members, used by Phase 5 for framing checks.
- Job queue with progress and cancel.
- Factor of safety results, deformed-shape animation, reports (PDF/HTML).
- Rigid-body dynamics with forces, springs, dampers and gravity; reaction forces handed to FEA as loads.

**Exit criteria**: Cantilever beam results within 2% of analytic deflection/stress; modal frequencies of a plate within 3% of reference.

---

### Phase 11 — CAM
**Upstream baseline**: CAM workbench: jobs with stock, work coordinate systems and fixtures; tool bits and tool libraries with import/export (1.1), tool controllers; operations facing, profile, pocket, adaptive (inherited, enabled; §12 R3), slot, drilling (peck), tapping, helix (bore), thread milling, deburr (chamfer), engrave, V-carve, 3D surface and waterline (OpenCAMLib); dressups tags, ramp entry, lead-in/out, dogbone, boundary, Z-correct, axis map, drag knife; simulators (stock removal), CAMotics bridge, inspect (G-code viewer), sanity check; Python post-processors for Grbl, LinuxCNC, Fanuc, Mach3/4, Heidenhain, Centroid, Marlin, OpenSBP and more, including a generic sheet-cutting post. True-shape nesting: BIM `Arch_Nest`.

**Known gaps**: listed below.

**Target scope**
- Setups: lathe and laser/plasma/waterjet machine types; 3+2 and 4/5-axis later.
- Feeds/speeds calculator by material.
- 2D: offset clearing with corner arc smoothing and feed reduction (constant-engagement clearing only after §12 R3 clearance).
- 3D toolpaths: offset roughing, scallop, pencil, spiral, radial, rest machining.
- Lathe: facing, turning, grooving, threading, parting.
- Cutting (laser/plasma/waterjet): kerf compensation, pierce points, lead-ins, common-line cutting.
- Nesting: part labels and remnant tracking on top of `Arch_Nest`.
- Construction integration: auto-generate CNC toolpaths for cabinet parts (shelf-pin holes, dadoes, profile cuts) from Phase 5 parts.
- Simulation: gouge and collision detection (tool, holder), cycle-time estimate.
- Post-processor naming: label vendor dialects "Fanuc-compatible", "Haas-compatible", "Mach3/4-compatible" (nominative use only, §12 R16); add a Haas-compatible post.
- Setup sheets (PDF/HTML).

**Exit criteria**: Cabinet side panel → nested sheet → toolpaths → G-code; simulation shows no gouges; G-code runs in a reference simulator (e.g., CAMotics) matching geometry.

---

### Phase 12 — Generative Design / Topology Optimization
**Upstream baseline (verify in audit)**: None built in. External `beso` add-on (LGPL-3.0, BESO + CalculiX) is reference only.

**Known gaps**: Entire phase, as a Generative add-on.

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

## 6. Cross-Cutting UI Requirements (core hooks proposed upstream and UX add-on in Phase 0; applied to every add-on in later phases)

- Workspaces: Design, Sketch, Drafting, Drawing, Assembly, Construction, Render, Simulate, Manufacture, Generative, Electronics. Map onto upstream workbenches; each shows only relevant toolbars.
- Contextual heads-up panel: when a command runs, a compact input panel appears near the cursor with fields, options, and current context hotkeys.
- Radial menu on right-drag: 8 context-dependent commands, user-configurable.
- Inline value entry: typing a number during any drag/draw sets the active dimension.
- Live preview for every feature before commit.
- Model browser (upstream tree view has search, hide/show and error icons): isolate, color by status (OK/warning/error).
- Error panel listing rebuild errors with "go to feature" and suggested repair.
- Measurement always available (no command interruption).
- Accessibility: full keyboard navigation, scalable UI (100–300%), high-contrast theme, screen-reader labels on panels.
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

- Location: `Resources/libraries/{region}/*.json` in the Construction add-on + user overrides in FreeCAD's user data folder.
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
  "material_card": "<UUID of a Material workbench card: density, appearance>",
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

- Add-on tests run in stock FreeCAD (stable and development) on every change; upstream PRs carry tests in FreeCAD's suites (C++ gtest, Python `TestApp`) and pass its CI.
- Unit tests per new module; tolerance assertions for geometry.
- Golden-model regression suite: reference `.FCStd` files rebuilt each CI run; compare volume, area, topology counts, and bounding box.
- Topological-naming stress tests (FreeCAD's implementation): scripted edits on 50+ models, assert add-on references resolve; failures reported upstream.
- Constraint solver fuzz tests (contributed upstream with Phase 1 PRs).
- Construction module: BOM/cut-list snapshot tests for each template.
- Simulation/CAM: analytic benchmark comparisons (exit criteria values).
- Viewport image-diff tests.
- File format migration tests for every schema version.
- Performance benchmarks tracked in CI (§7).
- Network-isolation test (Phase 0) on every CI run.

---

## 11. Open Questions

1. **Add-on names** — required before first public release; trademark search per §12 R17.
2. **Upstream acceptance** — what to do when FreeCAD declines a PR this plan depends on (e.g., the hotkey-context hooks): keep the feature out, or find an add-on design that needs no core change. Shipping a patched FreeCAD is not an option.
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
| R1 | Clickable cube orientation widget (upstream NaviCube; Phase 0) | Autodesk: US 7,782,319 (filed Mar 2007, cube orientation indicator/controller) and continuation US 9,043,707 (listed active) | FreeCAD ships a clickable NaviCube (`src/Gui/NaviCube.cpp`); it is FreeCAD's, not distributed by this project. Add-on code must not add cube-widget functionality. |
| R2 | Direct editing with automatic face-relationship detection (Phase 6) | Siemens (Synchronous Technology / "Live Rules", patent filings from 2008) | Edits apply only to user-selected faces. Relationships maintained only when explicitly user-defined. No automatic relationship-inference engine. FTO before adding any. |
| R3 | Constant-engagement / adaptive clearing toolpaths (Phase 11) | Celeritive (VoluMill; EP 2 681 683 B1 granted 2020), and other CAM vendors | FreeCAD ships CAM "Adaptive" (constant-engagement clearing); it is FreeCAD's, not distributed by this project. Add-ons and contributions add no new constant-engagement algorithms without FTO clearance. |
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
| R17 | Product name, logo | FreeCAD Project Association (FreeCAD logo registered in Benelux; claims rights over commercial use of name and logo); other mark holders | Own add-on names (§2). Trademark clearance (USPTO, EUIPO, WIPO) for them. Use "FreeCAD" only factually ("an add-on for FreeCAD"), no logo. |
| R21 | Feature names | Vendors | Reserved-term list (do not use as feature/command names): Push/Pull, Press Pull, Follow Me, Hole Wizard, Pack and Go, Rollback Bar, Smart Dimension, SmartMates, Design Table, Configurations (as a feature name), Toolbox, Weldments, FeatureManager, ViewCube, Adaptive Clearing, Dynamic Milling, VoluMill, T-Splines, Live Rules, Synchronous. CI check greps add-on UI strings for these terms; FreeCAD's own strings are FreeCAD's. |

### 12.3a Add-on and contribution risks

| ID | Area | Basis | Required mitigation |
|---|---|---|---|
| R22 | Dependence on FreeCAD features | Add-ons call FreeCAD features this project does not control or review | An add-on that builds on a FreeCAD feature named in R1–R21 does not extend the exposed technique. FreeCAD's own features are FreeCAD's responsibility; this project no longer flags or ships them. |
| R23 | License mixing | LGPL-2.1-or-later add-ons with Apache-2.0, LGPL-3.0, GPL components | Follow §1 linkage rules; CI dependency-license check; GPL programs only as external executables; no GPL-only source copied in. Upstream PRs use FreeCAD's license. |

### 12.4 Process requirements

1. FTO opinion from patent counsel before 1.0, covering R1–R10 and any later feature that implements a named technique from a commercial product.
2. `docs/prior-art/`: for each algorithm with patent exposure, publication references with dates and the source the implementation follows.
3. `docs/patent-watch.md`: tracked patents, expected expiry, status; review quarterly.
4. Every add-on feature with patent exposure can be switched off (preference or separate module) so it can be removed in a patch release if a claim is made.
5. Defensive publication: publish design notes for original techniques (hotkey context engine, construction generators) to establish prior art.
6. `LEGAL.md`: claim/takedown contact address, feature-disable steps, release process.

---

## 13. Rules for Implementation Agents (Claude Code)

1. Read this document, `SURVEY.md`, and the phase's `docs/gaps/phase-N.md` before writing code.
2. Run the §5.0 audit before implementing a phase. Do not reimplement Present items. Before writing any feature, check the source tree for an existing upstream implementation and follow the reuse rule (top of this document): build on what exists, and write down why when you cannot.
3. Place code per §4.2: in an add-on, without modifying FreeCAD's code. Change FreeCAD only when an add-on cannot provide the functionality or is measurably too slow; record why in the gap document, keep the change to the minimal hook, and submit it upstream.
4. Do not copy code from GPL-only projects, commercial software, or unlicensed sources. Cite prior art for algorithms with patent exposure in `docs/prior-art/` (§12.4).
5. No network access in add-on code (§1). Never patch, disable or replace FreeCAD features from an add-on. No new dependency without the license check (§3.2).
6. Every shipped data entry has `source` and `data_license` (§9).
7. Each command defines its hotkey context layer (§8.4).
8. Add tests for every new feature and run them in stock FreeCAD; upstream PRs pass FreeCAD's CI; meet phase exit criteria before moving on.
9. Keep §14 (summary of additions) current: every feature added, and whether it is an add-on or a FreeCAD change.

---

## 14. Summary of Additions

What this project has added so far (as of 2026-10-12), and how. All of it was built inside this repository's FreeCAD fork; the **Delivery** column says whether it is an add-on (no change to FreeCAD's code) or a change to FreeCAD's code, and **Plan** what happens to it under the add-on strategy (§4.5). Update this table with every addition (§13 rule 9).

### Changes to FreeCAD's code

| Addition | Where (fork) | Delivery | Plan |
|---|---|---|---|
| Context-layered hotkeys: engine, tool and task-dialog context, context layers ahead of Qt shortcuts (Phase 0) | `src/Gui/Hotkeys/`; hooks in `Command.cpp`, `Control.cpp`, `ToolHandler.cpp/.h`, `ShortcutManager.cpp`, `MainWindow.cpp`, `CommandStd.cpp`, `Workbench.cpp`; `tests/src/Gui/Hotkeys/` | FreeCAD change | UX add-on for workspace and task-dialog contexts; per-tool context needs a FreeCAD hook (no Python signal when a tool handler starts or ends): minimal upstream PR |
| Command palette, radial menu, heads-up hotkey strip (Phase 0) | `src/Gui/Hotkeys/HotkeyCommands.cpp`, `MainWindow.cpp` | FreeCAD change | UX add-on (Qt from Python); no FreeCAD change needed. Done in `addons/ux/`: palette, workspace/global hotkey layers, strip, suggestions, remapping dialog, radial menu (by command) |
| Rebranding: product name, app id, maintainer URL | `src/Main/Main*.cpp`, `branding/`, `cMake/CADApp/`, top `CMakeLists.txt` | FreeCAD change | Retired |
| Feature flags for FreeCAD features with risk exposure: NaviCube (R1), CAM Adaptive (R3) | `src/App/Fork/`, `App/Application.cpp`, `src/Ext/freecad/fork_features.py`, `Gui/View3DInventorViewer.cpp`, `Mod/CAM/InitGui.py`, `Mod/CAM/Path/GuiInit.py` | FreeCAD change | Retired: FreeCAD's features are FreeCAD's (§12 R22) |
| Network features behind runtime flags: downloads, BIM library, tutorial and SHP downloads, online Help, MTConnect import | `Gui/DownloadManager.cpp`, `Mod/BIM/ArchCommands.py`, `bimcommands/BimLibrary.py`, `bimcommands/BimTutorial.py`, `importers/importSHP.py`, `Mod/Help/Help.py`, `Mod/CAM/Machine/ui/mtconnect_import_dialog.py`; `docs/inherited-conflicts.md` | FreeCAD change | Retired |
| Construction workbench in the build | `src/Mod/CMakeLists.txt` (`BUILD_CONSTRUCTION`) | FreeCAD change | Retired: installed as an add-on instead |
| Fork CI checks (network APIs, reserved terms, data licences, SPDX headers, dependencies) | `tools/fork/`, `.github/workflows/fork_checks.yml` | Repository tooling | Kept as add-on CI checks |

### Add-ons (no change to FreeCAD's code)

The Construction workbench (Phases 5–5.2) uses only FreeCAD's public Python API and none of the changes above. It now lives in `addons/construction/` (moved 2026-10-13, after the Phase 5.3 rollback, `docs/gaps/phase-5.3.md`).

| Addition | Phase | Delivery | Plan |
|---|---|---|---|
| Material, hardware, joint, area-material, rule-set and fastening-schedule libraries (JSON with source and licence), user overrides, region per document, library editor with CSV import/export | 5 | Add-on | Construction add-on; link items to Material cards (5.3 #7) |
| Cabinets (frameless base, wall, tall, sink, blind corner; carcass joints, drawers, shelves, edge banding, shaker doors) and cabinet runs with fillers and appliance gaps | 5 | Add-on | Construction add-on |
| Member (lumber along an edge, roll, end cuts) | 5 | Add-on | Done: `Arch_Structure` subclass (5.3 #1) |
| Wall, floor, gable roof, mono-pitch roof and deck framing; corner studs, openings, blocking, beams on posts | 5 | Add-on | Construction add-on (deck guards onto `Arch_Fence`, 5.3 #5) |
| Stairs (straight and with landing, guards) | 5 | Add-on | Done: reads an `Arch_Stairs` (5.3 #2) |
| Slab and strip footing; garage template on a slab | 5 | Add-on | Done: BIM slab plus thickened edge (5.3 #3) |
| Sheathing with joints on the framing; coverings (roofing, wrap, siding, insulation) by area | 5 | Add-on | Construction add-on |
| Shed template (per-wall openings, gable or mono-pitch roof, floor or slab) | 5, 5.2 | Add-on | Construction add-on |
| Joinery (housing, mortise and tenon, loose tenon, half lap, bridle, box joint, dovetail, miter, dowels, screws, holes) and fastening schedules with hardware counts | 5, 5.1 | Add-on | Construction add-on |
| Builds: Board, Board Between, Panel, Joint (J), Align, Move Part (drag with snapping), Edit panels; templates end table, dining table, workbench, bookcase (parametric, keeping hand edits) | 5.1, 5.2 | Add-on | Construction add-on |
| Room: measured walls, openings and appliance gaps to wall framing and cabinet runs meeting at corners | 5.2 | Add-on | Construction add-on |
| Cut list with operations and costs, lumber buying plan, panel-saw sheet layout, hardware list, part labels, CSV export | 5 | Add-on | Construction add-on; sheet layouts as `Arch_Panel_Sheet` (5.3 #4) |
| Drawings (TechDraw pages at standard scales, dimensions, section, member tags), build sequence pages | 5 | Add-on | Construction add-on (uses TechDraw) |
| Advisory checks (beams, joists, rafters, headers, stairs, guards, cabinets and furniture anchoring, joinery, wood movement, foundation) with the disclaimer | 5, 5.1 | Add-on | Construction add-on; jurisdiction rule sets next (5.5) |
| IFC types on construction objects (exported by BIM) | 5 | Add-on | Construction add-on |
| Tutorials (tested examples) and the Tutorials command | 5.7 | Add-on | Construction add-on; use `Help.show` (5.3 #8) |

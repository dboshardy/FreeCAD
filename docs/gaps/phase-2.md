# Phase 2 gap audit: Parametric Part Modeling

Audit per DESIGN.md §5.0. Source searched: `src/Mod/{PartDesign,Part,Spreadsheet,Inspection,Measure,Material}`
and `src/Gui` (Tree, Command). Status: Present / Partial / Missing.
"Add-on" = Python add-on in `addons/bodytools/`. "FreeCAD change" = C++ needed.

| # | Target item | Status | Evidence in source | Route | Reason |
|---|-------------|--------|--------------------|-------|--------|
| 2.1 | Horizontal timeline, draggable history marker, reorder dependency check | Missing | No timeline/rollback code outside `Measure/Gui/TaskMassProperties.cpp` (unrelated). Tree has `Tip`/`Body.Tip` only (`PartDesign/App/Body.cpp`) | Add-on (dock widget over `Body.Group`/`Body.Tip`) | `Body.Tip` and `Body.Group` are scriptable. Dependency check uses `OutList`/`InList`. Reserved term: do not call it "Rollback Bar" (R21). Name: "History Strip". |
| 2.2 | Thin-wall extrude | Missing | `FeatureExtrude.h` has `SideType` (One side/Two sides/Symmetric) and no wall thickness | Add-on (Python feature building a shell from the profile) | Not possible as a property of the stock Pad without C++. A Python `PartDesign::FeaturePython` can do it. |
| 2.3 | Rib / web | Missing | No rib feature in `PartDesign/App` | Add-on | Same mechanism: extrude an open profile by thickness, then extend to the body. |
| 2.4 | Fillet variants (variable radius, face, full-round, setback) | Missing | `FeatureFillet.h` has one `Radius`, `UseAllEdges`. Chamfer has `ChamferType` only | Add-on for variable radius and face fillet via OCC `BRepFilletAPI_MakeFillet` through `Shape.makeFillet(r1, r2, edges)`. Full-round and setback: **FreeCAD change, not done** | `makeFillet` takes start and end radii per call, so variable radius works. Full-round and setback need OCC calls that are not exposed to Python. |
| 2.5 | Emboss / deboss | Missing | No hit | Add-on (extrude a sketch along a face normal, fuse or cut) | Plain Pad/Pocket on a face already does a flat emboss. The add-on adds the draft-angle and face-offset options. |
| 2.6 | Wrap | Missing | No wrap of a profile onto a curved face | **FreeCAD change, not done** | Needs projection of a planar wire onto a cylinder/cone surface with an offset. Python wire-to-surface mapping is not robust enough; no OCC helper is exposed. |
| 2.7 | Fill pattern | Missing | `Feature{Linear,Polar,Path,Point}Pattern`, `Mirrored`, `Scaled`, `MultiTransform` exist. No fill pattern | Add-on (compute positions inside a boundary face, feed `PointPattern`-style placements) | Pure geometry. |
| 2.8 | Patterns of bodies inside PartDesign | Partial | `FeatureTransformed.cpp` transforms features of one body only | Add-on (`Part::FeaturePython` array of body Shapes) | Stock FreeCAD can pattern with Draft arrays, but not inside a Body. |
| 2.9 | Parameters linked to an external JSON file | Missing | `json` only inside `FeatureHole.cpp` for the hole table | Add-on (loads JSON into a Spreadsheet's aliases; user reload action, no network) | Spreadsheet aliases are the stock parameter store. |
| 2.10 | Variants (per-variant values, suppression, properties, tabular editor) | Partial | `Spreadsheet` has "configuration table" setup (`DlgSheetConf.cpp`): one row selected via cell `ConfigurationTable`. Covers values only. Suppression through `Suppressed` property exists in the base feature | Add-on (variant table on top of Spreadsheet, plus a Qt table editor) | The upstream table drives values. The add-on adds suppression and arbitrary properties. Reserved terms "Configurations" and "Design Table" are not used. Name: "Variants". |
| 2.11 | Draft analysis | Missing | `FeatureDraft.h` makes a draft, it does not analyse one | Add-on (face normals against a pull direction, colour faces) | Pure geometry. |
| 2.12 | Curvature / zebra analysis | Missing | Curvature accessors only in geometry (`Geometry.cpp`, `BSplineSurfacePyImp.cpp`) | Add-on for the curvature part (per-face min/max sampled via `Surface.curvature`). Zebra shading: **FreeCAD change, not done** | Zebra needs an environment-mapped shader in the 3D view. |
| 2.13 | Interference check | Partial | `Part_CheckGeometry` (`TaskCheckGeometry.cpp`) checks one shape's validity. `Part_Boolean` common gives overlaps by hand | Add-on (pairwise `common`, report volume) | Pure geometry. |
| 2.14 | Wall-thickness check | Missing | Only the Thickness feature (`TaskThicknessParameters.cpp`) | Add-on (sample points on faces, ray-cast inward with `Shape.distToShape` against the opposite faces) | Approximate, with a stated sampling tolerance. |
| 2.15 | Hole/thread table provenance (R13) | Present, unverified | Hole data is in `FeatureHole.cpp`; the source of each table is not recorded in code | Doc only | Record the standards used. Not changed in Phase 2. |

## Upstream baseline confirmed present

PartDesign: Body, datums, Pad/Pocket, Revolution/Groove, Loft, Pipe, Helix, primitives, Hole,
Fillet/Chamfer/Draft/Thickness/Boolean, Linear/Polar/Mirrored/Scaled/Path/Point patterns,
MultiTransform, Tip, Suppressed. Spreadsheet with aliases and expressions. Material.
Part Check Geometry, Section Cut, Offset. Measure.

## Plan for this phase

Implemented as the `addons/bodytools/` add-on, in this order, each with tests:

1. `Parameters` : JSON-to-Spreadsheet link (2.9) and Variants table (2.10).
2. `Features` : thin-wall extrude (2.2), rib (2.3), variable-radius fillet (2.4), fill pattern (2.7).
3. `Inspect` : draft analysis (2.11), curvature (2.12), interference (2.13), wall thickness (2.14).
4. `History` : the strip with dependency check (2.1).
5. Exit-criteria test: a 30-feature bracket driven by 5 parameters, rebuild, reorder, suppress, mass
   properties against analytic values within 1e-6 relative.

## Not done in this phase (FreeCAD change needed)

- Full-round and setback fillet (2.4): OCC calls not exposed.
- Wrap (2.6): no robust projection helper.
- Zebra shading (2.12): needs a view shader.
- Emboss draft/offset options beyond what Pad on a face gives are kept simple (2.5).

## Status after implementation

Add-on: `addons/bodytools/`. Tests: `TestBodyTools` (21, headless), `TestBodyToolsGui` (6). All pass on stock FreeCAD 26.3.

| Item | Result |
|------|--------|
| 2.1 History strip | Done: `History.py` (move with dependency check, marker), `Strip.py` (horizontal list, click = marker, drag = reorder). The BaseFeature chain is ignored in the check because PartDesign relinks it. A cut or dress-up cannot be moved before the first solid. |
| 2.2 Thin-wall | Done (`Features.ThinWall`): open and closed profiles, symmetric option. |
| 2.3 Rib | Done (`Features.Rib`): open profile, symmetric extrusion, fused to a base shape. Does not extend the rib to the body walls on its own; the length is a number. |
| 2.4 Variable fillet | Done (`Features.VariableFillet`). Full-round, setback, face fillet: not done. |
| 2.5 Emboss | Not done: Pad/Pocket on a face covers the flat case. |
| 2.7 Fill pattern | Function done (`fill_points`, `fill_pattern_shape`); no feature object or command yet. |
| 2.8 Body patterns | Not done. |
| 2.9 JSON parameters | Done (`Parameters.load_json`, command "Parameters from JSON"). Local file only. |
| 2.10 Variants | Done (`Parameters.VariantTable`, `VariantDialog`): values, suppression, properties. |
| 2.11 Draft | Done (`Inspect.draft_analysis`, report command; no face colouring). |
| 2.12 Curvature | Done as numbers (`Inspect.curvature`); no command. Zebra: not done. |
| 2.13 Interference | Done (`Inspect.interference`, command). |
| 2.14 Wall thickness | Done (`Inspect.wall_thickness`, command), sampled, not exhaustive. |
| 2.6 Wrap, full-round/setback, zebra | FreeCAD change needed, not done. |

Features 2.2, 2.3 and 2.4 are plain Part features, not PartDesign features: they cannot sit inside a Body's feature chain.

### Exit criteria

`TestExitCriteria` builds a 30-feature bracket (15 sketches, 15 PartDesign features) in a Body, driven by 5 spreadsheet parameters
(`plate_l`, `plate_w`, `plate_t`, `hole_r`, `boss_h`). Tested: each parameter changed alone and two together, with all objects valid and the
volume equal to the closed-form value within 1e-6 relative; suppress and unsuppress a hole; move two pads and their sketches before the holes;
the marker at a middle feature; two variants. Mass is checked as volume times density, not through the Measure tool.

Parameter names such as `L`, `W`, `T`, `R`, `H` are unit tokens in FreeCAD and are rejected as aliases.

# Phase 3 gap audit: 2D Drafting and Engineering Drawings

Audit per DESIGN.md §5.0. Source searched: `src/Mod/TechDraw`, `src/Mod/Draft`, `src/Mod/Import`.
Status: Present / Partial / Missing. "Add-on" = Python add-on (proposed `addons/drawing/`).
"FreeCAD change" = change to FreeCAD source (C++ or its own Python) needed.

| # | Target item | Status | Evidence in source | Route | Reason |
|---|-------------|--------|--------------------|-------|--------|
| 3.1 | Blocks / symbol library | Partial | `Draft/draftobjects/block.py` is a plain compound, not a reusable library. TechDraw has `DrawViewSymbol` (SVG) and `Resources/symbols` | Add-on: a library of original SVG symbols placed with `DrawViewSymbol`, plus a Draft block reference | No stock library exists. Symbols must be drawn originally (R13). |
| 3.2 | External references (xrefs) | Missing | Only DXF import mentions xref (`Import/App/dxf`) | Add-on over `App::Link` to a file | Stock links to other documents work; the add-on adds a manager (list, lock, break, reload). Lock/break also serves Phase 4. |
| 3.3 | Model / paper space with viewports | Partial | TechDraw page = paper space, views = viewports (`DrawViewPart`, `DrawViewDraft`). Draft has one model space and no sheet | Add-on: sheet helper that places Draft objects on a TechDraw page through `DrawViewDraft` | Reuses upstream views. No new viewport type. |
| 3.4 | Polar tracking | Missing | Snapper has `angle` and `ortho` (`Draft/draftguitools/gui_snapper.py` ~l.164–172), no tracking at user-set increments | **FreeCAD change** (Python, in `gui_snapper.py`) | The snapper has no extension point. Patching it from an add-on would break on each upstream edit. |
| 3.5 | Object snap overrides | Partial | Snap toggles in `gui_snaps.py`; no per-click override | **FreeCAD change** (same file) | Same reason as 3.4. |
| 3.6 | Auxiliary view | Missing | `auxiliary` appears only in DXF/Draft utils, not in TechDraw | Add-on: `DrawViewPart` with a `Direction` taken from a picked edge or face | `Direction` accepts any vector. Fold-line and alignment: view is placed along the normal of the edge. |
| 3.7 | Half section | Missing | no hit in TechDraw | Add-on: section of a derived shape (source cut by a half-space) | Derived shape is a `Part::Cut` that the add-on creates and hides. Hatch and cut line come from the stock section view. |
| 3.8 | Break-out section | Missing | no hit | Add-on: same, with the cutter built from a closed sketch extruded to a depth | Same method as 3.7. |
| 3.9 | Exploded views on drawings | Partial | Phase 4 will add exploded views to the Assembly. TechDraw sees an assembly as shapes (`ShapeExtractor.cpp`) | Depends on Phase 4 | Not started until Phase 4 has explode states that are stored as placements. |
| 3.10 | Auto-dimension | Missing | `ViewProviderViewPart.cpp` match is unrelated | Add-on: create `DrawViewDimension` on a view's edges/circles | Python can create dimensions with `References2D`. Placement rules are the work. |
| 3.11 | Model-dimension import | Missing | none | Add-on: sketch / PartDesign constraint values to dimensions | Needs the mapping from a sketch edge to the projected edge index. |
| 3.12 | GD&T frames and datums | Missing | none | Add-on: original SVG generator for frames, datum triangles and symbols, placed as `DrawViewSymbol` | R13: symbols drawn from the published geometry of the standard, no copied artwork. Tolerance values are text only; no semantic check (no ISO 1101/ASME Y14.5 validation). |
| 3.13 | Auto-balloon | Missing | `DrawViewBalloon` exists, no automatic placement | Add-on: balloons around a view by BOM item | Needs a BOM source (3.15). |
| 3.14 | Associative revision table | Missing | none. Title-block fields are `EditableTexts` on templates | Add-on: spreadsheet-driven table on the page, plus template field update | Uses `DrawViewSpreadsheet`. |
| 3.15 | Hole, BOM and cut-list tables | Missing | `DrawViewSpreadsheet` exists, no generators | Add-on: generators that fill a spreadsheet (holes from cylindrical faces; BOM from Body/Part list; cut list from Construction) | Pure data. |
| 3.16 | Dangling annotation detection | Partial | `DrawViewDimension` has `invalidRef` and `checkReferences2D()`. Leaders and balloons have no summary | Add-on: page-wide scan, report list | Reads stock state. |
| 3.17 | DIN and JIS presets, style manager | Missing | Templates only `ASME` and `ISO`. Draft has an annotation style editor (`gui_annotationstyleeditor.py`), TechDraw has none | Add-on: preset files (JSON of TechDraw preference values plus original templates) and an editor | Template SVG artwork must be original (R13). Standards-text content is not copied. |
| 3.18 | Export PNG | Missing | `exportPageAsPdf` and `exportPageAsSvg` exist, no PNG | Add-on: render the exported SVG with Qt | Uses `QSvgRenderer`. |
| 3.19 | DWG export | Present, limited | LibreDWG, ≤R2004 | None | Upstream limit stated in the design. |

## Upstream baseline confirmed present

TechDraw page and templates (ASME, ISO), projection groups, section, complex section (`ProjectionStrategy` Offset/Aligned),
detail, clip, Draft and Arch views, dimension types and tolerances, balloons, leaders, rich text, hatching, PDF/SVG/DXF export
(`TechDraw.writeDXFPage`, `TechDrawGui.exportPageAsPdf/Svg`). Draft: layers, snaps (endpoint, midpoint, center, intersection,
perpendicular, parallel, extension, angle, ortho), annotation styles, hatch, working planes, DXF/SVG import and export.

## Plan

Add-on `addons/drawing/`, each part with tests; GUI-only parts need the GUI test run for page creation and PDF/PNG output.

1. `Views`: auxiliary (3.6), half section (3.7), break-out (3.8).
2. `Dimensions`: auto-dimension (3.10), model-dimension import (3.11).
3. `Tables`: hole table, BOM, cut list, revision table (3.14, 3.15) and auto-balloon (3.13).
4. `Gdt`: frame and datum symbol generator (3.12).
5. `Check`: dangling annotation scan (3.16). `Export`: PNG (3.18).
6. `Presets`: DIN and JIS (3.17), library (3.1), sheet helper (3.3), xref manager (3.2).
7. Exit criteria: a 3-view, section and detail drawing of the Phase 2 bracket with GD&T; change a parameter; the drawing updates; PDF and DXF re-read by a third-party reader.

## Open risks

- **Headless limits.** `TechDrawGui.exportPageAsPdf` needs the GUI; the exit test must run under Xvfb. The DXF check can use `ezdxf` if installed; if not, DXF is only checked for a valid header and entity count.
- **Third-party viewer.** No viewer is installed in the container. "Opens in third-party viewers" can only be tested with a parser (e.g. `pypdf`, `ezdxf`), not an actual viewer.
- **Items needing FreeCAD changes (3.4, 3.5)** are Python edits in `gui_snapper.py`; they will be listed as not done unless a PR is wanted.
- **3.9** waits for Phase 4.

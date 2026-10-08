<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Reuse Survey

Reuse analysis for the CADApp fork (see `docs/DESIGN.md`). Lists which upstream
FreeCAD components cover each design-document phase, and which components the
fork adds. Detailed Present / Partial / Missing inventories live in
`docs/gaps/phase-N.md` and are written at the start of each phase (§5.0).

## Fork base

| Item | Value |
|---|---|
| Upstream repository | https://github.com/FreeCAD/FreeCAD |
| Fork base commit | `16298004` (upstream `main`, `version.json` = 27.1.0dev) |
| Deviation from §1 | §1 specifies the latest stable tag (1.1.x). The repository was created from upstream `main`, not a tag. Re-basing onto a stable tag is tracked in `docs/gaps/phase-0.md` (item 0.1.3). |
| Upstream history in clone | Shallow (681 commits). Full history must be restored before release (§2 "keep full git history"). |

## Upstream components by phase

| Phase | Upstream components (paths) | Expected coverage |
|---|---|---|
| 0 UX core | `src/Gui/Command.*`, `src/Gui/ShortcutManager.*`, `src/Gui/CommandCompleter.*`, `src/Gui/InputHint*.{h,cpp}`, `src/Gui/ToolHandler.*`, `src/Gui/Dialogs/DlgKeyboardImp.*`, `src/App/Branding.*` | Partial: global shortcuts, command search widget, per-tool input hints in status bar, branding.xml override. No context layers, palette, radial menu. |
| 1 Sketcher | `src/Mod/Sketcher` (PlaneGCS in `App/planegcs`, `Gui/DrawSketchHandler*.h`, on-view parameters, text tool `DrawSketchHandlerText.h`) | High |
| 2 Part modeling | `src/Mod/PartDesign` (`App/Feature*.cpp`: Pad, Pocket, Revolution, Groove, Loft, Pipe, Helix, Hole, Fillet, Chamfer, Draft, Thickness, patterns, Boolean, Defeaturing), `src/Mod/Part`, `src/Mod/Spreadsheet`, `src/App/VarSet.*`, `src/Mod/Measure` | High |
| 3 Drawings | `src/Mod/TechDraw`, `src/Mod/Draft` | High for drawings from 3D; partial for standalone 2D drafting |
| 4 Assemblies | `src/Mod/Assembly` (OndselSolver in `src/3rdParty/OndselSolver`; joints, BOM `CommandCreateBom.py`, exploded views `CommandCreateView.py`, simulation `CommandCreateSimulation.py`) | Medium |
| 5 Construction | `src/Mod/BIM` (walls, doors, windows, structure, `BimTruss.py`, `BimStairs.py`, `BimRoof.py`, `BimSchedule.py`, `BimFrame.py`, `BimProfile.py`, IFC import/export) | Low: building elements only; framing, joinery, cut optimization, nesting are new (`src/Mod/Construction/`) |
| 6 Direct/surface/mesh | `src/Mod/Part`, `src/Mod/Surface`, `src/Mod/Mesh`, `src/Mod/MeshPart`, `src/Mod/ReverseEngineering` | Medium for surface/mesh; direct editing and subdivision are new |
| 7 Sheet metal/frames | None in tree (SheetMetal is an external add-on); `src/Mod/BIM/bimcommands/BimFrame.py` for frames | Low |
| 8 Interop/automation | `src/Mod/Import` (STEP, IGES, glTF readers/writers, DXF), `src/Mod/Mesh` (STL, OBJ, 3MF, AMF), `src/Mod/BIM/importers` (IFC, DAE, SHP), Python API, macro recorder, `FreeCADCmd` | High for formats; vault/history are new |
| 9 Rendering | `src/Mod/Material` (appearance) | Low: no photoreal renderer in tree |
| 10 FEA | `src/Mod/Fem` (`femsolver/calculix`, `elmer`, `mystran`, `z88`, `fenics`; Gmsh/Netgen meshing; VTK post) | High |
| 11 CAM | `src/Mod/CAM` (operations incl. Adaptive, profile, pocket, drilling, engrave, V-carve, surface/waterline; simulator `PathSimulator`; post-processors `Path/Post/scripts`) | High; nesting and construction integration are new |
| 12 Generative | None | New (`src/Mod/Generative/`) |
| 13 Electronics | None | Deferred |

## Components added by the fork

Per §3.2. None are added in Phase 0. Each is added only after its license is
recorded in `THIRD_PARTY_LICENSES`.

## External add-ons evaluated (not in tree)

| Add-on | License (as stated by the project; verify before use) | Use |
|---|---|---|
| SheetMetal | LGPL-2.1 (verify LICENSE file) | Phase 7 candidate for merge |
| Woodworking | MIT | Phase 5 candidate, with credit |
| Fasteners | GPL-2.0 | Reference only; not merged |
| beso | LGPL-3.0 | Reference only |

<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Inherited Conflicts

Upstream features that conflict with `docs/DESIGN.md` (§1 network rule, §12 risk
register). Per the inherited-feature rule they stay **enabled by default**.
Re-check on every upstream merge (§12 R22).

## Risk register (§12)

| Risk | Feature | Upstream location | Compile flag (CMake) | Runtime flag | Default |
|---|---|---|---|---|---|
| R1 | Clickable navigation cube | `src/Gui/NaviCube.cpp`, gated in `src/Gui/View3DInventorViewer.cpp` | `CADAPP_FEATURE_NAVICUBE` | `BaseApp/Preferences/Fork/Features/NaviCube` | on |
| R3 | CAM Adaptive (constant-engagement clearing) | `src/Mod/CAM/Path/Op/Adaptive.py`, `Path/Op/Gui/Adaptive.py`, `src/Mod/CAM/libarea/Adaptive.*`; gated in `src/Mod/CAM/InitGui.py`, `src/Mod/CAM/Path/GuiInit.py` | `CADAPP_FEATURE_CAM_ADAPTIVE` | `BaseApp/Preferences/Fork/Features/CAMAdaptive` | on |

Runtime flags: set the bool to `false` in the parameter editor and restart.
Flag code: `src/App/Fork/FeatureFlags.*`, `src/Ext/freecad/fork_features.py`.

## Network features (§1)

Inherited code that makes network requests. Left enabled. Each is behind a flag
(default on). Runtime flags are bools under `BaseApp/Preferences/Fork/Features`;
with a flag off the feature behaves as if offline.

| Feature | Location | What it fetches | Flag | Off means |
|---|---|---|---|---|
| Addon Manager | `src/Mod/AddonManager` (submodule) | Add-on index, add-on repositories, macros | CMake `BUILD_ADDONMGR` (upstream option) | Not built |
| Online Help | `src/Mod/Help/Help.py` (`location_url`, `get_contents`, `convert_github`) | Wiki pages; GitHub markdown rendering API | `OnlineHelp` | No fetch; offline help location still works |
| Download manager | `src/Gui/DownloadManager.*`, `src/Gui/DownloadItem.*` (used from `MainWindow.cpp`, `ApplicationPy.cpp`) | Files from URLs dropped or opened in the app | `DownloadManager` | URLs ignored |
| BIM Library | `src/Mod/BIM/bimcommands/BimLibrary.py` (`download`, `getOnlineContentsAPI`, `getThumbnail`) | Online BIM object library and thumbnails | `BIMOnlineLibrary` | "Online" checkbox off and disabled; local library works |
| BIM Tutorial | `src/Mod/BIM/bimcommands/BimTutorial.py` | Tutorial pages and images from the wiki | `BIMTutorial` | Command greyed out |
| BIM shapefile import | `src/Mod/BIM/importers/importSHP.py` (`checkShapeFileLibrary`) | `pyshp` library download | `BIMShapefileDownload` | No download offer; manual install message |
| IFC schema download | `src/Mod/BIM/ArchCommands.py` (`download`), used by `importIFClegacy.py` | IFC schema files | `BIMDownload` | Returns `None` (same as a failed download) |
| CAM MTConnect import | `src/Mod/CAM/Machine/ui/mtconnect_import_dialog.py` (`_fetch_url`) | Machine description from a user-given URL | `CAMMTConnectURL` | URL import fails with a message; local files still work |

Not counted: code that only opens a URL in the system browser, and build or
maintainer scripts under `src/Tools/` that are not shipped.

## Reserved terms in inherited UI strings (§12 R21)

From `python3 tools/fork/check.py inventory`. Not renamed.

| Term | Module | String | Note |
|---|---|---|---|
| Adaptive Clearing | CAM | "Adaptive clearing and profiling" | Tooltip of R3 feature above |
| Configurations | FreeCAD | "Lists the mouse button configs …", "Safe mode temporarily disables your configurations and addons …" | Generic use, not a feature name |
| Toolbox | FreeCAD | "Toolbox Bars" | Qt toolbox widget, not a parts library |

<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Phase 0 Gap Inventory

Audit of Phase 0 target scope (`docs/DESIGN.md` §5) against this repository.
Status: **Present** (done, upstream or fork), **Partial**, **Missing**.

## 0.1 Fork setup

| # | Item | Status | Where / notes |
|---|---|---|---|
| 0.1.1 | `upstream` remote, fork `main` | Partial | `tools/fork/UPSTREAM_BASE` records the base commit; no `upstream` remote configured (`git remote add upstream https://github.com/FreeCAD/FreeCAD.git`) |
| 0.1.2 | Full upstream git history | Present | Not shallow; history back to 2011 |
| 0.1.3 | Base on latest stable tag (1.1.x) | Missing | Based on upstream `main` (see `SURVEY.md`); re-base onto tag |
| 0.1.4 | CI builds on Windows, macOS, Linux | Partial | Upstream `CI_primary.yml`, `sub_build*.yml`; not yet run with fork branding |
| 0.1.5 | Installers (MSI, DMG, AppImage/Flatpak) | Partial | Upstream `build_release.yml`; installer metadata not rebranded |
| 0.1.6 | Upstream test suite passing | Partial | Local macOS arm64 build (pixi, `build/relWithDebInfo`), 2026-10-09: C++ suite (ctest) 2183 / 2184 pass. Failing: `CrashReporterTests.realCrashCapturesUsableFrames` (captures 0 stack frames on this Mac; the fork does not touch the crash reporter). Python `TestApp` suite not yet run. CI not yet run on the fork |

## 0.2 Rebrand (§2)

| # | Item | Status | Where / notes |
|---|---|---|---|
| 0.2.1 | Single branding config | Present | `branding/branding.cmake` → `BrandingConfig.h` |
| 0.2.2 | Product name, vendor, app id, maintainer URL | Present | `src/Main/Main*.cpp` |
| 0.2.3 | User data directory differs from upstream | Present | Follows `ExeName` (`AppDataSkipVendor=true`) |
| 0.2.4 | Icons, splash, application logo | Missing | Upstream assets in `src/Gui/Icons/freecad*`; original replacements needed |
| 0.2.5 | About dialog: FreeCAD credit + non-affiliation | Partial | Strings in `BrandingConfig.h`; not yet shown in About |
| 0.2.6 | Window titles | Partial | Follow `ExeName`; audit hard-coded "FreeCAD" UI strings |
| 0.2.7 | Installer metadata, desktop file, macOS bundle | Missing | |

## 0.3 Compliance files

| # | Item | Status | Where / notes |
|---|---|---|---|
| 0.3.1 | `LICENSE` (upstream) | Present | |
| 0.3.2 | `THIRD_PARTY_LICENSES` | Present | Generated from `tools/fork/dependencies.json` |
| 0.3.3 | `CONTRIBUTING.md` clean-room attestation (R20) | Present | Fork section at top of `CONTRIBUTING.md`. CI enforcement of sign-off: Missing |
| 0.3.4 | `LEGAL.md` | Present | Dedicated contact address still TODO |
| 0.3.5 | SPDX headers, license and reserved-term CI checks (R21) | Present | `tools/fork/check.py`, `.github/workflows/fork_checks.yml` |
| 0.3.6 | Snippet-match scanning (R19) | Missing | |

## 0.4 Network rule (§1)

| # | Item | Status | Where / notes |
|---|---|---|---|
| 0.4.1 | Static network-API check on fork-added code | Present | `check.py network` |
| 0.4.2 | Inventory of inherited network features | Present | `docs/inherited-conflicts.md` |
| 0.4.3 | Flags (default on) for inherited network features | Present | Runtime flags per feature (`OnlineHelp`, `DownloadManager`, `BIMOnlineLibrary`, `BIMTutorial`, `BIMShapefileDownload`, `BIMDownload`, `CAMMTConnectURL`); Addon Manager via upstream `BUILD_ADDONMGR`. Table in `docs/inherited-conflicts.md` |
| 0.4.4 | Network-isolation runtime test (§10) | Missing | |

## 0.5 Inherited risk-register conflicts (§12)

| # | Item | Status | Where / notes |
|---|---|---|---|
| 0.5.1 | NaviCube behind flag, default on (R1) | Present | `CADAPP_FEATURE_NAVICUBE` + runtime flag |
| 0.5.2 | CAM Adaptive behind flag, default on (R3) | Present | `CADAPP_FEATURE_CAM_ADAPTIVE` + runtime flag. `OFF` hides the command; the operation's source files are still built |
| 0.5.3 | Full R1–R21 review of all upstream workbenches (R22) | Partial | Reserved terms and network done; patent review per workbench pending |
| 0.5.4 | DWG: bundle only LibreDWG | Missing | Not yet packaged |

## 0.6 Core UX layer (§6, §8)

Upstream baseline: `src/Gui/ShortcutManager.*` (global shortcuts, per-command
priority, multi-key sequences), `src/Gui/CommandCompleter.*` (command search
widget), `src/Gui/InputHint*` (per-tool hints in the status bar),
`src/Gui/Dialogs/DlgKeyboardImp.*` (remapping UI, global layer only).

| # | Item | Status | Where / notes |
|---|---|---|---|
| 0.6.1 | Context-layered hotkey resolution (command → workspace → global) | Partial | Engine `src/Gui/Hotkeys/HotkeyEngine.h` (Qt-free, tested). Wired in by `src/Gui/Hotkeys/ContextHotkeys.*`: hooks in `ShortcutManager` (key events), `Command::_invoke` (command scope), `ToolHandler` and `ControlSingleton::showDialog` (active tool). Context: workspace = active workbench name, command = command that started the innermost open tool handler or task dialog, selection = element type of the first selected item. Built; in the app, `TestConstructionGui.TestContextHotkeys` binds a workspace-layer key and pressing it runs the command; the strip shows the binding. Command-layer switching with an active tool not yet tested in the app |
| 0.6.2 | Chords and sequences | Partial | Engine supports sequences; upstream supports global sequences |
| 0.6.3 | Per-layer conflict detection, user override, reset to default | Partial | Engine API. Bindings come from `<UserAppData>/Hotkeys.json`; `Std_HotkeysReload` re-reads it and lists conflicts. No remapping UI for context layers |
| 0.6.4 | Profile import/export (JSON) | Partial | `Std_HotkeysImport` / `Std_HotkeysExport` (Tools menu) copy `Hotkeys.json`; import refuses a file that does not parse and reloads. Written without a build in this environment: compile and run once. Covers context layers only, not upstream's global shortcuts |
| 0.6.5 | Heads-up hotkey strip (`F1`) | Partial | Status-bar item "Hotkey Strip" (`src/Gui/Hotkeys/HotkeyCommands.cpp`), shown/hidden from the status-bar context menu; shows the innermost active layer. No `F1` toggle (upstream `F1` is What's This, 0.6.10). Polls the context every 300 ms |
| 0.6.6 | Next-tool suggestions | Missing | |
| 0.6.7 | Command palette (`Space`) | Partial | `Std_CommandPalette`: popup search over all commands (upstream `CommandCompleter`). No default key (upstream `Space` is show/hide, 0.6.10) |
| 0.6.8 | Radial menu | Partial | `Std_RadialMenu`: up to 8 commands around the cursor, per workbench in `BaseApp/Preferences/Fork/RadialMenu`. Opened by command only; right-drag opening (§6) not done, as navigation styles use the right button |
| 0.6.9 | Inline value entry framework | Partial | Sketcher on-view parameters; not generic |
| 0.6.10 | Default keymaps (§8.2–8.4) | Missing | Decision (2026-10-08): upstream keymaps stay the defaults. §8 keys conflict with them (§8.3 `G` shadows Sketcher `G, L`, …; §8.2 `Space` is upstream show/hide; `F1` is What's This). §8 keymaps may ship only as an opt-in profile (0.6.4) |

## Exit criteria status

| Criterion | Status |
|---|---|
| Branded build installs side-by-side with upstream on 3 OS | Not met (0.1.4, 0.1.5, 0.2.4, 0.2.7) |
| Upstream tests pass | Partial: 2183 / 2184 C++ tests locally (0.1.6) |
| Fork-added code passes network check | Met |
| `docs/inherited-conflicts.md` lists all inherited conflicts with flags (default on) | Partial (0.5.3 patent review per workbench) |
| Hotkey context layers switch with the active tool | Partial: workspace layer verified in the app; command layer (active tool) not yet tested in the app (0.6.1) |
| Remap a hotkey | Global: upstream dialog. Context layers: edit `Hotkeys.json` + `Std_HotkeysReload` |
| Command palette finds any registered command | Met in the app: the palette's completer lists registered commands (`TestCoreUx`) |

## 0.7 UX add-on (`addons/ux/`, 2026-10-13)

Python rewrite of the fork's C++ UX (§4.5). Tests: `FreeCADCmd -t TestUx` (24, headless) and
`FreeCAD -t TestUxGui` (6, GUI); both pass against the CADApp-branded build in this container.

| Item | Status | Notes |
|---|---|---|
| Add-on template, local-folder install, test runner | Present | `addons/template/`; `addons/ci/run_tests.py <addon> <module>... [--gui]` links the add-on into `<user data>/Mod/`, runs the static checks and the tests, removes the link |
| Command palette | Present | `Palette.py`, `Ctrl+Shift+P`, app-wide `QShortcut` (a command's `Accel` only fires when its action is on the active workbench). Lists commands of loaded workbenches only: a workbench's commands exist once it is activated (same as upstream's search) |
| Workspace and global hotkey layers, per-layer conflicts | Present | `Hotkeys.py`, `<user data>/UxHotkeys.json`; `ShortcutOverride` filter runs ahead of Qt shortcuts; text inputs are skipped. No chords |
| Profile import/export (JSON), remapping UI with search and conflicts | Present | `Remap.py` (`UX_Hotkeys`). Covers the UX layers only, not upstream's global shortcuts |
| Heads-up hotkey strip | Present | `Strip.py` (`UX_HotkeyStrip`): status-bar label, workspace bindings first. No `F1` toggle (upstream `F1` is What's This) |
| Next-tool suggestions | Present | `Suggest.py`: rules keyed by the type of the last created object (sketch → Pad, Pocket, ...), shown in the strip, run with `Alt+1`..`Alt+5`. No local usage statistics |
| Radial menu | Partial | `Radial.py` (`UX_RadialMenu`): up to 8 commands per workbench from `UxHotkeys.json` (`radial`). Opened by command or hotkey; right-drag opening not done (navigation styles use the right button) |
| Command (active-tool) layer | Missing | Needs a Python signal from tool handlers: proposal in `docs/upstream/tool-context-hook.md`, not submitted |
| Inline value entry | Missing | Sketcher has on-view parameters; a generic framework is not started |
| Default keymaps (§8.2-8.4) | Missing | As 0.6.10: opt-in profile only |
| CI on 3 OS, stock FreeCAD | Written, not run | `.github/workflows/addons.yml`; all local testing is against the CADApp-branded build, not stock FreeCAD |
| Network-API check | Present | `addons/*/check.py network`; no runtime network-isolation test |

## Exit criteria (Phase 0, add-on strategy)

| Criterion | Status |
|---|---|
| Construction and UX add-ons install into stock FreeCAD on 3 OS from a local folder and pass their tests | Partial: install and pass on Linux in the CADApp build; stock FreeCAD and Windows/macOS not tried |
| Add-on code passes the network-API check | Met (`check.py all` on template, ux, construction) |
| Workspace-level hotkey layers switch with the workbench and task dialog | Partial: workbench layer tested (`Hotkeys.resolve`, key press in `TestUxGui`); no task-dialog layer yet (`Gui.Control.activeDialog()` could serve) |
| Remap a hotkey | Met (`TestUxGui.test_remap_dialog_edits_and_saves`) |
| Command palette finds any registered command | Met for loaded workbenches |
| The per-tool context hook is proposed upstream | Drafted (`docs/upstream/tool-context-hook.md`), not submitted |

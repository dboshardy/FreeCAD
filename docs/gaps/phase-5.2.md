<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Phase 5.2 Gap Inventory — Construction Usability

Audit of Phase 5.2 target scope (`docs/DESIGN.md`, Phase 5.2). Status:
**Present**, **Partial**, **Missing**.

| Scope item | Status | Notes |
|---|---|---|
| 1. Parametric templates | Present | Template presets (`Build.PRESETS`: end table, dining table, workbench, bookcase) put their sizes and choices on the build as properties (group Template: lengths, counts, stock and joint dropdowns). Changing one regenerates the tables (`BuildFeature.regenerate`); rows edited or added by hand are kept (`Build.merge`) and edited ones marked `edited`. A size the template cannot build marks the build invalid with the reason. Survives save and reopen |
| 2. Task panels with dropdowns | Missing | |
| 3. Room / footprint object | Missing | |
| 4. Shed template opened up | Missing | |
| 5. Direct manipulation | Missing | |

## Exit criteria status

| Criterion | Status |
|---|---|
| (a) L-shaped kitchen from one panel | Not yet |
| (b) End Table 50 mm taller and Z-clips with two property changes | Met: `TestConstructionApp.test_parametric_template` |
| (c) Window added to a shed wall from a panel | Not yet |
| (d) Build part dragged, snapping to a face | Not yet |

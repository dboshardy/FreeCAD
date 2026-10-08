<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork (design doc §12.4 item 6).
-->

# Legal

CADApp is based on FreeCAD (https://www.freecad.org) and is licensed under
LGPL-2.1-or-later. CADApp is not affiliated with, endorsed by, or sponsored by the
FreeCAD project or the FreeCAD Project Association. Third-party components and
their licenses are listed in `THIRD_PARTY_LICENSES`.

## Claims and takedown requests

Open an issue at https://github.com/dboshardy/MyCAD/issues titled
`LEGAL: <short subject>`. Do not include confidential material in the issue. Ask
for a private contact address in the issue if one is needed.
<!-- TODO before first public release: replace with a dedicated legal contact address. -->

Include: the right claimed (patent, copyright, trademark), its number or
registration, the affected feature or file, and your contact details.

## Disabling a feature

Features with known patent exposure (`docs/DESIGN.md` §12) are behind a
compile-time and a runtime flag. The full list is in `docs/inherited-conflicts.md`.

- **Runtime (user):** Tools > Edit parameters > `BaseApp/Preferences/Fork/Features`,
  set the feature's bool to `false`, restart.
- **Build (release):** configure with `-D<FLAG>=OFF`, for example
  `cmake -DCADAPP_FEATURE_NAVICUBE=OFF`. The feature is then not built.

## Release process (legal steps)

1. `python3 tools/fork/check.py all` passes (network, reserved terms, data
   licenses, headers, dependency licenses).
2. `THIRD_PARTY_LICENSES` matches `tools/fork/dependencies.json`.
3. Corresponding source is published with every binary (LGPL).
4. Before 1.0: freedom-to-operate opinion covering §12 R1–R10, and trademark
   clearance for the product name (§12 R17).
5. If a claim is accepted: ship a patch release with the affected feature's
   compile flag set to `OFF`, and record the change in `docs/inherited-conflicts.md`.

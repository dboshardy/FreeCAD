<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

# CADApp add-on template

Copy this folder, rename the workbench class, `package.xml` entries and `TestTemplate.py`.
Install by copying to `<FreeCAD user dir>/Mod/<name>` or from the Addon Manager.
Tests: see `CONTRIBUTING.md`.

## Install from a local folder and test

```
ln -s "$PWD" "$(FreeCADCmd -c 'import FreeCAD;print(FreeCAD.getUserAppDataDir())' | tail -1)Mod/<name>"
FreeCADCmd -t TestTemplate
```

`PYTHONPATH` does not reach the test loader; the symlink into `Mod/` does (its `Init.py` registers the test).
Static checks: `python3 check.py all .`

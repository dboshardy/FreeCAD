#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Installs an add-on into stock FreeCAD from its folder and runs its tests there.

Usage: run_tests.py <addon folder> <test module>... [--gui] [--freecad DIR_OR_EXE]
  Static checks (network APIs, SPDX headers) run first. --gui runs the modules with
  the FreeCAD GUI (`FreeCAD -t`), otherwise headless (`FreeCADCmd -t`).
The add-on is linked (copied on Windows) into <user data>/Mod/<folder name>, and removed after.
"""
# shortcut: tests run one FreeCAD process per module; batch them if start-up cost matters.

import os
import shutil
import subprocess
import sys
from pathlib import Path


def find(name, hint):
    names = (name, name.lower())  # conda installs lower-case names on Linux
    if hint:
        p = Path(hint)
        if p.is_file():
            return str(p)
        for n in names:
            for c in (p / n, p / "bin" / n, p / "usr" / "bin" / n, p / f"{n}.exe", p / "bin" / f"{n}.exe"):
                if c.exists():
                    return str(c)
    return next((w for n in names if (w := shutil.which(n))), None) or sys.exit(f"{name} not found: pass --freecad")


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    gui = "--gui" in argv
    hint = argv[argv.index("--freecad") + 1] if "--freecad" in argv else os.environ.get("FREECAD")
    if hint in args:
        args.remove(hint)
    addon, modules = Path(args[0]).resolve(), args[1:]
    if subprocess.run([sys.executable, str(addon / "check.py"), "all", str(addon)]).returncode:
        return 1
    cmd = find("FreeCADCmd", hint)
    out = subprocess.run(
        [cmd, "-c", "import FreeCAD;print('USERDIR='+FreeCAD.getUserAppDataDir())"],
        capture_output=True, text=True,
    ).stdout
    userdir = next(l for l in out.splitlines() if l.startswith("USERDIR="))[8:]
    target = Path(userdir) / "Mod" / addon.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.exists():
        target.unlink() if target.is_symlink() else shutil.rmtree(target)
    try:
        target.symlink_to(addon, target_is_directory=True)
    except OSError:  # Windows without symlink rights
        shutil.copytree(addon, target)
    try:
        failed = 0
        for module in modules:
            exe = find("FreeCAD", hint) if gui else cmd
            failed |= subprocess.run([exe, "-t", module]).returncode
        return 1 if failed else 0
    finally:
        target.unlink() if target.is_symlink() else shutil.rmtree(target)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

# Hotkey profiles

`design-doc-keymap.json`: the single-key defaults of design doc §8.2-8.3, opt-in. Several keys shadow
FreeCAD's own (`Space` shows or hides, `H`, `G` in the Sketcher, `F2`); FreeCAD's keymaps stay the
default. Import it in Tools > Hotkeys... (Import), or copy it to `<user data>/UxHotkeys.json`.
Not in the profile: keys that map to nothing FreeCAD has as one command (`Q`, `W`, `X`, `K`) and
the in-command layers of §8.4 (they need the upstream tool hook).

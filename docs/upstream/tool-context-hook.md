<!--
SPDX-License-Identifier: LGPL-2.1-or-later
-->

# Upstream proposal: a Python-visible "active tool" signal

Draft for a FreeCAD pull request (design doc §4.2, Phase 0). Not yet submitted: needs a FreeCAD
build to write and test the C++ change, and the project's contribution process.

## Why an add-on cannot do it

The UX add-on (`addons/ux`) layers hotkeys: command (active tool), workspace, global. Workspace and
global layers work from Python. The command layer needs to know *which tool is running*, for example
the Sketcher line tool, and Python gets no signal when one starts or ends:

- `Gui::ToolHandler` (Sketcher tools, Draft-style handlers) and `Gui::Control::showDialog` (task
  dialogs) are C++ only.
- `Gui.Control.activeDialog()` answers for task dialogs, but not for tool handlers, and cannot notify.
- Polling `Gui.Control.activeDialog()` misses every tool handler. Event filters cannot tell a Sketcher
  tool from idle.

## Smallest change

A single Python-visible notification, nothing about hotkeys in FreeCAD:

```python
# FreeCADGui
Gui.addToolObserver(obj)   # obj.toolStarted(name: str), obj.toolFinished(name: str)
Gui.removeToolObserver(obj)
Gui.activeTool() -> str | None     # name of the innermost tool: the command that started it
```

- `name` is the command that started the tool or task dialog (`Command::_invoke` already knows it;
  the fork keeps it in a scope object, `Hotkeys::CommandScope`).
- Fire from `ToolHandler::activate()/deactivate()` and `Control::showDialog()/closeDialog()`, the
  places the fork's hooks sit (`src/Gui/ToolHandler.cpp`, `src/Gui/Control.cpp`).
- Tests: a gtest for the observer list, and a Python `TestGui` test that starts a Sketcher line tool
  through `Gui.runCommand("Sketcher_CreateLine")` and sees one `toolStarted` / `toolFinished` pair.

## Second hook, only if needed

Context layers that run ahead of Qt shortcuts (the fork's `Hotkeys::handleKey` in `ShortcutManager`).
The add-on already gets this from a `QEvent::ShortcutOverride` event filter, so it is **not** part of
the proposal unless that filter proves unreliable for key sequences.

## What stays in the add-on

Bindings, layer resolution, the strip, remapping and profiles: `addons/ux/Hotkeys.py`. The command
layer is added there as a third layer once the signal exists (`LAYERS` in `Hotkeys.py`).

## Fallback if upstream declines

Per design doc §11 question 2: keep the command layer out; the add-on's strip still lists workspace
and global bindings, and Sketcher's own per-tool shortcuts keep working. Shipping a patched FreeCAD
is not an option.

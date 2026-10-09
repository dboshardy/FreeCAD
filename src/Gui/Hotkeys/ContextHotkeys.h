// SPDX-License-Identifier: LGPL-2.1-or-later
// FORK: connects the hotkey engine (HotkeyEngine.h) to the GUI (design doc §8.1).

#pragma once

#include <string>
#include <vector>

#include "HotkeyEngine.h"

class QKeyEvent;

namespace Gui
{
class MainWindow;
}

namespace Gui::Hotkeys
{

/// Names the command whose activated() is running, so tools it starts
/// (tool handlers, task dialogs) take its id as their command context.
class CommandScope
{
public:
    explicit CommandScope(const char* commandId);
    ~CommandScope();
    CommandScope(const CommandScope&) = delete;
    CommandScope& operator=(const CommandScope&) = delete;

private:
    std::string previous;
};

/// A tool handler or task dialog opened or closed.
void toolStarted(const void* owner);
void toolFinished(const void* owner);

/// Offers a ShortcutOverride or KeyPress event to the context layers.
/// Returns true when the event was consumed.
bool handleKey(QKeyEvent* event);

/// Re-reads <UserAppData>/Hotkeys.json. Returns one line per conflict.
std::vector<std::string> reload();

/// Bindings of the innermost active layer in the current context.
std::vector<Binding> stripBindings();

/// Registers Std_CommandPalette, Std_RadialMenu, Std_HotkeysReload (HotkeyCommands.cpp).
void createCommands();

/// Adds the heads-up hotkey strip to the status bar (HotkeyCommands.cpp).
void addHotkeyStrip(MainWindow* mw);

}  // namespace Gui::Hotkeys

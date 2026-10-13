// SPDX-License-Identifier: LGPL-2.1-or-later
// FORK: connects the hotkey engine (HotkeyEngine.h) to the GUI (design doc §8.1).

#include "ContextHotkeys.h"

#include <algorithm>
#include <utility>

#include <QApplication>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QKeyEvent>
#include <QKeySequence>
#include <QTimer>
#include <QWidget>

#include <App/Application.h>
#include <Base/Console.h>
#include <Gui/Application.h>
#include <Gui/Command.h>
#include <Gui/Selection/Selection.h>
#include <Gui/Workbench.h>
#include <Gui/WorkbenchManager.h>

#include "HotkeyEngine.h"

namespace Gui::Hotkeys
{

namespace
{

std::string invoking;  // command whose activated() is running
ToolStack tools;
Keys typed;             // chords of a sequence in progress
bool swallowKeyPress = false;

std::string keymapPath()
{
    return App::Application::getUserAppDataDir() + "Hotkeys.json";
}

/// Reads the user keymap:
/// {"bindings": [{"keys": ["G", "H"], "command": "Std_ViewHome",
///                "layer": "command|workspace|global", "scope": "...",
///                "selection": "Edge", "priority": 0}]}
std::vector<Binding> loadKeymap()
{
    const auto path = keymapPath();
    QFile file(QString::fromStdString(path));
    if (!file.open(QIODevice::ReadOnly)) {
        return {};
    }
    QJsonParseError error;
    const auto doc = QJsonDocument::fromJson(file.readAll(), &error);
    if (error.error != QJsonParseError::NoError) {
        Base::Console().warning("{}: {}\n", path, error.errorString().toStdString());
        return {};
    }
    std::vector<Binding> out;
    for (const auto& value : doc.object().value(QStringLiteral("bindings")).toArray()) {
        const auto obj = value.toObject();
        Binding b;
        for (const auto& key : obj.value(QStringLiteral("keys")).toArray()) {
            b.keys.push_back(key.toString().toStdString());
        }
        b.commandId = obj.value(QStringLiteral("command")).toString().toStdString();
        b.scope = obj.value(QStringLiteral("scope")).toString().toStdString();
        b.selection = obj.value(QStringLiteral("selection")).toString().toStdString();
        b.priority = obj.value(QStringLiteral("priority")).toInt();
        const auto layer = obj.value(QStringLiteral("layer")).toString(QStringLiteral("global"));
        if (layer == QLatin1String("command")) {
            b.layer = Layer::Command;
        }
        else if (layer == QLatin1String("workspace")) {
            b.layer = Layer::Workspace;
        }
        else if (layer != QLatin1String("global")) {
            b.keys.clear();  // reject below
        }
        bool badKey = std::ranges::any_of(b.keys, [](const auto& k) { return k.empty(); });
        if (b.keys.empty() || badKey || b.commandId.empty()) {
            Base::Console().warning("{}: skipped invalid binding for '{}'\n", path, b.commandId);
            continue;
        }
        out.push_back(std::move(b));
    }
    return out;
}

HotkeyEngine instance;
bool loaded = false;

HotkeyEngine& engine()
{
    if (!loaded) {
        reload();
    }
    return instance;
}

Context currentContext()
{
    Context ctx;
    if (auto wb = WorkbenchManager::instance()->active()) {
        ctx.workspace = wb->name();
    }
    ctx.command = tools.active();
    const auto sel = Selection().getSelection(nullptr, ResolveMode::OldStyleElement);
    if (!sel.empty() && sel.front().SubName) {
        ctx.selection = selectionType(sel.front().SubName);
    }
    return ctx;
}

bool isModifier(int key)
{
    return key == Qt::Key_Shift || key == Qt::Key_Control || key == Qt::Key_Alt
        || key == Qt::Key_Meta || key == Qt::Key_AltGr;
}

}  // namespace

CommandScope::CommandScope(const char* commandId)
    : previous(std::exchange(invoking, commandId ? commandId : ""))
{}

CommandScope::~CommandScope()
{
    invoking = std::move(previous);
}

std::vector<std::string> reload()
{
    loaded = true;
    instance.setDefaults(loadKeymap());
    typed.clear();
    std::vector<std::string> out;
    for (const auto& [a, b] : instance.conflicts()) {
        out.push_back("'" + a.commandId + "' and '" + b.commandId + "' conflict");
        Base::Console().warning("Hotkeys: {}\n", out.back());
    }
    return out;
}

void toolStarted(const void* owner)
{
    tools.start(owner, invoking);
}

void toolFinished(const void* owner)
{
    tools.finish(owner);
}

bool handleKey(QKeyEvent* event)
{
    if (event->type() == QEvent::KeyPress) {
        // The press that follows an override we consumed.
        return std::exchange(swallowKeyPress, false);
    }
    swallowKeyPress = false;  // in case the previous press never arrived

    const int key = event->key();
    if (key == 0 || key == Qt::Key_unknown || isModifier(key)) {
        return false;
    }
    // Text input (line edits, Python console, ...) keeps its keys.
    auto focus = QApplication::focusWidget();
    if (focus && focus->testAttribute(Qt::WA_InputMethodEnabled)) {
        typed.clear();
        return false;
    }

    typed.push_back(
        QKeySequence(event->keyCombination()).toString(QKeySequence::PortableText).toStdString()
    );
    const auto result = engine().resolve(typed, currentContext());
    if (result.status == Resolution::Status::None) {
        typed.clear();
        return false;
    }
    if (result.status == Resolution::Status::Match) {
        typed.clear();
        // Run outside the event filter, like upstream's delayed shortcut trigger.
        QTimer::singleShot(0, [id = result.commandId] {
            Application::Instance->commandManager().runCommandByName(id.c_str());
        });
    }
    swallowKeyPress = true;
    event->accept();
    return true;
}

}  // namespace Gui::Hotkeys

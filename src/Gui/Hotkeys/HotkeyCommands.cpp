// SPDX-License-Identifier: LGPL-2.1-or-later
// FORK: core UX commands (design doc §6, §8): command palette, radial menu,
// heads-up hotkey strip, keymap reload. No default shortcuts: upstream
// keymaps stay the defaults (docs/gaps/phase-0.md 0.6.10).

#include <cmath>
#include <numbers>

#include <QCursor>
#include <QLabel>
#include <QLineEdit>
#include <QStringList>
#include <QTimer>
#include <QToolButton>

#include <App/Application.h>
#include <Gui/Action.h>
#include <Gui/Application.h>
#include <Gui/BitmapFactory.h>
#include <Gui/Command.h>
#include <Gui/CommandCompleter.h>
#include <Gui/MainWindow.h>
#include <Gui/Workbench.h>
#include <Gui/WorkbenchManager.h>

#include "ContextHotkeys.h"

namespace Gui::Hotkeys
{

namespace
{

void runLater(const QByteArray& name)
{
    // Leave the popup's event handling before the command runs.
    QTimer::singleShot(0, [name] {
        Application::Instance->commandManager().runCommandByName(name.constData());
    });
}

QString menuText(const std::string& commandId)
{
    auto cmd = Application::Instance->commandManager().getCommandByName(commandId.c_str());
    return cmd ? Action::commandMenuText(cmd) : QString::fromStdString(commandId);
}

/// Radial menu commands for the active workbench: parameter
/// BaseApp/Preferences/Fork/RadialMenu/<workbench name>, falling back to "Default".
/// Comma-separated command names, up to 8.
QStringList radialCommands()
{
    static const char* fallback =
        "Std_ViewFitAll,Std_ViewIsometric,Std_ViewFront,Std_ViewTop,"
        "Std_ToggleVisibility,Std_Delete,Std_Undo,Std_Redo";
    auto group = App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Fork/RadialMenu"
    );
    std::string list = group->GetASCII("Default", fallback);
    if (auto wb = WorkbenchManager::instance()->active()) {
        list = group->GetASCII(wb->name().c_str(), list.c_str());
    }
    return QString::fromStdString(list).split(QLatin1Char(','), Qt::SkipEmptyParts).mid(0, 8);
}

}  // namespace

// ---------------------------------------------------------------- palette

DEF_STD_CMD(StdCmdCommandPalette)

StdCmdCommandPalette::StdCmdCommandPalette()
    : Command("Std_CommandPalette")
{
    sGroup = "Tools";
    sMenuText = QT_TR_NOOP("Command &Palette");
    sToolTipText = QT_TR_NOOP("Searches all commands by name, internal name, or shortcut");
    sWhatsThis = "Std_CommandPalette";
    sStatusTip = sToolTipText;
    eType = 0;
}

void StdCmdCommandPalette::activated(int)
{
    auto mw = getMainWindow();
    auto edit = new QLineEdit(mw);
    edit->setWindowFlags(Qt::Popup);
    edit->setAttribute(Qt::WA_DeleteOnClose);
    edit->setPlaceholderText(QObject::tr("Type a command name"));
    edit->setMinimumWidth(480);
    auto completer = new CommandCompleter(edit, edit);
    QObject::connect(
        completer,
        &CommandCompleter::commandActivated,
        edit,
        [edit](const QByteArray& name) {
            edit->close();
            runLater(name);
        }
    );
    edit->adjustSize();
    edit->move(mw->mapToGlobal(QPoint((mw->width() - edit->width()) / 2, mw->height() / 6)));
    edit->show();
    edit->setFocus();
}

// ---------------------------------------------------------------- radial menu

DEF_STD_CMD(StdCmdRadialMenu)

StdCmdRadialMenu::StdCmdRadialMenu()
    : Command("Std_RadialMenu")
{
    sGroup = "Tools";
    sMenuText = QT_TR_NOOP("&Radial Menu");
    sToolTipText = QT_TR_NOOP("Shows up to 8 commands around the cursor");
    sWhatsThis = "Std_RadialMenu";
    sStatusTip = sToolTipText;
    eType = 0;
}

// ponytail: opened by command only. Right-drag opening (§6) needs a hook in the
// navigation styles, several of which already use the right button.
void StdCmdRadialMenu::activated(int)
{
    constexpr int radius = 100;
    constexpr int size = 2 * radius + 120;
    auto menu = new QWidget(getMainWindow(), Qt::Popup | Qt::FramelessWindowHint);
    menu->setAttribute(Qt::WA_DeleteOnClose);
    menu->setAttribute(Qt::WA_TranslucentBackground);
    menu->resize(size, size);

    const auto names = radialCommands();
    auto& manager = Application::Instance->commandManager();
    for (int i = 0; i < names.size(); ++i) {
        auto cmd = manager.getCommandByName(names[i].toUtf8().constData());
        if (!cmd) {
            continue;
        }
        auto button = new QToolButton(menu);
        button->setText(Action::commandMenuText(cmd));
        button->setToolTip(Action::commandToolTip(cmd));
        if (cmd->getPixmap()) {
            button->setIcon(BitmapFactory().iconFromTheme(cmd->getPixmap()));
        }
        button->setToolButtonStyle(Qt::ToolButtonTextUnderIcon);
        button->setEnabled(cmd->isActive());
        button->adjustSize();
        // Clockwise from the top, 45° apart.
        const double angle = -std::numbers::pi / 2 + i * std::numbers::pi / 4;
        const QPoint centre(
            size / 2 + int(std::lround(radius * std::cos(angle))),
            size / 2 + int(std::lround(radius * std::sin(angle)))
        );
        button->move(centre - button->rect().center());
        QObject::connect(button, &QToolButton::clicked, menu, [menu, name = names[i].toUtf8()] {
            menu->close();
            runLater(name);
        });
    }
    menu->move(QCursor::pos() - QPoint(size / 2, size / 2));
    menu->show();
}

// ---------------------------------------------------------------- reload

DEF_STD_CMD(StdCmdHotkeysReload)

StdCmdHotkeysReload::StdCmdHotkeysReload()
    : Command("Std_HotkeysReload")
{
    sGroup = "Tools";
    sMenuText = QT_TR_NOOP("Reload &Hotkeys");
    sToolTipText = QT_TR_NOOP(
        "Re-reads the context hotkeys file (Hotkeys.json in the user data folder); "
        "conflicts are listed in the Report view"
    );
    sWhatsThis = "Std_HotkeysReload";
    sStatusTip = sToolTipText;
    eType = 0;
}

void StdCmdHotkeysReload::activated(int)
{
    // Conflicts are listed in the Report view by reload(); no modal dialog.
    const auto conflicts = reload();
    const QString text = conflicts.empty()
        ? QObject::tr("Hotkeys reloaded. No conflicts.")
        : QObject::tr("Hotkeys reloaded. %n conflict(s), see the Report view.",
                      "",
                      int(conflicts.size()));
    getMainWindow()->showMessage(text, 10000);
}

// ---------------------------------------------------------------- setup

void createCommands()
{
    auto& manager = Application::Instance->commandManager();
    manager.addCommand(new StdCmdCommandPalette());
    manager.addCommand(new StdCmdRadialMenu());
    manager.addCommand(new StdCmdHotkeysReload());
}

void addHotkeyStrip(MainWindow* mw)
{
    auto label = new QLabel(mw);
    mw->addStatusBarItem(
        label,
        {.id = "hotkeyStrip",
         //: A context menu action used to show or hide the hotkey strip in the status bar
         .title = QObject::tr("Hotkey Strip"),
         .slot = StatusBarSlot::Right,
         .order = 90,
         .persistentVisibility = true}
    );
    // ponytail: polls the context every 300 ms; switch to change notifications
    // (tool start/finish, workbench, selection) if profiling shows a cost.
    auto timer = new QTimer(label);
    QObject::connect(timer, &QTimer::timeout, label, [label] {
        if (!label->isVisible()) {
            return;
        }
        QStringList items;
        for (const auto& b : stripBindings()) {
            QStringList keys;
            for (const auto& k : b.keys) {
                keys << QString::fromStdString(k);
            }
            items << QStringLiteral("<b>%1</b> %2").arg(
                keys.join(QStringLiteral(", ")).toHtmlEscaped(),
                menuText(b.commandId).toHtmlEscaped()
            );
        }
        label->setText(items.join(QStringLiteral("&nbsp;&nbsp;")));
    });
    timer->start(300);
}

}  // namespace Gui::Hotkeys

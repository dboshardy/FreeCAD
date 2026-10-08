// SPDX-License-Identifier: LGPL-2.1-or-later
// FORK: context-layered hotkey resolution (design doc §8.1). Header-only and
// free of Qt so it builds and tests standalone (tests/src/Gui/Hotkeys).

#pragma once

#include <algorithm>
#include <map>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace Gui::Hotkeys
{

/// Resolution order: Command, then Workspace, then Global. First match wins.
enum class Layer
{
    Command,
    Workspace,
    Global,
};

/// What is active when a key is pressed.
struct Context
{
    std::string workspace;  ///< e.g. "Sketch"
    std::string command;    ///< active command id, empty when idle
    std::string selection;  ///< selection type, e.g. "Edge"; empty for none
};

/// One key sequence: chords in order, e.g. {"G", "H"} or {"Ctrl+S"}.
/// Chords are compared as strings; callers pass one canonical spelling
/// (QKeySequence::PortableText in the Qt layer).
using Keys = std::vector<std::string>;

struct Binding
{
    Keys keys;
    std::string commandId;
    Layer layer = Layer::Global;
    /// Command id (Command layer) or workspace name (Workspace layer). Ignored for Global.
    std::string scope;
    /// Active only for this selection type. Empty: any selection.
    std::string selection;
    /// Higher wins among same-layer bindings with identical keys.
    int priority = 0;
};

struct Resolution
{
    enum class Status
    {
        None,     ///< no binding starts with these keys
        Pending,  ///< prefix of a longer sequence; wait for the next chord
        Match,
    };
    Status status = Status::None;
    std::string commandId;
};

class HotkeyEngine
{
public:
    /// Replaces the default bindings. User overrides are kept.
    void setDefaults(std::vector<Binding> bindings)
    {
        defaults = std::move(bindings);
    }

    /// Remaps the default binding with the same layer, scope, command and
    /// selection as @p binding (its keys are ignored).
    /// Empty @p keys unbinds it. Returns false if no such default exists.
    bool setUserKeys(const Binding& binding, Keys keys)
    {
        auto it = std::find_if(defaults.begin(), defaults.end(), [&](const Binding& b) {
            return key(b) == key(binding);
        });
        if (it == defaults.end()) {
            return false;
        }
        overrides[key(*it)] = std::move(keys);
        return true;
    }

    void reset(const Binding& binding)
    {
        overrides.erase(key(binding));
    }

    void resetAll()
    {
        overrides.clear();
    }

    /// Defaults with user overrides applied; unbound entries removed.
    std::vector<Binding> bindings() const
    {
        std::vector<Binding> out;
        for (auto b : defaults) {
            if (auto it = overrides.find(key(b)); it != overrides.end()) {
                b.keys = it->second;
            }
            if (!b.keys.empty()) {
                out.push_back(std::move(b));
            }
        }
        return out;
    }

    /// Resolves the chords typed so far in @p ctx.
    Resolution resolve(const Keys& typed, const Context& ctx) const
    {
        const auto all = bindings();
        for (Layer layer : {Layer::Command, Layer::Workspace, Layer::Global}) {
            const Binding* best = nullptr;
            bool pending = false;
            for (const auto& b : all) {
                if (b.layer != layer || !active(b, ctx)) {
                    continue;
                }
                if (b.keys == typed) {
                    if (!best || rank(b) > rank(*best)) {
                        best = &b;
                    }
                }
                else if (isPrefix(typed, b.keys)) {
                    pending = true;
                }
            }
            if (best) {
                return {Resolution::Status::Match, best->commandId};
            }
            if (pending) {
                return {Resolution::Status::Pending, {}};
            }
        }
        return {};
    }

    /// Pairs in the same layer and scope that can fire together and clash:
    /// identical keys at equal priority, or one sequence a prefix of the other
    /// (the shorter one makes the longer unreachable).
    std::vector<std::pair<Binding, Binding>> conflicts() const
    {
        const auto all = bindings();
        std::vector<std::pair<Binding, Binding>> out;
        for (size_t i = 0; i < all.size(); ++i) {
            for (size_t j = i + 1; j < all.size(); ++j) {
                const auto& a = all[i];
                const auto& b = all[j];
                if (a.layer != b.layer || (a.layer != Layer::Global && a.scope != b.scope)) {
                    continue;
                }
                if (!a.selection.empty() && !b.selection.empty() && a.selection != b.selection) {
                    continue;
                }
                bool clash = a.keys == b.keys ? a.priority == b.priority
                                              : isPrefix(a.keys, b.keys) || isPrefix(b.keys, a.keys);
                if (clash) {
                    out.emplace_back(a, b);
                }
            }
        }
        return out;
    }

private:
    using Key = std::tuple<Layer, std::string, std::string, std::string>;

    static Key key(const Binding& b)
    {
        return {b.layer, b.scope, b.commandId, b.selection};
    }

    static bool active(const Binding& b, const Context& ctx)
    {
        if (!b.selection.empty() && b.selection != ctx.selection) {
            return false;
        }
        switch (b.layer) {
            case Layer::Command:
                return !ctx.command.empty() && b.scope == ctx.command;
            case Layer::Workspace:
                return b.scope == ctx.workspace;
            case Layer::Global:
                return true;
        }
        return false;
    }

    /// Priority first, then selection-specific over generic.
    static std::pair<int, bool> rank(const Binding& b)
    {
        return {b.priority, !b.selection.empty()};
    }

    /// true when @p prefix is a strict prefix of @p keys.
    static bool isPrefix(const Keys& prefix, const Keys& keys)
    {
        return prefix.size() < keys.size() && std::equal(prefix.begin(), prefix.end(), keys.begin());
    }

    std::vector<Binding> defaults;
    std::map<Key, Keys> overrides;
};

}  // namespace Gui::Hotkeys

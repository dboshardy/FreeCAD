// SPDX-License-Identifier: LGPL-2.1-or-later
// FORK: tests for the context-layered hotkey engine (design doc §8.1).

#include <gtest/gtest.h>

#include "Gui/Hotkeys/HotkeyEngine.h"

using namespace Gui::Hotkeys;
using Status = Resolution::Status;

namespace
{

HotkeyEngine sampleEngine()
{
    HotkeyEngine e;
    e.setDefaults({
        {{"L"}, "Std_Measure", Layer::Global},
        {{"F"}, "Std_ViewFit", Layer::Global},
        {{"G", "H"}, "Std_GoHome", Layer::Global},
        {{"L"}, "Sketcher_CreateLine", Layer::Workspace, "Sketch"},
        {{"A"}, "Sketcher_LineToArc", Layer::Command, "Sketcher_CreateLine"},
        {{"F"}, "PartDesign_Flip", Layer::Command, "PartDesign_Pad"},
        {{"E"}, "Fillet_AddChain", Layer::Command, "PartDesign_Fillet", "Edge"},
    });
    return e;
}

Resolution press(const HotkeyEngine& e, Keys keys, Context ctx = {})
{
    return e.resolve(keys, ctx);
}

}  // namespace

TEST(HotkeyEngine, layersSwitchWithActiveTool)
{
    auto e = sampleEngine();
    EXPECT_EQ(press(e, {"L"}).commandId, "Std_Measure");
    EXPECT_EQ(press(e, {"L"}, {"Sketch"}).commandId, "Sketcher_CreateLine");
    EXPECT_EQ(press(e, {"F"}, {"Part", "PartDesign_Pad"}).commandId, "PartDesign_Flip");
    EXPECT_EQ(press(e, {"F"}, {"Part"}).commandId, "Std_ViewFit");
    EXPECT_EQ(press(e, {"A"}, {"Sketch"}).status, Status::None);
    EXPECT_EQ(press(e, {"A"}, {"Sketch", "Sketcher_CreateLine"}).commandId, "Sketcher_LineToArc");
}

TEST(HotkeyEngine, selectionPredicate)
{
    auto e = sampleEngine();
    EXPECT_EQ(press(e, {"E"}, {"Part", "PartDesign_Fillet", "Face"}).status, Status::None);
    EXPECT_EQ(press(e, {"E"}, {"Part", "PartDesign_Fillet", "Edge"}).commandId, "Fillet_AddChain");
}

TEST(HotkeyEngine, sequences)
{
    auto e = sampleEngine();
    EXPECT_EQ(press(e, {"G"}).status, Status::Pending);
    EXPECT_EQ(press(e, {"G", "H"}).commandId, "Std_GoHome");
    EXPECT_EQ(press(e, {"G", "X"}).status, Status::None);
}

TEST(HotkeyEngine, priorityBreaksTies)
{
    HotkeyEngine e;
    e.setDefaults({
        {{"P"}, "Low", Layer::Global, "", "", 0},
        {{"P"}, "High", Layer::Global, "", "", 5},
    });
    EXPECT_EQ(press(e, {"P"}).commandId, "High");
    EXPECT_TRUE(e.conflicts().empty());
}

TEST(HotkeyEngine, remapAndReset)
{
    auto e = sampleEngine();
    Binding fit {{}, "Std_ViewFit", Layer::Global};
    ASSERT_TRUE(e.setUserKeys(fit, {"Z"}));
    EXPECT_EQ(press(e, {"Z"}).commandId, "Std_ViewFit");
    EXPECT_EQ(press(e, {"F"}).status, Status::None);

    ASSERT_TRUE(e.setUserKeys(fit, {}));  // unbind
    EXPECT_EQ(press(e, {"Z"}).status, Status::None);

    e.reset(fit);
    EXPECT_EQ(press(e, {"F"}).commandId, "Std_ViewFit");

    EXPECT_FALSE(e.setUserKeys({{}, "No_Such_Command"}, {"Q"}));
}

TEST(HotkeyEngine, innermostLayerForStrip)
{
    auto e = sampleEngine();
    auto ids = [&](Context ctx) {
        std::vector<std::string> out;
        for (const auto& b : e.innermostLayer(ctx)) {
            out.push_back(b.commandId);
        }
        return out;
    };
    using V = std::vector<std::string>;
    EXPECT_EQ(ids({"Sketch", "Sketcher_CreateLine"}), V {"Sketcher_LineToArc"});
    EXPECT_EQ(ids({"Sketch"}), V {"Sketcher_CreateLine"});
    EXPECT_EQ(ids({"Part"}), (V {"Std_Measure", "Std_ViewFit", "Std_GoHome"}));
    // Selection-scoped binding hidden until the selection matches; falls back to Global.
    EXPECT_EQ(ids({"Part", "PartDesign_Fillet"}).size(), 3u);
}

TEST(ToolStack, innermostNamedToolIsActive)
{
    ToolStack s;
    int sketch = 0, line = 0, dialog = 0;
    EXPECT_EQ(s.active(), "");
    s.start(&sketch, "Sketcher_EditSketch");
    s.start(&line, "Sketcher_CreateLine");
    EXPECT_EQ(s.active(), "Sketcher_CreateLine");
    s.start(&dialog, "");  // opened without a command: does not hide the line tool
    EXPECT_EQ(s.active(), "Sketcher_CreateLine");
    s.finish(&line);
    EXPECT_EQ(s.active(), "Sketcher_EditSketch");
    s.finish(&sketch);
    s.finish(&dialog);
    EXPECT_EQ(s.active(), "");
}

TEST(SelectionType, stripsPathAndIndex)
{
    EXPECT_EQ(selectionType("Edge12"), "Edge");
    EXPECT_EQ(selectionType("Body.Pad.Face3"), "Face");
    EXPECT_EQ(selectionType(""), "");
    EXPECT_EQ(selectionType("Body."), "");
    EXPECT_EQ(selectionType("42"), "");
}

TEST(HotkeyEngine, conflictsPerLayer)
{
    auto e = sampleEngine();
    EXPECT_TRUE(e.conflicts().empty());  // same keys in different layers is not a conflict

    e.setUserKeys({{}, "Std_ViewFit", Layer::Global}, {"L"});
    ASSERT_EQ(e.conflicts().size(), 1u);  // same layer, same keys, same priority

    e.resetAll();
    e.setUserKeys({{}, "Std_ViewFit", Layer::Global}, {"G"});
    ASSERT_EQ(e.conflicts().size(), 1u);  // "G" shadows "G H"
}

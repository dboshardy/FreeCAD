# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs in stock FreeCAD: FreeCADCmd -t TestUx."""

import unittest

import Palette

ENTRIES = [("Std_New", "&New"), ("Std_Open", "&Open..."), ("Sketcher_CreateLine", "Create line"),
           ("PartDesign_Pad", "Pad")]


class TestPalette(unittest.TestCase):
    def test_all_words_must_match(self):
        self.assertEqual(Palette.search(ENTRIES, "create line"), [("Sketcher_CreateLine", "Create line")])

    def test_matches_command_name(self):
        self.assertEqual([n for n, _ in Palette.search(ENTRIES, "pad")], ["PartDesign_Pad"])

    def test_prefix_ranked_first(self):
        self.assertEqual(Palette.search(ENTRIES, "o")[0][0], "Std_Open")

    def test_empty_query_lists_all(self):
        self.assertEqual(len(Palette.search(ENTRIES, "")), len(ENTRIES))

    def test_label_matches_before_name_only_matches(self):
        entries = [("Sketcher_CreateBSpline", "B-Spline"), ("Sketcher_CreateLine", "Line")]
        self.assertEqual(Palette.search(entries, "create line")[0][0], "Sketcher_CreateLine")
        self.assertEqual(Palette.search(entries, "line")[0][0], "Sketcher_CreateLine")

    def test_no_match(self):
        self.assertEqual(Palette.search(ENTRIES, "zzz"), [])


import Hotkeys

B = [
    {"layer": "global", "workbench": None, "dialog": None, "key": "M", "command": "Std_Measure"},
    {"layer": "workspace", "workbench": "SketcherWorkbench", "dialog": None, "key": "M", "command": "Sketcher_Mirror"},
]


class TestHotkeys(unittest.TestCase):
    def test_workspace_beats_global(self):
        self.assertEqual(Hotkeys.resolve(B, "SketcherWorkbench", "M"), "Sketcher_Mirror")

    def test_global_fallback(self):
        self.assertEqual(Hotkeys.resolve(B, "PartDesignWorkbench", "M"), "Std_Measure")

    def test_no_match(self):
        self.assertIsNone(Hotkeys.resolve(B, "PartDesignWorkbench", "Q"))

    def test_dialog_layer_beats_workspace(self):
        b = B + [{"layer": "dialog", "workbench": None, "dialog": "Pad", "key": "M", "command": "Std_Undo"}]
        self.assertEqual(Hotkeys.resolve(b, "SketcherWorkbench", "M", ["Pad Parameters"]), "Std_Undo")
        self.assertEqual(Hotkeys.resolve(b, "SketcherWorkbench", "M", ["Pocket Parameters"]), "Sketcher_Mirror")
        self.assertEqual(Hotkeys.resolve(b, "SketcherWorkbench", "M"), "Sketcher_Mirror")  # no dialog open

    def test_dialog_star_matches_any_dialog(self):
        b = [{"layer": "dialog", "workbench": None, "dialog": "*", "key": "Z", "command": "Std_Undo"}]
        self.assertEqual(Hotkeys.resolve(b, None, "Z", ["Anything"]), "Std_Undo")
        self.assertIsNone(Hotkeys.resolve(b, None, "Z"))

    def test_dialog_binding_needs_a_title(self):
        with self.assertRaises(ValueError):
            Hotkeys.parse('{"bindings":[{"layer":"dialog","key":"A","command":"c"}]}')

    def test_roundtrip(self):
        self.assertEqual(Hotkeys.parse(Hotkeys.dump(B)), B)

    def test_rejects_bad_layer(self):
        with self.assertRaises(ValueError):
            Hotkeys.parse('{"bindings":[{"layer":"x","key":"A","command":"c"}]}')

    def test_rejects_workspace_without_workbench(self):
        with self.assertRaises(ValueError):
            Hotkeys.parse('{"bindings":[{"layer":"workspace","key":"A","command":"c"}]}')

    def test_conflict(self):
        self.assertEqual(len(Hotkeys.conflicts(B + [dict(B[0], command="Other")])), 1)
        self.assertEqual(Hotkeys.conflicts(B), [])


import Strip


class TestStrip(unittest.TestCase):
    def test_workspace_first_and_short_names(self):
        self.assertEqual(Strip.text(B), "M Mirror  |  M Measure")

    def test_limit(self):
        many = [dict(B[0], key=str(i)) for i in range(10)]
        self.assertTrue(Strip.text(many).endswith("(+2)"))

    def test_empty(self):
        self.assertEqual(Strip.text([]), "no hotkeys bound")


import Radial
import Suggest


class TestRadial(unittest.TestCase):
    def test_workbench_list_then_default_then_builtin(self):
        radial = {"default": ["A"], "PartDesignWorkbench": ["B", "C"]}
        self.assertEqual(Radial.commands_for(radial, "PartDesignWorkbench"), ["B", "C"])
        self.assertEqual(Radial.commands_for(radial, "SketcherWorkbench"), ["A"])
        self.assertEqual(Radial.commands_for({}, "X"), Radial.DEFAULT)
        self.assertEqual(len(Radial.commands_for({"default": list("ABCDEFGHIJ")}, "X")), 8)

    def test_positions_clockwise_from_the_top(self):
        self.assertEqual(Radial.positions(4, 100), [(0, -100), (100, 0), (0, 100), (-100, 0)])

    def test_parse_radial_limits(self):
        self.assertEqual(Hotkeys.parse_radial('{"radial": {"default": ["A"]}}'), {"default": ["A"]})
        with self.assertRaises(ValueError):
            Hotkeys.parse_radial('{"radial": {"default": ["a","b","c","d","e","f","g","h","i"]}}')

    def test_dump_keeps_radial(self):
        text = Hotkeys.dump(B, {"default": ["A"]})
        self.assertEqual(Hotkeys.parse(text), B)
        self.assertEqual(Hotkeys.parse_radial(text), {"default": ["A"]})


class TestSuggest(unittest.TestCase):
    def test_after_a_sketch(self):
        self.assertEqual(Suggest.after("Sketcher::SketchObject")[0], "PartDesign_Pad")

    def test_unknown_type_has_none(self):
        self.assertEqual(Suggest.after("App::Origin"), [])

    def test_limit(self):
        self.assertEqual(len(Suggest.after("Sketcher::SketchObject", 2)), 2)

    def test_strip_next_text(self):
        self.assertEqual(Strip.next_text(["Pad", "Pocket"]), "Next: Alt+1 Pad  Alt+2 Pocket")
        self.assertEqual(Strip.next_text([]), "")


import os


class TestProfile(unittest.TestCase):
    def test_design_doc_profile_parses_without_conflicts(self):
        path = os.path.join(os.path.dirname(os.path.abspath(Hotkeys.__file__)), "profiles", "design-doc-keymap.json")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        bindings = Hotkeys.parse(text)
        self.assertGreater(len(bindings), 15)
        self.assertEqual(Hotkeys.conflicts(bindings), [])
        self.assertTrue(Hotkeys.parse_radial(text)["SketcherWorkbench"])

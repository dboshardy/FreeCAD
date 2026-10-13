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

    def test_no_match(self):
        self.assertEqual(Palette.search(ENTRIES, "zzz"), [])


import Hotkeys

B = [
    {"layer": "global", "workbench": None, "key": "M", "command": "Std_Measure"},
    {"layer": "workspace", "workbench": "SketcherWorkbench", "key": "M", "command": "Sketcher_Mirror"},
]


class TestHotkeys(unittest.TestCase):
    def test_workspace_beats_global(self):
        self.assertEqual(Hotkeys.resolve(B, "SketcherWorkbench", "M"), "Sketcher_Mirror")

    def test_global_fallback(self):
        self.assertEqual(Hotkeys.resolve(B, "PartDesignWorkbench", "M"), "Std_Measure")

    def test_no_match(self):
        self.assertIsNone(Hotkeys.resolve(B, "PartDesignWorkbench", "Q"))

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

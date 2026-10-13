# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: tests for the Construction workbench core. Run inside the app via the
# test runner (registered in Init.py) or standalone: python3 TestConstruction.py

import itertools
from collections import Counter
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Build  # noqa: E402
import Cabinet  # noqa: E402
import Checks  # noqa: E402
import CutList  # noqa: E402
import Framing  # noqa: E402
import Joinery  # noqa: E402
import Library  # noqa: E402
import Member  # noqa: E402
import Parts  # noqa: E402
import Room  # noqa: E402
import Sheathing  # noqa: E402
import Shed  # noqa: E402

FRONT_ROLES = ("door", "drawer_front", "filler", "blind_panel")


def bbox(parts):
    lo = [min(p.pos[i] for p in parts) for i in range(3)]
    hi = [max(p.pos[i] + p.size[i] for p in parts) for i in range(3)]
    return lo, hi


def overlaps(a, b):
    return all(
        a.pos[i] < b.pos[i] + b.size[i] - 1e-9 and b.pos[i] < a.pos[i] + a.size[i] - 1e-9
        for i in range(3)
    )


def assert_no_overlap(test, parts):
    for a, b in itertools.combinations(parts, 2):
        test.assertFalse(overlaps(a, b), f"{a.name} overlaps {b.name}")


class TestCabinet(unittest.TestCase):
    def test_carcass_fills_outer_size(self):
        for kind in Cabinet.KINDS:
            c = Cabinet.defaults(kind)
            c.width = 800
            body = [p for p in c.parts() if p.role not in FRONT_ROLES]
            lo, hi = bbox(body)
            self.assertEqual(lo, [0, 0, 0], kind)
            self.assertEqual(hi, [800, c.depth, c.height], kind)

    def test_no_parts_overlap(self):
        for kind, fronts, width, shelves in itertools.product(
            Cabinet.KINDS, Cabinet.FRONTS, (450, 600, 900), (0, 1, 3)
        ):
            c = Cabinet.defaults(kind)
            c.fronts, c.width, c.shelves = fronts, width, shelves
            with self.subTest(kind=kind, fronts=fronts, width=width, shelves=shelves):
                assert_no_overlap(self, c.parts())

    def test_presets_build_without_overlap(self):
        for preset in Cabinet.PRESETS:
            with self.subTest(preset=preset):
                parts = Cabinet.defaults(preset).parts()
                assert_no_overlap(self, parts)
                lo, hi = bbox([p for p in parts if p.role not in FRONT_ROLES])
                c = Cabinet.defaults(preset)
                self.assertEqual(hi, [c.width, c.depth, c.height])

    def test_sink_is_open_for_plumbing(self):
        names = [p.name for p in Cabinet.defaults("sink").parts()]
        self.assertNotIn("Back", names)
        self.assertNotIn("Back stretcher", names)
        self.assertIn("Front stretcher", names)
        self.assertIn("False front", names)
        self.assertFalse([n for n in names if n.startswith(("Shelf", "Drawer"))])

    def test_blind_corner_fronts(self):
        for side in Cabinet.BLIND_SIDES:
            c = Cabinet.Cabinet(width=1000, blind_width=600, blind_side=side)
            parts = c.parts()
            fronts = [p for p in parts if p.role in ("door", "blind_panel")]
            covered = sum(p.size[0] for p in fronts) + c.door_gap * (len(fronts) - 0.5)
            self.assertAlmostEqual(covered, 1000, msg=side)
            blind = next(p for p in parts if p.role == "blind_panel")
            door = next(p for p in parts if p.role == "door")
            if side == "left":
                self.assertEqual(blind.pos[0], 0)  # flush with the blind edge
                self.assertGreater(door.pos[0], blind.pos[0] + blind.size[0])
            else:
                self.assertAlmostEqual(blind.pos[0] + blind.size[0], 1000)
                self.assertLess(door.pos[0] + door.size[0], blind.pos[0])
            assert_no_overlap(self, parts)
        self.assertEqual(Cabinet.Cabinet(width=1000, blind_width=600).door_count(), 1)

    def test_wall_and_tall_have_full_top(self):
        for kind in ("wall", "tall"):
            names = [p.name for p in Cabinet.defaults(kind).parts()]
            self.assertIn("Top", names)
            self.assertNotIn("Front stretcher", names)
        self.assertNotIn("Kick board", [p.name for p in Cabinet.defaults("wall").parts()])

    def test_doors_cover_width_with_gaps(self):
        for width, count in ((450, 1), (600, 1), (601, 2), (1000, 2)):
            c = Cabinet.Cabinet(width=width)
            doors = [p for p in c.parts() if p.role == "door"]
            self.assertEqual(len(doors), count)
            total = sum(d.size[0] for d in doors) + c.door_gap * count
            self.assertAlmostEqual(total, width)
            self.assertAlmostEqual(doors[0].pos[0], c.door_gap / 2)

    def test_fronts_cover_height_with_gaps(self):
        for fronts in Cabinet.FRONTS:
            c = Cabinet.Cabinet(fronts=fronts, drawers=4)
            parts = [p for p in c.parts() if p.role in ("door", "drawer_front")]
            rows = {(p.pos[2], p.size[2]) for p in parts}  # one row per height band
            covered = sum(h for _, h in rows) + c.door_gap * len(rows)
            self.assertAlmostEqual(covered, c.carcass_height(), msg=fronts)

    def test_drawer_bank(self):
        c = Cabinet.Cabinet(fronts="drawers", drawers=3, width=600, depth=580)
        parts = c.parts()
        self.assertEqual(len([p for p in parts if p.role == "drawer_front"]), 3)
        self.assertFalse([p for p in parts if p.name.startswith("Shelf")])
        bottoms = [p for p in parts if p.role == "drawer_bottom"]
        # Box width = inner width - 2 x slide clearance; depth in 50 mm slide steps.
        self.assertAlmostEqual(bottoms[0].size[0], 600 - 2 * 18 - 2 * 13)
        self.assertEqual(bottoms[0].size[1], 550)  # 574 carcass - 10 rear -> 550 slide

    def test_rejects_impossible_sizes(self):
        for kwargs in (
            {"width": 30},
            {"height": 120},
            {"depth": 100},
            {"thickness": 0},
            {"shelves": -1},
            {"shelves": 40},
            {"door_gap": 700},
            {"plinth_setback": 600},
            {"kind": "corner"},
            {"fronts": "glass"},
            {"fronts": "drawers", "drawers": 0},
            {"fronts": "drawers", "drawers": 12},
            {"fronts": "drawers", "depth": 260},
            {"fronts": "drawer_over_doors", "drawer_front_height": 900},
            {"blind_width": 300, "fronts": "drawers"},
            {"blind_width": 599},
            {"blind_width": -1},
            {"blind_width": 200, "blind_side": "top"},
        ):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                Cabinet.Cabinet(**kwargs).parts()

    def test_cut_size_follows_grain(self):
        side = Parts.Part("Side", "carcass", (18, 574, 770), (0, 0, 0), "z")
        self.assertEqual(side.cut_size(), (770, 574, 18))
        shelf = Parts.Part("Shelf", "carcass", (562, 554, 18), (0, 0, 0), "x")
        self.assertEqual(shelf.cut_size(), (562, 554, 18))  # grain along the shorter side kept
        mdf = Parts.Part("Panel", "carcass", (300, 18, 500), (0, 0, 0), None)
        self.assertEqual(mdf.cut_size(), (500, 300, 18))


class TestRun(unittest.TestCase):
    def test_fill_widths_minimises_filler_then_count(self):
        self.assertEqual(sum(Cabinet.fill_widths(2400)), 2400)
        self.assertEqual(len(Cabinet.fill_widths(2400)), 3)
        self.assertEqual(Cabinet.fill_widths(1350), [900, 450])
        self.assertEqual(sum(Cabinet.fill_widths(2475)), 2450)  # all sizes are 50 mm steps
        self.assertEqual(Cabinet.fill_widths(250), [])
        self.assertEqual(Cabinet.fill_widths(700, (600, 350)), [350, 350])  # not 600 + 100 filler

    def test_layout_and_fillers(self):
        run = Cabinet.Run(Cabinet.Cabinet(), length=2475)
        widths, left, right = run.layout()
        self.assertAlmostEqual(sum(widths) + left + right, 2475)
        self.assertAlmostEqual(left, right)
        run.filler_side = "right"
        self.assertEqual(run.layout()[1], 0)
        run.widths = (600, 600)
        self.assertEqual(run.layout(), ([600, 600], 0.0, 1275.0))
        run.widths = (1500, 1000)
        with self.assertRaises(ValueError):
            run.layout()

    def test_run_parts_span_length_without_overlap(self):
        for fronts in Cabinet.FRONTS:
            template = Cabinet.Cabinet(fronts=fronts)
            parts = Cabinet.Run(template, length=2475).parts()
            lo, hi = bbox(parts)
            self.assertAlmostEqual(lo[0], 0)
            self.assertAlmostEqual(hi[0], 2475)
            assert_no_overlap(self, parts)

    def test_per_cabinet_styles(self):
        run = Cabinet.Run(
            Cabinet.Cabinet(),
            length=3100,
            widths=(1000, 600, 800, 600),
            styles=("blind_left", "drawers", "sink"),
            filler_side="both",
        )
        widths, left, right = run.layout()
        self.assertEqual((left, right), (0.0, 100.0))  # blind corner stays in the corner
        parts = run.parts()
        assert_no_overlap(self, parts)
        names = [p.name for p in parts]
        self.assertEqual(names.count("Blind panel"), 1)
        self.assertEqual(names.count("False front"), 1)
        self.assertEqual(len([p for p in parts if p.role == "drawer_front"]), 3 + 1)
        backs = [p for p in parts if p.name == "Back"]
        self.assertEqual(len(backs), 3)  # the sink has none
        blind = next(p for p in parts if p.role == "blind_panel")
        self.assertEqual(blind.pos[0], 0)

    def test_parse_entries(self):
        self.assertEqual(
            Cabinet.parse_entries("1000 blind_left, 600 drawers; 800 sink, 600"),
            ((1000.0, 600.0, 800.0, 600.0), ("blind_left", "drawers", "sink")),
        )
        self.assertEqual(Cabinet.parse_entries(" 600, , 450 "), ((600.0, 450.0), ()))
        self.assertEqual(Cabinet.parse_entries(""), ((), ()))
        for text, allow in (
            ("wide", True),
            ("600 drawers extra", True),
            ("600 glass", True),
            ("-300", True),
            ("600 drawers", False),
        ):
            with self.assertRaises(ValueError, msg=text):
                Cabinet.parse_entries(text, allow)

    def test_rejects_bad_runs(self):
        for kwargs in (
            {"length": 0},
            {"length": 250},
            {"filler_side": "middle"},
            {"widths": (600,), "styles": ("glass",)},
            {"styles": ("drawers",)},  # styles without widths
            {"widths": (1000, 1000), "styles": ("blind_left", "blind_right")},  # 400 left over
        ):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                Cabinet.Run(Cabinet.Cabinet(), **kwargs).parts()
        with self.assertRaises(ValueError):  # sinks only in base runs
            Cabinet.Run(Cabinet.defaults("wall"), widths=(600,), styles=("sink",)).parts()


class TestCutList(unittest.TestCase):
    def test_row_numbers_tag_each_part(self):
        parts = [("ply", p) for p in Cabinet.Cabinet(width=600, shelves=0).parts()]
        rows = CutList.rows(parts)
        tags = CutList.row_numbers(parts)
        self.assertEqual(len(tags), len(parts))
        for (material, part), tag in zip(parts, tags):
            row = rows[tag - 1]
            self.assertEqual((row[0], row[2]), (material, round(part.cut_size()[0], 1)))
        sides = [tag for (_, p), tag in zip(parts, tags) if p.name.endswith("side")]
        self.assertEqual(len(set(sides)), 1)  # both sides share a tag

    def test_groups_identical_parts(self):
        parts = Cabinet.Cabinet(width=600, shelves=0).parts()
        rows = CutList.rows(("ply", p) for p in parts)
        sides = [r for r in rows if r[1] == "Left side"]
        self.assertEqual(len(sides), 1)
        self.assertEqual(sides[0][6], 2)  # left and right side share a row
        self.assertEqual(sum(r[6] for r in rows), len(parts))


def check_layout(test, sheets, sheet_w, sheet_h, kerf, trim):
    """Every part inside the trimmed sheet and at least one kerf from the others."""
    for placed in sheets:
        for p in placed:
            test.assertGreaterEqual(p.x, trim - 1e-6, p.name)
            test.assertGreaterEqual(p.y, trim - 1e-6, p.name)
            test.assertLessEqual(p.x + p.w, sheet_w - trim + 1e-6, p.name)
            test.assertLessEqual(p.y + p.h, sheet_h - trim + 1e-6, p.name)
        for a, b in itertools.combinations(placed, 2):
            apart = (
                a.x + a.w + kerf <= b.x + 1e-6
                or b.x + b.w + kerf <= a.x + 1e-6
                or a.y + a.h + kerf <= b.y + 1e-6
                or b.y + b.h + kerf <= a.y + 1e-6
            )
            test.assertTrue(apart, f"{a.name} and {b.name} closer than the kerf")


class TestSheetLayout(unittest.TestCase):
    def test_exact_fit_and_kerf(self):
        squares = [(f"P{i}", 500, 500, False) for i in range(8)]
        sheets = CutList.layout_sheets(squares, 1000, 2000, kerf=0, trim=0)
        self.assertEqual(len(sheets), 1)
        check_layout(self, sheets, 1000, 2000, 0, 0)
        sheets = CutList.layout_sheets(squares, 1000, 2000, kerf=3, trim=0)
        # 503 mm per square with the kerf: 1 across 1003, 3 along 2003 -> 3 per sheet.
        self.assertEqual(len(sheets), 3)
        check_layout(self, sheets, 1000, 2000, 3, 0)

    def test_grain_stays_along_sheet(self):
        # Sheet 2000 across, 1000 along its length (grain).
        with self.assertRaises(ValueError):
            CutList.layout_sheets([("Side", 1500, 300, True)], 2000, 1000, kerf=3, trim=10)
        sheets = CutList.layout_sheets([("Shelf", 1500, 300, False)], 2000, 1000, kerf=3, trim=10)
        self.assertTrue(sheets[0][0].rotated)
        sheets = CutList.layout_sheets([("Side", 900, 300, True)], 2000, 1000, kerf=3, trim=10)
        self.assertFalse(sheets[0][0].rotated)
        self.assertEqual(sheets[0][0].h, 900)

    def test_rejects_oversize_part(self):
        with self.assertRaises(ValueError):
            CutList.layout_sheets([("Top", 2500, 600, False)], 1220, 2440)

    def test_cabinet_run_layout(self):
        parts = Cabinet.Run(Cabinet.Cabinet(fronts="drawer_over_doors"), length=2400).parts()
        cut = CutList.rows(("ply", p) for p in parts if p.role not in ("back", "drawer_bottom"))
        pieces = CutList.pieces(cut, "ply")
        self.assertEqual(len(pieces), sum(r[6] for r in cut))
        sheets = CutList.layout_sheets(pieces, 1220, 2440, kerf=3.2, trim=10)
        check_layout(self, sheets, 1220, 2440, 3.2, 10)
        self.assertEqual(sum(len(s) for s in sheets), len(pieces))
        area = sum(length * width for _, length, width, _ in pieces)
        self.assertLess(len(sheets), area / (1200 * 2420) + 2)  # within one sheet of the bound


class TestHardware(unittest.TestCase):
    def test_hinges_by_height(self):
        hinge = Joinery.rule(Library.load()["joint.concealed_hinge"], "Side", "Door")
        for height, count in ((700, 2), (900, 2), (901, 3), (2400, 5), (2401, 6), (2900, 7)):
            # One more per started 400 mm beyond the table.
            self.assertEqual(Joinery.fastener_count(hinge, height), count, height)

    def test_cabinet_hardware(self):
        items = Library.load()
        c = Cabinet.Cabinet(width=800, fronts="drawer_over_doors", shelves=1)
        hw = dict(CutList.hardware(items, fasteners=c.joined(items).fasteners))
        self.assertEqual(hw[items["hardware.hinge"]["name"]], 4)  # 2 doors x 2 hinges
        self.assertEqual(hw[items["hardware.shelf_pin"]["name"]], 4)
        self.assertEqual(hw[items["hardware.drawer_slide"]["name"] + ", 550 mm"], 1)
        # Confirmat, 50 from the ends, at most 200 apart: bottom 574 deep -> 474 between
        # the end screws -> 4; a 100 mm stretcher leaves none between -> 1. Both sides:
        # 2 x (4 + 1 + 1) = 12.
        self.assertEqual(hw[items["hardware.confirmat_7x50"]["name"]], 12)
        # Back nailed at most 150 apart, 25 from the ends: sides 770 -> 6 each; bottom and
        # back stretcher 764 -> 6 each.
        self.assertEqual(hw[items["hardware.brad_nail"]["name"]], 24)
        tall = Cabinet.defaults("tall")  # one 2000 mm door: 4 hinges
        tall_hw = dict(CutList.hardware(items, fasteners=tall.joined(items).fasteners))
        self.assertEqual(tall_hw[items["hardware.hinge"]["name"]], 4)
        # A blind corner's single door hangs from the side away from the blind panel.
        corner = Cabinet.defaults("corner")
        joined = corner.joined(items)
        door = next(i for i, p in enumerate(joined.boxes) if p.name == "Door")
        self.assertIn((door, "2 hinge cups, 35 mm"), joined.operations)

    def test_carcass_joint_choice(self):
        items = Library.load()
        dado = Cabinet.Cabinet(carcass_joint="joint.dado")
        bottom = next(p for p in dado.joined(items).boxes if p.name == "Bottom")
        self.assertEqual(bottom.size[0], dado.inner_width() + 2 * 6)  # 6 mm into each side

    def test_edge_banding(self):
        items = Library.load()
        c = Cabinet.Cabinet()  # 600 base, one door, one shelf
        joined = c.joined(items)
        door = next(p for p in joined.boxes if p.name == "Door")
        self.assertEqual(door.operations.count("edge band 597"), 2)
        self.assertEqual(door.operations.count("edge band 767"), 2)
        # Sides 2 x 770, bottom 564, shelf 562, door 2 x 597 + 2 x 767 = 5394 mm,
        # 8 edges + 50 mm each to trim = 5794 -> 5.8 m.
        self.assertEqual(joined.fasteners["hardware.edge_banding"], 5.8)
        stretcher = next(p for p in joined.boxes if p.name == "Front stretcher")
        self.assertFalse([op for op in stretcher.operations if op.startswith("edge band")])
        bare = Cabinet.Cabinet(edge_banding=False).joined(items)
        self.assertNotIn("hardware.edge_banding", bare.fasteners)

    def test_shaker_doors(self):
        items = Library.load()
        c = Cabinet.Cabinet(door_style="shaker")  # 600 base: one 597 x 767 door
        joined = c.joined(items)
        door = {p.name: p for p in joined.boxes if p.name.startswith("Door")}
        self.assertEqual(sorted(door), ["Door panel", "Door rail", "Door stile"])
        rail, panel = door["Door rail"], door["Door panel"]
        self.assertEqual(rail.size[0], 597 - 2 * 60)  # between the stiles, doweled
        # The panel is housed 10 mm into the rails and stiles.
        self.assertEqual((panel.size[0], panel.size[2]), (477 + 20, 647 + 20))
        self.assertEqual(panel.size[1], c.back_thickness)
        hw = dict(CutList.hardware(items, fasteners=joined.fasteners))
        self.assertEqual(hw[items["hardware.hinge"]["name"]], 2)  # on the stile
        self.assertNotIn("edge band", " ".join(rail.operations))
        with self.assertRaises(ValueError):  # 247 mm door, 2 x 120 frame + groove
            Cabinet.Cabinet(door_style="shaker", width=250, frame_width=120).parts()

    def test_run_joins_each_cabinet(self):
        items = Library.load()
        run = Cabinet.Run(Cabinet.Cabinet(), length=1200, widths=[600, 600])
        hw = dict(CutList.hardware(items, fasteners=run.joined(items).fasteners))
        self.assertEqual(hw[items["hardware.hinge"]["name"]], 4)  # 1 door each, 2 hinges


class TestQuantities(unittest.TestCase):
    ITEMS = Library.load()

    def test_board_feet_and_volume(self):
        two_by_four = self.ITEMS["lumber.us.2x4"]
        # Sold by nominal size: 2 x 4 x 96 in / 144 = 5.33 board feet.
        self.assertAlmostEqual(CutList.board_feet(two_by_four, 8 * 304.8), 16 / 3)
        stud = self.ITEMS["lumber.metric.45x95"]
        self.assertAlmostEqual(CutList.volume_m3(stud, 3000), 0.045 * 0.095 * 3)

    def test_price(self):
        board = {**self.ITEMS["lumber.metric.45x95"], "price": 2.5, "price_per": "m"}
        self.assertAlmostEqual(CutList.price(board, 4, 3000), 30)  # 4 x 3 m x 2.5
        sheet = {**self.ITEMS["sheet.metric.plywood.18"], "price": 40}
        self.assertEqual(CutList.price(sheet, 3), 120)
        self.assertIsNone(CutList.price(self.ITEMS["sheet.metric.plywood.18"], 3))
        oak = {**self.ITEMS["lumber.us.2x4"], "price": 3, "price_per": "board_foot"}
        self.assertAlmostEqual(CutList.price(oak, 3, 8 * 304.8), 48)
        nails = {**self.ITEMS["hardware.nail_framing"], "price": 0.02}
        items = {**self.ITEMS, "hardware.nail_framing": nails}
        costs = CutList.hardware_costs(items, 1, {"hardware.nail_framing": 100})
        self.assertAlmostEqual(costs[nails["name"]], 2)
        self.assertIsNone(costs[items["hardware.wall_anchor"]["name"]])  # no price

    def test_covering_units(self):
        shingles = self.ITEMS["area.roofing.asphalt_shingles"]
        # 30 m² + 15 % waste = 34.5 m² at 3.1 m² a bundle -> 11.1 -> 12 bundles.
        self.assertEqual(CutList.covering_units(shingles, 30), 12)
        self.assertEqual(CutList.covering_units({"coverage_m2": 10, "waste": 0}, 20), 2)


class TestLibraryEditing(unittest.TestCase):
    def test_rows_csv_and_user_items(self):
        import tempfile

        items = Library.load()
        rows = Library.to_rows(items, Library.LUMBER)
        mine = [
            "lumber.mine.oak.25x150",
            "Oak 25x150",
            "25",
            "150",
            "mm",
            "1800 2400",
            "12.5",
            "m",
            "metric",
        ]
        new = Library.from_rows(rows + [mine], Library.LUMBER, items)
        user = Library.changed(new, items)
        self.assertEqual([i["id"] for i in user], ["lumber.mine.oak.25x150"])
        oak = user[0]
        self.assertEqual(oak["actual"], {"w": 25.0, "h": 150.0, "unit": "mm"})
        self.assertEqual((oak["stock_lengths_mm"], oak["price"]), ([1800.0, 2400.0], 12.5))
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "lumber.csv")
        Library.write_csv(path, {i["id"]: i for i in new}, Library.LUMBER)
        read = {r[0]: r for r in Library.read_csv(path, Library.LUMBER)}
        self.assertEqual(read[mine[0]][:2], mine[:2])
        Library.write_user_file(os.path.join(folder, "user", "lumber.json"), user)
        self.assertEqual(Library.load([folder])["lumber.mine.oak.25x150"]["name"], "Oak 25x150")
        with self.assertRaises(ValueError):
            Library.from_rows([["x", "", "1", "2", "mm", "", "", "", "metric"]], Library.LUMBER)
        with self.assertRaises(ValueError):
            Library.from_rows(
                [["x", "X", "thick", "2", "mm", "", "", "", "metric"]], Library.LUMBER
            )
        sheets = Library.to_rows(items, Library.SHEET_GOODS)
        mdf = next(r for r in sheets if r[0] == "sheet.us.mdf.3-4")
        self.assertEqual(mdf[6], "none")  # no grain: turns freely in layouts


class TestMember(unittest.TestCase):
    def assertVec(self, a, b):
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y)

    def test_conventions(self):
        # Joist along X stands on edge: depth up, thickness across.
        length, x, y, z = Member.frame((0, 0, 0), (3000, 0, 0))
        self.assertAlmostEqual(length, 3000)
        self.assertVec(y, (0, 0, 1))
        self.assertVec(x, (0, 1, 0))
        # Stud: depth along Y, thickness along X (a wall running along X).
        _, x, y, z = Member.frame((0, 0, 0), (0, 0, 2400))
        self.assertVec((x, y, z), ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        # Plate: joist rolled 90 degrees lies flat.
        _, x, y, z = Member.frame((0, 0, 0), (3000, 0, 0), roll=90)
        self.assertVec(x, (0, 0, 1))

    def test_frame_is_orthonormal(self):
        for end in ((1, 2, 3), (-5, 0.1, 0), (0.001, 0, 9), (3, -4, -12)):
            _, x, y, z = Member.frame((0, 0, 0), end, roll=30)
            for a, b in itertools.combinations((x, y, z), 2):
                self.assertAlmostEqual(sum(i * j for i, j in zip(a, b)), 0)
            for a in (x, y, z):
                self.assertAlmostEqual(sum(i * i for i in a), 1)
            cross = (
                x[1] * y[2] - x[2] * y[1],
                x[2] * y[0] - x[0] * y[2],
                x[0] * y[1] - x[1] * y[0],
            )
            self.assertVec(cross, z)  # right-handed

    def test_zero_length_rejected(self):
        with self.assertRaises(ValueError):
            Member.frame((1, 1, 1), (1, 1, 1))


class TestLumberPlan(unittest.TestCase):
    def test_precut_studs_need_no_cut(self):
        boards = CutList.plan_lengths([("Stud", 2352.7)] * 8, [2352.7, 2438.4, 3048])
        self.assertEqual([b.stock for b in boards], [2352.7] * 8)

    def test_kerf_between_pieces(self):
        boards = CutList.plan_lengths([("Rail", 1200)] * 4, [2438.4], kerf=3.2)
        self.assertEqual(len(boards), 2)
        self.assertAlmostEqual(boards[0].offcut(), 2438.4 - 2403.2 - 3.2)
        boards = CutList.plan_lengths([("Rail", 1220)] * 2, [2438.4], kerf=3.2)
        self.assertEqual(len(boards), 2)  # 2440 + kerf does not fit

    def test_shortest_stock_that_holds_the_cuts(self):
        boards = CutList.plan_lengths([("Block", 1000)], [6000, 2400, 3000])
        self.assertEqual(boards[0].stock, 2400)

    def test_every_piece_placed_once(self):
        pieces = [(f"P{i}", 300 + 137 * i) for i in range(30)]
        boards = CutList.plan_lengths(pieces, [2400, 3000, 3600, 4800], kerf=3)
        placed = sorted(c for b in boards for c in b.cuts)
        self.assertEqual(placed, sorted(pieces))
        for b in boards:
            self.assertLessEqual(b.used(), b.stock + 1e-6)
        total = sum(length for _, length in pieces)
        self.assertLess(sum(b.stock for b in boards), total * 1.15)  # under 15% waste here

    def test_rejects_too_long(self):
        with self.assertRaises(ValueError):
            CutList.plan_lengths([("Ridge", 7000)], [2400, 6000])


def piece_box(piece, sections):
    """Axis-aligned bounds (lo, hi) of a framing piece. sections: name -> (w, h)."""
    w, h = sections[piece.section]
    _, x, y, z = Member.frame(piece.start, piece.end, piece.roll)
    lo, hi = [], []
    for i in range(3):
        half = abs(x[i]) * w / 2 + abs(y[i]) * h / 2
        a, b = sorted((piece.start[i], piece.end[i]))
        lo.append(a - half)
        hi.append(b + half)
    return lo, hi


def assert_pieces_apart(test, pieces, sections):
    boxes = [piece_box(p, sections) for p in pieces]
    for (pa, a), (pb, b) in itertools.combinations(zip(pieces, boxes), 2):
        test.assertFalse(boxes_overlap(a, b), f"{pa.name} {pa.start} overlaps {pb.name} {pb.start}")
    return boxes


def boxes_overlap(a, b):
    return all(a[0][i] < b[1][i] - 1e-6 and b[0][i] < a[1][i] - 1e-6 for i in range(3))


class TestFraming(unittest.TestCase):
    def check_no_overlap(self, wall):
        pieces = wall.pieces()
        boxes = assert_pieces_apart(self, pieces, {"stud": wall.stud, "header": wall.header})
        for lo, hi in boxes:  # inside the wall
            self.assertGreaterEqual(min(lo[0], lo[1], lo[2]), -1e-6)
            self.assertLessEqual(hi[0], wall.length + 1e-6)
            self.assertLessEqual(hi[1], wall.stud[1] + 1e-6)
            self.assertLessEqual(hi[2], wall.height + 1e-6)
        return pieces

    def test_plain_wall(self):
        wall = Framing.Wall(length=3600, height=2440, spacing=600, top_plates=2)
        pieces = self.check_no_overlap(wall)
        names = [p.name for p in pieces]
        self.assertEqual(names.count("Bottom plate"), 1)
        self.assertEqual(names.count("Top plate"), 2)
        studs = sorted(p.start[0] for p in pieces if p.name == "Stud")
        # Ends plus centres 600..3000; 3600 is the end stud itself.
        self.assertEqual(studs, [22.5, 600, 1200, 1800, 2400, 3000, 3577.5])
        stud = next(p for p in pieces if p.name == "Stud")
        self.assertAlmostEqual(stud.length(), 2440 - 3 * 45)

    def test_door_and_window(self):
        wall = Framing.Wall(
            length=4800,
            openings=Framing.parse_openings(
                "door 900x2100 @ 700, window 1200x1000 @ 2600 sill 900"
            ),
        )
        pieces = self.check_no_overlap(wall)
        names = [p.name for p in pieces]
        self.assertEqual(names.count("King stud"), 4)
        self.assertEqual(names.count("Jack stud"), 4)
        self.assertEqual(names.count("Header"), 2 * 2)  # 2 plies per opening in a 95 mm wall
        self.assertEqual(names.count("Sill"), 1)
        self.assertEqual(names.count("Bottom plate"), 2)  # cut at the door
        door_jack = next(p for p in pieces if p.name == "Jack stud")
        self.assertAlmostEqual(max(door_jack.start[2], door_jack.end[2]), 2100)
        # Door: one cripple at 1200 above its header. Window: 3000 and 3600, above
        # the header and below the sill.
        cripples = sorted(p.start[0] for p in pieces if p.name == "Cripple")
        self.assertEqual(cripples, [1200, 3000, 3000, 3600, 3600])
        header = next(p for p in pieces if p.name == "Header" and p.start[0] > 2000)
        self.assertAlmostEqual(header.length(), 1200 + 2 * 45)

    def test_long_wall_plates_spliced_over_studs(self):
        wall = Framing.Wall(
            length=12000,
            max_piece=4800,
            openings=Framing.parse_openings(
                "door 900x2100 @ 1000, window 1200x1000 @ 7000 sill 900"
            ),
        )
        pieces = self.check_no_overlap(wall)
        plates = [p for p in pieces if "plate" in p.name]
        self.assertTrue(all(p.length() <= 4800 + 1e-6 for p in plates))
        stud_x = {p.start[0] for p in pieces if p.name in ("Stud", "King stud", "Jack stud")}
        for name in ("Bottom plate", "Top plate"):
            for p in plates:
                if p.name == name:
                    for x in (p.start[0], p.end[0]):
                        self.assertTrue(
                            x in (0, 12000)
                            or x in stud_x
                            or any(abs(x - o) < 1e-6 for o in (1000, 1900)),
                            f"{name} joint at {x} not over a stud",
                        )
        lower = sorted(p.end[0] for p in plates if p.name == "Top plate" and p.start[2] < 2400 - 45)
        upper = sorted(p.end[0] for p in plates if p.name == "Top plate" and p.start[2] > 2400 - 45)
        for a in lower[:-1]:
            for b in upper[:-1]:
                self.assertGreaterEqual(abs(a - b), wall.spacing - 1e-6)  # staggered
        self.assertEqual(sum(p.length() for p in plates if p.name == "Top plate"), 2 * 12000)

    def test_plate_that_cannot_be_spliced(self):
        with self.assertRaises(ValueError):  # no stud within a 500 mm piece of 600 mm spacing
            Framing.Wall(length=3600, max_piece=500).pieces()

    def test_corner_studs(self):
        wall = Framing.Wall(length=3600, corners=(95, 95))
        pieces = self.check_no_overlap(wall)
        corner = sorted(p.start[0] for p in pieces if p.name == "Corner stud")
        self.assertEqual(corner, [95 + 22.5, 3600 - 95 - 22.5])  # just past the butting walls
        with self.assertRaises(ValueError):  # a door into the corner backing
            Framing.Wall(
                length=3600, corners=(95, 0), openings=Framing.parse_openings("door 900x2100 @ 150")
            ).pieces()

    def test_us_wall_16_on_centre(self):
        wall = Framing.Wall(
            length=3657.6,
            height=2438.4,
            spacing=406.4,
            stud=(38.1, 88.9),
            header=(38.1, 184.15),
            openings=Framing.parse_openings("door 914x2083 @ 1219"),
        )
        self.check_no_overlap(wall)

    def test_rejects_impossible_walls(self):
        for kwargs, text in (
            ({"length": 50}, ""),
            ({"height": 100}, ""),
            ({"spacing": 60}, ""),
            ({"top_plates": 3}, ""),
            ({}, "door 900x2100 @ 50"),  # no room for king and jack at the wall start
            ({}, "door 900x2100 @ 3000"),  # runs past the wall end
            ({}, "door 900x2100 @ 600, window 900x900 @ 1550 sill 900"),  # overlapping framing
            ({}, "window 900x900 @ 800 sill 40"),  # sill below the plate
            ({}, "door 900x2300 @ 800"),  # header hits the top plates
        ):
            with self.assertRaises(ValueError, msg=f"{kwargs} {text}"):
                Framing.Wall(openings=Framing.parse_openings(text), **kwargs).pieces()

    def test_parse_openings(self):
        self.assertEqual(
            Framing.parse_openings("Door 900x2100 @ 600; window 1200 × 1000 @ 2400 sill 900"),
            [
                Framing.Opening("door", 600, 900, 2100),
                Framing.Opening("window", 2400, 1200, 1000, 900),
            ],
        )
        self.assertEqual(Framing.parse_openings(" , "), [])
        for text in ("door 900 @ 600", "garage 900x2100 @ 600", "door 900x2100"):
            with self.assertRaises(ValueError, msg=text):
                Framing.parse_openings(text)


class TestFloor(unittest.TestCase):
    def test_slab(self):
        slab = Framing.Slab()  # 6000 x 3600 x 100, edges 300 wide, 450 deep
        # Slab 2.16 m³; edges 350 below it around a 5400 x 3000 inside: 5.4 m² x 0.35.
        self.assertAlmostEqual(slab.concrete_m3(), 2.16 + 1.89)
        self.assertEqual(Checks.slab(slab, {})[0][1], Checks.REQUIRED)
        with self.assertRaises(ValueError):
            Framing.Slab(edge_depth=50).boxes()

    def test_floor_platform(self):
        floor = Framing.Floor(length=3658, width=3048, spacing=406.4, joist=(38.1, 184.15))
        pieces = floor.pieces()
        boxes = assert_pieces_apart(self, pieces, {"joist": floor.joist})
        lo = [min(b[0][i] for b in boxes) for i in range(3)]
        hi = [max(b[1][i] for b in boxes) for i in range(3)]
        for got, want in zip(lo + hi, [0, 0, 0, 3658, 3048, 184.15]):
            self.assertAlmostEqual(got, want)
        joists = [p for p in pieces if p.name == "Joist"]
        self.assertEqual(len(joists), 2 + 8)  # ends + centres 406.4 .. 3251.2
        self.assertAlmostEqual(joists[0].length(), 3048 - 2 * 38.1)

    def test_long_rims_spliced(self):
        floor = Framing.Floor(length=9000, max_piece=4800)
        rims = [p for p in floor.pieces() if p.name == "Rim joist"]
        self.assertTrue(all(p.length() <= 4800 + 1e-6 for p in rims))
        self.assertAlmostEqual(sum(p.length() for p in rims), 2 * 9000)

    def test_rejects(self):
        for kwargs in ({"width": 7000}, {"spacing": 50}, {"length": 50}):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                Framing.Floor(**kwargs).pieces()


class TestFloorFraming(unittest.TestCase):
    def names(self, floor):
        return Counter(p.name for p in floor.pieces())

    def test_beam_and_posts(self):
        floor = Framing.Floor(length=3600, width=6000, beams=(3000,), post_height=600)
        names = self.names(floor)
        # Every joist line in two pieces, butt-joined over the beam.
        self.assertEqual(names["Joist"], 2 * len(floor.joist_centres()))
        self.assertEqual(names["Beam"], 2)  # 2 plies, 3600 in one piece
        self.assertEqual(names["Post"], 3)  # 3600 at most 1800 apart -> 2 bays
        self.assertEqual(floor.spans(), [3000 - 22.5, 3000 - 22.5])
        with self.assertRaises(ValueError):  # 5955 between rims: longer than 4800 stock
            Framing.Floor(width=6000, max_piece=4800).pieces()

    def test_opening(self):
        floor = Framing.Floor(openings=((1000, 800, 900, 1200),))
        pieces = floor.pieces()
        names = Counter(p.name for p in pieces)
        self.assertEqual(names["Trimmer"], 4)  # doubled each side
        self.assertEqual(names["Header joist"], 4)  # doubled each end, 900 long
        # Joists at 1200 and 1600 are inside the opening: 2 tails each. The joist at
        # 2000 is 32.5 from the outer trimmer and gives way to it.
        self.assertEqual(names["Tail joist"], 4)
        xs = {round(p.start[0], 1) for p in pieces if p.name == "Joist"}
        self.assertNotIn(2000, xs)
        self.assertIn(800, xs)
        tails = sorted((p.start[1], p.end[1]) for p in pieces if p.name == "Tail joist")
        self.assertEqual(tails[0], (45, 800 - 90))  # rim face to the outer header
        with self.assertRaises(ValueError):
            Framing.Floor(openings=((10, 800, 900, 1200),)).pieces()  # no room for trimmers

    def test_blocking_skips_openings(self):
        floor = Framing.Floor(blocking_rows=1, openings=((1000, 800, 900, 1200),))
        blocks = [p for p in floor.pieces() if p.name == "Blocking"]
        mid = 1500  # the row at mid-span crosses the opening (800 .. 2000)
        self.assertTrue(all(p.start[1] == mid for p in blocks))
        for p in blocks:
            self.assertFalse(p.start[0] < 1900 and p.end[0] > 1000, (p.start, p.end))
        self.assertEqual(
            Framing.parse_floor_openings("900x2400 @ 600, 300"), [(600, 300, 900, 2400)]
        )


class TestDeckOptions(unittest.TestCase):
    def test_freestanding(self):
        deck = Framing.Deck(attached=False, blocking_rows=1)
        names = Counter(p.name for p in deck.pieces())
        self.assertNotIn("Ledger", names)
        self.assertEqual(len(deck.beam_lines()), 2)
        self.assertEqual(names["Post"], 6)  # 3 posts (3600 at most 1800 apart) per beam
        joists = len(deck.joist_centres())
        self.assertEqual(names["Blocking"], joists - 1)  # one row between every pair
        # 6 footings of 400 x 400 x 600 mm = 0.576 m³.
        self.assertAlmostEqual(deck.concrete_m3(), 6 * 0.4 * 0.4 * 0.6)
        lines = deck.beam_lines()
        self.assertAlmostEqual(deck.joist_span(), lines[1] - lines[0])
        found = {c for c, _, _ in Checks.deck(deck, {})}
        self.assertNotIn("Ledger attachment", found)
        self.assertIn("Footings", found)

    def test_guards(self):
        deck = Framing.Deck(height=1200, guards=True)
        pieces = deck.pieces()
        names = Counter(p.name for p in pieces)
        # Rim side 3695 at most 1500 apart -> 4 posts; each end 3047.5 -> 4, the
        # outer corner shared: 10 posts.
        self.assertEqual(names["Guard post"], 10)
        self.assertEqual(names["Guard rail"], 3)
        # Along the rim side, no clear gap (baluster to baluster or to a post) over 100.
        h, bt = deck.post[0] / 2, deck.baluster[1]
        y = deck.projection
        edges = sorted(
            [
                (p.start[0] - h, p.start[0] + h)
                for p in pieces
                if p.name == "Guard post" and p.start[1] > y
            ]
            + [
                (p.start[0] - bt / 2, p.start[0] + bt / 2)
                for p in pieces
                if p.name == "Baluster" and p.start[1] > y - 1
            ]
        )
        gaps = [b0 - a1 for (_, a1), (b0, _) in zip(edges, edges[1:])]
        self.assertLessEqual(max(gaps), 100 + 1e-6)
        self.assertGreater(min(gaps), 0)
        rules = Library.load()["rules.generic-example"]
        checks = {c: st for c, st, _ in Checks.deck(deck, rules)}
        self.assertEqual(checks["Guards"], Checks.OK)
        self.assertEqual(checks["Guard posts"], Checks.REQUIRED)
        self.assertEqual(deck.extra_hardware(), {"hardware.guard_corner_bracket": 2})
        loose = Framing.Deck(height=1200, guards=True, max_baluster_gap=150)
        self.assertEqual(
            {c: st for c, st, _ in Checks.deck(loose, rules)}["Guards"], Checks.WARNING
        )
        free = Framing.Deck(height=1200, guards=True, attached=False)
        self.assertEqual(len(free.guard_sides()), 4)
        self.assertEqual(free.guard_corners(), 4)

    def test_floor_concrete(self):
        floor = Framing.Floor(width=6000, beams=(3000,), post_height=600)
        self.assertAlmostEqual(floor.concrete_m3(), 3 * 0.4 * 0.4 * 0.6)
        self.assertEqual(Framing.Floor().concrete_m3(), 0)


class TestShedRoof(unittest.TestCase):
    def test_rafters_and_rise(self):
        roof = Framing.ShedRoof(length=3600, span=3000, pitch=14.04, overhang=300, seat=95)
        rafters = roof.boards()
        self.assertEqual(len(rafters), 7)  # 3600 at 600: both ends plus 5
        # High wall plates (3000 - 95) x tan(14.04) above the low wall's.
        self.assertAlmostEqual(roof.rise(), 2905 * math.tan(math.radians(14.04)))
        # Along the slope: 3600 on plan / cos + the plumb cuts' corners.
        expected = 3600 / math.cos(math.radians(14.04)) + 145 * math.tan(math.radians(14.04))
        self.assertAlmostEqual(rafters[0].cut_length(), expected, places=6)
        (surface,) = Sheathing.surfaces(roof)
        self.assertAlmostEqual(surface.size[1], 3600 / math.cos(math.radians(14.04)))
        checks = {
            c: status for c, status, _ in Checks.shed_roof(roof, {"birdsmouth_max_fraction": 0.333})
        }
        self.assertEqual(checks["Birdsmouth"], Checks.OK)
        self.assertEqual(checks["High wall"], Checks.REQUIRED)
        with self.assertRaises(ValueError):
            Framing.ShedRoof(span=150).boards()


class TestLandingStair(unittest.TestCase):
    def test_landing(self):
        model = Framing.LandingStair(Framing.Stair(), landing_after=7)
        stair = model.stair
        self.assertEqual(stair.risers(), 14)  # 2600 / 190 -> 14 equal risers
        # The landing's front edge is the first flight's top riser face (6 runs).
        self.assertAlmostEqual(model.landing_y(), 6 * stair.run())
        self.assertAlmostEqual(model.landing_top(), 7 * stair.riser())
        names = Counter(p.name for p in model.pieces())
        # 6 treads of 2 boards in each flight, and 6 boards across the 900 landing:
        # 6 x 145 + 5 x 6 = 900.
        self.assertEqual(names["Tread"], 30)
        self.assertEqual(names["Landing post"], 4)
        self.assertEqual(names["Landing rail"], 2)  # both sides open
        self.assertEqual(len(model.boards()), 2 * len(stair.stringer_centres()))
        rules = Library.load()["rules.generic-example"]
        found = {c: st for c, st, _ in Checks.landing_stair(model, rules)}
        self.assertEqual(found["Landing depth"], Checks.OK)
        self.assertEqual(found["Landing guards"], Checks.REQUIRED)
        with self.assertRaises(ValueError):
            Framing.LandingStair(Framing.Stair(), landing_after=1).pieces()


class TestRoom(unittest.TestCase):
    def kitchen(self):
        # An L: 3600 along x, then 2400 along y; a window on wall 1, a range on wall 2.
        return Room.Room(
            walls=[(3600, "left"), (2400, "left")],
            openings=[(1, "window", 1200, 1000, 1200, 900)],
            gaps=[(2, "range", 900, 600)],
        )

    def test_geometry(self):
        room = self.kitchen()
        self.assertEqual(room.corners(), [(0, 0), (3600, 0), (3600, 2400)])
        self.assertFalse(room.closed())
        self.assertEqual([room.corner_kind(i) for i in range(2)], ["outside", None])
        box = Room.Room(walls=[(4000, "left"), (3000, "left"), (4000, "left"), (3000, "left")])
        self.assertTrue(box.closed())
        self.assertEqual({box.corner_kind(i) for i in range(4)}, {"outside"})
        self.assertEqual(
            Room.plan([(0, 0), (4000, 0), (4000, 3000), (0, 3000), (0, 0)]),
            [(4000, "left"), (3000, "left"), (4000, "left"), (3000, "left")],
        )
        with self.assertRaises(ValueError):
            Room.plan([(0, 0), (1000, 0), (2000, 500)])  # not square
        with self.assertRaises(ValueError):
            Room.Room(walls=[(1000, "left")], gaps=[(1, "range", 800, 600)]).validate()

    def test_framing_corners(self):
        frames = Room.Room(walls=[(4000, "left"), (3000, "left"), (4000, "left"), (3000, "left")])
        walls = frames.framing(95)
        # Every wall runs 95 through the outside corner at its end and has a
        # corner stud where the previous wall butts against it.
        self.assertEqual([w.length for _, w, _, _, _ in walls], [4095, 3095, 4095, 3095])
        self.assertEqual({w.corners for _, w, _, _, _ in walls}, {(95, 0)})
        _, _, origin, local_x, local_y = walls[1]
        self.assertEqual((origin, local_x, local_y), ((4095, 0), (0, 1), (-1, 0)))

    def test_kitchen_runs(self):
        room = self.kitchen()
        base = {w: (entries, origin, x) for w, entries, origin, x in room.runs([1, 2], 598)}
        entries, origin, x = base[1]
        # Wall 1 runs from its end (the corner) back: a 1000 blind corner cabinet first.
        self.assertEqual((origin, x), ((3600, 0), (-1, 0)))
        self.assertEqual(entries[0], (1000, "blind_left"))
        self.assertEqual(sum(w for w, _ in entries), 3600)
        entries, origin, x = base[2]
        # Wall 2: from its far end back to the corner, the range gap at 900..1500
        # and the corner's 598 left free for wall 1's blind cabinet.
        self.assertEqual(entries[1], (600, "gap"))
        self.assertEqual(entries[-1], (598, "gap"))
        self.assertEqual(sum(w for w, _ in entries), 2400)
        upper = {w: entries for w, entries, _, _ in room.runs([1], 338, upper=True)}
        self.assertIn((1200, "gap"), upper[1])  # wall cabinets stop at the window
        run = Cabinet.Run(
            Cabinet.Cabinet(), length=1000, widths=(600, 400), styles=(None, "filler")
        )
        self.assertEqual([p.name for p in run.parts()].count("Filler"), 1)


class TestGableRoof(unittest.TestCase):
    def test_geometry(self):
        roof = Framing.GableRoof(length=3600, span=3000, pitch=26.565, overhang=300)
        rafters = [b for b in roof.boards() if b.name == "Rafter"]
        self.assertEqual(len(rafters), 2 * len(roof.rafter_centres()))
        slope = math.tan(math.radians(26.565))
        self.assertAlmostEqual(roof.heel(), 95 * slope)
        near = rafters[0].profile
        self.assertAlmostEqual(max(y for y, _ in near), roof.ridge_face())
        self.assertAlmostEqual(min(y for y, _ in near), -300)
        far = rafters[1].profile
        self.assertAlmostEqual(min(y for y, _ in far), 3000 - roof.ridge_face())
        self.assertTrue(roof.ridge_face() < 1500 < 3000 - roof.ridge_face())  # ridge between
        # Seat sits on the plate: the outline touches z = 0 from y = 0 to the seat width.
        self.assertIn((0.0, 0.0), near)
        self.assertIn((95.0, 0.0), near)
        run = 300 + roof.ridge_face()
        length = rafters[0].cut_length()
        self.assertGreater(length, run / math.cos(math.radians(26.565)))
        self.assertLess(length, run / math.cos(math.radians(26.565)) + roof.plumb_depth())

    def test_ridge_and_ties(self):
        roof = Framing.GableRoof(length=3600, span=3000)
        pieces = roof.pieces()
        ridge = [p for p in pieces if p.name == "Ridge board"]
        self.assertAlmostEqual(sum(p.length() for p in ridge), 3600)
        self.assertAlmostEqual(ridge[0].start[2] + roof.ridge[1] / 2, roof.ridge_top())
        ties = [b for b in roof.boards() if b.name == "Ceiling joist"]
        self.assertEqual(len(ties), len(roof.rafter_centres()))
        for tie in ties:  # beside the rafters, not through them
            for x in roof.rafter_centres():
                self.assertGreaterEqual(abs(tie.x - x), (roof.rafter[0] + roof.tie[0]) / 2 - 1e-6)
            self.assertAlmostEqual(tie.cut_length(), 3000)
            # Corners cut to the slope: never above the rafter tops.
            for y, z in tie.profile:
                near_y = min(y, 3000 - y)
                self.assertLessEqual(z, roof.bottom(near_y) + roof.plumb_depth() + 1e-6)
        self.assertFalse(
            [b for b in Framing.GableRoof(ties=False).boards() if b.name == "Ceiling joist"]
        )

    def test_gable_studs(self):
        roof = Framing.GableRoof(length=3600, span=3000)
        studs = [b for b in roof.boards() if b.name == "Gable stud"]
        self.assertEqual(len(studs), 8)
        for stud in studs:
            self.assertIn(stud.x, (95 / 2, 3600 - 95 / 2))  # centred on the end walls
            self.assertEqual(stud.extrude, 95)  # the wall depth
            for y, z in stud.profile:
                self.assertLessEqual(z, roof.under_roof(y) + 1e-6)  # under rafters and ridge
                self.assertGreaterEqual(y, 95 - 1e-6)  # between the front and back walls
        # End ceiling joists move inside the end walls, clear of the gable studs.
        ties = sorted(b.x for b in roof.boards() if b.name == "Ceiling joist")
        self.assertEqual((ties[0], ties[-1]), (95 + 22.5, 3600 - 95 - 22.5))
        # A stud straddling the ridge stops under the ridge board.
        wide = Framing.GableRoof(length=3600, span=3000, spacing=500)
        near_end = [s for s in wide.boards() if s.name == "Gable stud" and s.x < 100]
        crossing = [
            s
            for s in near_end
            if min(y for y, _ in s.profile) < 1500 < max(y for y, _ in s.profile)
        ]
        self.assertEqual(len(crossing), 1)
        top = max(z for _, z in crossing[0].profile)
        self.assertAlmostEqual(top, wide.ridge_top() - wide.ridge[1])
        self.assertFalse(
            [b for b in Framing.GableRoof(gable_studs=False).boards() if b.name == "Gable stud"]
        )

    def test_rejects(self):
        for kwargs in (
            {"pitch": 70},
            {"seat": 400},  # birdsmouth through the rafter
            {"span": 7000},  # ties longer than stock
            {"span": 11000, "ties": False},  # rafters longer than stock
            {"spacing": 60},
        ):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                Framing.GableRoof(**kwargs).boards()


class TestSheathing(unittest.TestCase):
    def test_cover_staggered(self):
        panels = Sheathing.cover((3600, 3000), (2440, 1220))
        area = sum(du * dv for _, _, du, dv in panels)
        self.assertAlmostEqual(area, 3600 * 3000)
        rows = sorted({v for _, v, _, _ in panels})
        self.assertEqual(rows, [0, 1220, 2440])
        seams = {v: sorted(u for u, vv, _, _ in panels if vv == v and u > 0) for v in rows}
        self.assertEqual(seams[0], [2440])
        self.assertEqual(seams[1220], [1220])  # half a sheet over
        self.assertFalse(set(seams[0]) & set(seams[1220]))
        for u, v, du, dv in panels:
            self.assertLessEqual(du, 2440 + 1e-6)
            self.assertLessEqual(dv, 1220 + 1e-6)
            self.assertLessEqual(u + du, 3600 + 1e-6)
            self.assertLessEqual(v + dv, 3000 + 1e-6)

    def test_cover_upright(self):
        for stagger in (False, True):  # one sheet tall: staggering would only waste
            panels = Sheathing.cover((3600, 2440), (2440, 1220), long_along="v", stagger=stagger)
            self.assertEqual(len(panels), 3)
            self.assertEqual(panels[0], (0, 0, 1220, 2440))

    def test_surfaces_right_handed_and_sized(self):
        roof = Framing.GableRoof(length=3600, span=3000, overhang=300)
        for model in (Framing.Floor(), Framing.Wall(), roof):
            for surface in Sheathing.surfaces(model):
                n = surface.normal()
                self.assertAlmostEqual(sum(x * x for x in n), 1)
        near, far, left, right = Sheathing.surfaces(roof)
        self.assertEqual(left.normal(), (-1, 0, 0))  # gable ends face out
        self.assertEqual(right.normal(), (1, 0, 0))
        self.assertGreater(near.normal()[2], 0)  # both slopes face up and out
        self.assertLess(near.normal()[1], 0)
        self.assertGreater(far.normal()[1], 0)
        # Slope length reaches from the eave tail to the ridge line.
        self.assertAlmostEqual(near.size[1], (1500 + 300) / math.cos(math.radians(roof.pitch)))

    def test_clip_polygon(self):
        triangle = [(0, 0), (100, 0), (50, 50)]
        piece = Sheathing.clip_polygon([(0, 0), (100, 0), (100, 100), (0, 100)], triangle)
        self.assertAlmostEqual(Sheathing.area(piece), 2500)
        self.assertEqual(Sheathing.clip_polygon([(200, 0), (300, 0), (300, 50)], triangle), [])
        surface = Sheathing.Surface("t", (0, 0, 0), (1, 0, 0), (0, 0, 1), (100, 50), clip=triangle)
        self.assertEqual(Sheathing.cover_surface(surface, (100, 60)), [(0.0, 0.0, 100.0, 50.0)])

    def test_whole_sheets_need_no_layout(self):
        pieces = [("Panel", 2440, 1220, True)] * 3 + [("Cut", 1200, 600, True)]
        sheets = CutList.layout_sheets(pieces, 1220, 2440, kerf=3.2, trim=10)
        self.assertEqual(len(sheets), 4)
        self.assertEqual([len(s) for s in sheets[:3]], [1, 1, 1])


def to_world(box, component):
    """Axis-aligned box in a component's frame -> world (rotations of 90 deg)."""
    (lo, hi), (ox, oy, oz) = box, component.origin
    a = math.radians(component.rotation)
    c, s = round(math.cos(a)), round(math.sin(a))
    corners = [
        (x * c - y * s + ox, x * s + y * c + oy) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
    ]
    xs, ys = [p[0] for p in corners], [p[1] for p in corners]
    return [min(xs), min(ys), lo[2] + oz], [max(xs), max(ys), hi[2] + oz]


class TestSheathingOnFraming(unittest.TestCase):
    def test_joints_on_framing(self):
        # 1220 sheets on studs at 600: cut to 1200 so every joint is on a stud.
        wall = Sheathing.surfaces(Framing.Wall(length=3600, spacing=600))[0]
        self.assertEqual(
            [p[2] for p in Sheathing.cover_surface(wall, (2440, 1220))], [1200, 1200, 1200]
        )
        # 2440 sheets on joists at 400: end joints at 2400; staggered rows start at 1200.
        floor = Sheathing.surfaces(Framing.Floor())[0]
        joists = set(floor.supports)
        for u, v, du, dv in Sheathing.cover_surface(floor, (2440, 1220)):
            end = u + du
            self.assertTrue(end in joists or abs(end - 3600) < 1e-6, (u, du))


class TestShed(unittest.TestCase):
    """Phase 5 exit test: a 3.6 x 3.0 m gable shed, quantities against a hand count."""

    def counts(self, component):
        names = [p.name for p in component.model.pieces()]
        names += [b.name for b in getattr(component.model, "boards", list)()]
        return {n: names.count(n) for n in set(names)}

    def test_hand_count(self):
        parts = {c.name: self.counts(c) for c in Shed.Shed().components()}
        # Floor 3600 x 3000, joists at 400: ends + 400..3200 (8) = 10; 2 rims.
        self.assertEqual(parts["Floor"], {"Joist": 10, "Rim joist": 2})
        # Front 3600, studs at 600, door 900 centred (1350..2250): ends + 600, 1200,
        # 2400, 3000 (1800 falls in the door framing) = 6; kings 2, jacks 2,
        # header 2 plies, 1 cripple at 1800; bottom plate cut in 2; 2 top plates.
        self.assertEqual(
            parts["Front wall"],
            {
                "Stud": 6,
                "Corner stud": 2,
                "King stud": 2,
                "Jack stud": 2,
                "Header": 2,
                "Cripple": 1,
                "Bottom plate": 2,
                "Top plate": 2,
            },
        )
        # Back 3600: ends + 600..3000 (5) = 7.
        # Front and back also get a corner stud at each end, just inside the side
        # walls (centre 95 + 22.5 from each end).
        self.assertEqual(
            parts["Back wall"], {"Stud": 7, "Corner stud": 2, "Bottom plate": 1, "Top plate": 2}
        )
        # Sides 3000 - 2 x 95 = 2810: ends + 600..2400 (4) = 6.
        for side in ("Left wall", "Right wall"):
            self.assertEqual(parts[side], {"Stud": 6, "Bottom plate": 1, "Top plate": 2})
        # Roof 3600, rafters at 600: ends + 600..3000 (5) = 7 pairs, 7 ceiling joists.
        # Gable studs on the rafter layout across the 3000 span, between the front and
        # back walls (95..2905): 600, 1200, 1800, 2400 = 4 per end.
        self.assertEqual(
            parts["Roof"], {"Rafter": 14, "Ceiling joist": 7, "Ridge board": 1, "Gable stud": 8}
        )

    def test_framing_fits_together(self):
        shed = Shed.Shed()
        sections = shed.sections()
        boxes = []
        for c in shed.components():
            if isinstance(c.model, Framing.GableRoof):
                continue  # sloped profiles: their bounding boxes are not the solids
            for p in c.model.pieces():
                boxes.append((f"{c.name} {p.name}", to_world(piece_box(p, sections), c)))
        for (na, a), (nb, b) in itertools.combinations(boxes, 2):
            self.assertFalse(boxes_overlap(a, b), f"{na} overlaps {nb}")
        lo = [min(b[0][i] for _, b in boxes) for i in range(3)]
        hi = [max(b[1][i] for _, b in boxes) for i in range(3)]
        for got, want in zip(lo + hi, [0, 0, 0, 3600, 3000, 195 + 18 + 2440]):
            self.assertAlmostEqual(got, want)

    def test_roof_sits_on_the_walls(self):
        components = {c.name: c for c in Shed.Shed().components()}
        roof, front = components["Roof"], components["Front wall"]
        self.assertAlmostEqual(roof.origin[2], front.origin[2] + front.model.height)
        self.assertEqual(roof.model.seat, front.model.stud[1])
        self.assertEqual(roof.model.span, 3000)

    def test_side_sheathing_wraps_the_corners(self):
        left = {c.name: c for c in Shed.Shed().components()}["Left wall"]
        surface = Shed.sheathing_surfaces(left)[0]
        self.assertAlmostEqual(surface.size[0], 3000 + 2 * 12)  # 2810 + 2 x (95 + 12)

    def test_sheathing_hand_count(self):
        # Sheets 1220 x 2440, no trim (factory edges), kerf 3.2. Hand count:
        # floor 3600 x 3000, staggered: 4 (area alone needs 3.63);
        # front/back 3600 x 2440 upright: 2 whole + 1160 wide = 3;
        # sides 2810 + 2 x 107 wrap = 3024: 2 whole + 584 wide = 3;
        # roof slopes 3600 x 2012.5: per slope 1 whole, 1160 x 1220, 1220 x 792.5,
        # 2380 x 792.5; both slopes: 2 whole + 2 (1160 x 1220 with 1220 x 792.5)
        # + 2 (one 2380 x 792.5 each) = 6. Gable ends (pentagon 3000 wide, 114.6 at
        # the eaves, 864.6 at the peak), upright 1220 columns clipped to it:
        # 1220 x 724.6, 1220 x 864.6, 560 x 394.6 per end; one of each fits a sheet
        # (724.6 + 864.6 + 394.6 + kerfs < 2440): 2. Roof total 8.
        expected = {
            "Floor": 4,
            "Front wall": 3,
            "Back wall": 3,
            "Left wall": 3,
            "Right wall": 3,
            "Roof": 8,
        }
        for c in Shed.Shed().components():
            pieces = []
            for surface in Shed.sheathing_surfaces(c):
                for _, _, du, dv in Sheathing.cover_surface(surface, (2440, 1220)):
                    # Grain (the sheet's long side) along u or v, as the cut list does.
                    length, width = (du, dv) if surface.long_along == "u" else (dv, du)
                    pieces.append((surface.name, length, width, True))
            sheets = CutList.layout_sheets(pieces, 1220, 2440, kerf=3.2, trim=0)
            self.assertEqual(len(sheets), expected[c.name], c.name)

    def test_editing_regenerates(self):
        tall = {c.name: c for c in Shed.Shed(wall_height=2700, door_width=1200).components()}
        self.assertAlmostEqual(tall["Roof"].origin[2], 195 + 18 + 2700)
        header = next(p for p in tall["Front wall"].model.pieces() if p.name == "Header")
        self.assertAlmostEqual(header.length(), 1200 + 2 * 45)
        with self.assertRaises(ValueError):
            Shed.Shed(door_width=3500).components()


class TestShedOptions(unittest.TestCase):
    def test_openings_and_shed_roof(self):
        text = "front: door 900x2100 @ 1350; right: window 600x600 @ 1000 sill 1200"
        openings = Shed.parse_openings(text)
        self.assertEqual(Shed.format_openings(openings), text)
        shed = Shed.Shed(roof="shed", pitch=14.04, openings=tuple(openings))
        parts = {c.name: c for c in shed.components()}
        roof = parts["Roof"].model
        self.assertIsInstance(roof, Framing.ShedRoof)
        # The back (high) wall is the roof's rise taller than the front.
        self.assertAlmostEqual(parts["Back wall"].model.height, 2440 + roof.rise())
        right = Counter(p.name for p in parts["Right wall"].model.pieces())
        self.assertEqual(right["Sill"], 1)  # the window
        self.assertEqual(Counter(b.name for b in roof.boards())["Gable stud"], 8)
        names = [s.name for s in Shed.sheathing_surfaces(parts["Roof"])]
        self.assertEqual(names.count("Gable sheathing"), 2)
        self.assertEqual(Shed.Shed(openings=()).wall_openings("front"), [])
        with self.assertRaises(ValueError):
            Shed.parse_openings("roof: window 600x600 @ 100 sill 100")

    def test_garage_on_slab(self):
        garage = Shed.Shed(**Shed.GARAGE)
        parts = {c.name: c for c in garage.components()}
        self.assertNotIn("Floor", parts)
        self.assertEqual(parts["Front wall"].origin[2], 0.0)  # on the slab's top
        (door,) = parts["Front wall"].model.openings
        self.assertEqual((door.x, door.width), (600.0, 2400.0))  # centred in 3600
        slab = garage.slab_model()
        self.assertEqual((slab.length, slab.width), (3600.0, 6000.0))
        self.assertIsNone(Shed.Shed().slab_model())


class TestStair(unittest.TestCase):
    def test_equal_risers_and_run(self):
        stair = Framing.Stair(total_rise=2600, max_riser=190)
        self.assertEqual(stair.risers(), 14)  # 2600 / 190 = 13.7 -> 14
        self.assertAlmostEqual(stair.riser() * stair.risers(), 2600)
        self.assertLessEqual(stair.riser(), 190)
        self.assertEqual(stair.run(), 2 * 145 + 6 - 25)  # boards + gap - nosing
        self.assertEqual(stair.total_run(), 13 * 271)

    def test_treads_rest_on_the_stringer_cuts(self):
        stair = Framing.Stair()
        r, t, tt = stair.riser(), stair.run(), stair.tread[0]
        treads = [p for p in stair.pieces() if p.name == "Tread"]
        self.assertEqual(len(treads), (stair.risers() - 1) * stair.tread_boards)
        tops = sorted({round(p.start[2] + tt / 2, 6) for p in treads})
        self.assertEqual(tops, [round(i * r, 6) for i in range(1, stair.risers())])
        cut_heights = {round(z, 6) for y, z in stair.outline()[3:]}
        self.assertEqual(cut_heights, {round(i * r - tt, 6) for i in range(1, stair.risers())})
        # Front tread boards overhang the riser face by the nosing.
        first = min(p.start[1] for p in treads) - stair.tread[1] / 2
        self.assertAlmostEqual(first, -stair.nosing)

    def test_stringers(self):
        stair = Framing.Stair(width=900, max_stringer_spacing=450)
        self.assertEqual([round(x, 1) for x in stair.stringer_centres()], [22.5, 450.0, 877.5])
        outline = stair.outline()
        self.assertEqual(outline[0], (0.0, 0.0))  # foot on the floor at the first riser
        self.assertTrue(all(z >= -1e-9 for _, z in outline))
        us = Framing.Stair(stringer=(38.1, 285.75))  # a 2x12 leaves more throat
        self.assertGreater(us.throat(), stair.throat())

    def test_handrails_and_guards(self):
        stair = Framing.Stair(open_sides="both")
        pieces = stair.pieces()
        counts = Counter(p.name for p in pieces)
        self.assertEqual(counts["Handrail"], 2)
        self.assertEqual(counts["Newel post"], 4)
        r, a = stair.riser(), math.radians(stair.angle())
        half_rail = stair.rail[1] / 2 / math.cos(a)
        rail = next(p for p in pieces if p.name == "Handrail")
        # Rail top sits handrail_height above the nosing line at both ends.
        for point in (rail.start, rail.end):
            self.assertAlmostEqual(point[2] + half_rail - stair.nosing_line(point[1]), 900)
        for side in (stair.post[0] / 2, stair.width - stair.post[0] / 2):
            balusters = sorted(
                (p for p in pieces if p.name == "Baluster" and p.start[0] == side),
                key=lambda p: p.start[1],
            )
            ys = [b.start[1] for b in balusters]
            posts = sorted(
                p.start[1] for p in pieces if p.name == "Newel post" and p.start[0] == side
            )
            faces = [posts[0] + stair.post[1] / 2] + ys + [posts[-1] - stair.post[1] / 2]
            gaps = [b - a - stair.baluster[1] for a, b in zip(ys, ys[1:])]
            gaps += [
                ys[0] - stair.baluster[1] / 2 - faces[0],
                faces[-1] - ys[-1] - stair.baluster[1] / 2,
            ]
            self.assertLessEqual(max(gaps), stair.max_baluster_gap + 1e-6)
            lengths = {round(b.length(), 1) for b in balusters}
            self.assertEqual(len(lengths), 2)  # 2 per tread: 2 lengths repeat
            for b in balusters:
                self.assertAlmostEqual(b.start[2] / r, round(b.start[2] / r))  # on a tread top
                low = rail.start[2] + (
                    b.start[1] - stair.baluster[1] / 2 - rail.start[1]
                ) * math.tan(a)
                self.assertLessEqual(b.end[2], low - half_rail + 1e-6)  # under the rail
        walled = Counter(p.name for p in Framing.Stair(open_sides="none").pieces())
        self.assertEqual((walled["Handrail"], walled["Baluster"], walled["Newel post"]), (1, 0, 0))

    def test_rejects(self):
        for kwargs in (
            {"total_rise": 150},  # one riser
            {"nosing": 400},
            {"stringer": (45, 95)},  # cuts go through
            {"width": 60},
            {"total_rise": 6000, "max_piece": 4800},  # stringer too long
            {"open_sides": "middle"},
            {"handrail_height": 50},
        ):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                Framing.Stair(**kwargs).boards()


class TestDeck(unittest.TestCase):
    SECTIONS = {
        "joist": (45, 195),
        "beam": (45, 195),
        "post": (95, 95),
        "decking": (28, 120),
    }

    def test_counts_and_heights(self):
        deck = Framing.Deck(length=3600, projection=3000, height=600)
        pieces = deck.pieces()
        counts = Counter(p.name for p in pieces)
        # Joists at 400: ends + 400..3200 = 10. Posts within 1800: 3.
        # Decking: (3000 + 5) / (120 + 5) = 24 rows, one board each (3600 <= 6000).
        self.assertEqual(
            dict(counts),
            {"Ledger": 1, "Rim joist": 1, "Joist": 10, "Beam": 2, "Post": 3, "Decking": 24},
        )
        boxes = assert_pieces_apart(self, pieces, self.SECTIONS)
        self.assertAlmostEqual(max(b[1][2] for b in boxes), 600)  # decking top
        self.assertAlmostEqual(min(b[0][2] for b in boxes), 0)  # posts on grade
        outer = max(b[1][1] for b in boxes)
        self.assertLessEqual(abs(outer - 3000), 120 / 2)  # within half a board of the rim

    def test_long_deck_splices_staggered(self):
        deck = Framing.Deck(length=9000, max_piece=4800)
        decking = [p for p in deck.pieces() if p.name == "Decking"]
        self.assertTrue(all(p.length() <= 4800 + 1e-6 for p in decking))
        rows = {}
        for p in decking:
            rows.setdefault(round(p.start[1], 3), []).append(p)
        joints = [sorted(p.end[0] for p in row)[:-1] for _, row in sorted(rows.items())]
        for a, b in zip(joints, joints[1:]):
            for x in a:
                for y in b:
                    self.assertGreaterEqual(abs(x - y), deck.spacing - 1e-6)
        centres = deck.joist_centres()
        for row in joints:
            for x in row:
                self.assertTrue(any(abs(x - c) < 1e-6 for c in centres))  # over a joist

    def test_rejects(self):
        for kwargs in ({"height": 300}, {"cantilever": 3000}, {"projection": 7000}):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                Framing.Deck(**kwargs).pieces()


class TestJoinery(unittest.TestCase):
    def carcass(self):
        # Two 18 mm sides with a bottom between them (like Cabinet parts).
        return [
            Parts.Part("Left side", "", (18, 560, 770), (0, 0, 0)),
            Parts.Part("Right side", "", (18, 560, 770), (582, 0, 0)),
            Parts.Part("Bottom", "", (564, 560, 18), (18, 0, 0)),
        ]

    def test_contact(self):
        side, _, bottom = self.carcass()
        axis, sign, (lo, hi) = Joinery.contact(side, bottom)
        self.assertEqual((axis, sign), (0, 1))
        self.assertEqual((lo, hi), ((18, 0, 0), (18, 560, 18)))
        self.assertIsNone(Joinery.contact(side, Parts.Part("x", "", (10, 10, 10), (500, 0, 0))))

    def test_housing_lengthens_and_pockets(self):
        rules = [Joinery.Rule("*side", "Bottom", "housing", depth=6)]
        result = Joinery.apply(self.carcass(), rules)
        bottom = result.boxes[2]
        self.assertEqual((bottom.size[0], bottom.pos[0]), (564 + 12, 12))  # 6 into each side
        pockets = sorted((i, p.pos, p.size) for i, p in result.pockets)
        self.assertEqual(pockets, [(0, (12, 0, 0), (6, 560, 18)), (1, (582, 0, 0), (6, 560, 18))])
        self.assertEqual(len(result.operations), 2)
        with self.assertRaises(ValueError):  # deeper than the side is thick
            Joinery.apply(self.carcass(), [Joinery.Rule("*side", "Bottom", "housing", depth=20)])

    def test_rabbet_at_an_edge(self):
        # A back flush with the side's rear edge: the pocket opens to the edge.
        side = Parts.Part("Side", "", (18, 560, 770), (0, 0, 0))
        back = Parts.Part("Back", "", (6, 6, 770), (18, 554, 0))
        result = Joinery.apply([side, back], [Joinery.Rule("Side", "Back", "housing", depth=9)])
        ((_, pocket),) = result.pockets
        self.assertEqual(pocket.pos[1] + pocket.size[1], 560)  # reaches the edge

    def test_fasteners_by_spacing_and_per_joint(self):
        rules = [Joinery.Rule("*side", "Bottom", fastener="screw", spacing=200, edge=50)]
        result = Joinery.apply(self.carcass(), rules)
        # Contact 560 long: 460 between the end screws -> 4 per side.
        self.assertEqual(result.fasteners, {"screw": 8})
        studs = [
            Parts.Part("Plate", "", (3600, 95, 45), (0, 0, 0)),
            Parts.Part("Stud", "", (45, 95, 2300), (0, 0, 45)),
            Parts.Part("Stud", "", (45, 95, 2300), (600, 0, 45)),
        ]
        nails = Joinery.apply(studs, [Joinery.Rule("Plate", "Stud", fastener="nail", per_joint=2)])
        self.assertEqual(nails.fasteners, {"nail": 4})
        self.assertEqual(nails.boxes, studs)  # fastened: no change

    def test_symmetric_rule_counts_once(self):
        plates = [
            Parts.Part("Top plate", "", (3600, 95, 45), (0, 0, 0)),
            Parts.Part("Top plate", "", (3600, 95, 45), (0, 0, 45)),
        ]
        rule = Joinery.Rule("Top plate", "Top plate", fastener="nail", spacing=400, edge=100)
        # 3600 - 2 x 100 = 3400 at 400 -> 9 spaces, 10 nails; counted once, not twice.
        self.assertEqual(Joinery.apply(plates, [rule]).fasteners, {"nail": 10})

    def test_half_lap(self):
        a = Parts.Part("Rail", "", (1000, 45, 95), (0, 0, 0))
        b = Parts.Part("Rail", "", (45, 1000, 95), (400, -400, 0))
        result = Joinery.apply([a, b], [Joinery.Rule("Rail", "Rail", "half_lap")])
        self.assertEqual(len(result.pockets), 2)
        depths = sorted(p.size[2] for _, p in result.pockets)
        self.assertEqual(depths, [47.5, 47.5])  # half of 95 each

    def table(self):
        # Two 45 mm legs, 700 tall, and a 20 x 100 apron between them, flush at the top.
        return [
            Parts.Part("Leg", "", (45, 45, 700), (0, 0, 0)),
            Parts.Part("Leg", "", (45, 45, 700), (495, 0, 0)),
            Parts.Part("Apron", "", (450, 20, 100), (45, 12.5, 600)),
        ]

    def test_mortise_and_tenon(self):
        rule = Joinery.Rule("Leg", "Apron", "tenon", depth=25, shoulder=10)
        result = Joinery.apply(self.table(), [rule])
        apron = result.boxes[2]
        self.assertEqual((apron.size[0], apron.pos[0]), (500, 20))  # 25 into each leg
        mortises = [p for i, p in result.pockets if i in (0, 1)]
        self.assertEqual([m.pos[0] for m in mortises], [20, 495])
        for m in mortises:
            self.assertAlmostEqual(m.size[1], 20 / 3)  # a third of the apron
            self.assertEqual((m.size[0], m.size[2], m.pos[2]), (25, 80, 610))
        waste = [p for i, p in result.pockets if i == 2]
        self.assertEqual(len(waste), 8)  # 2 cheeks + 2 shoulders per end
        volume = sum(p.size[0] * p.size[1] * p.size[2] for p in waste)
        # Per end: the 20 x 100 x 25 lengthening minus the 6.7 x 80 x 25 tenon.
        self.assertAlmostEqual(volume, 2 * (20 * 100 * 25 - 20 / 3 * 80 * 25))
        texts = sorted(t for _, t in result.operations)
        self.assertEqual(texts[0], "mortise 80 x 6.7 x 25 deep")
        self.assertEqual(texts[-1], "tenon 80 x 6.7 x 25 long")
        with self.assertRaises(ValueError):  # longer than the leg is thick
            Joinery.apply(self.table(), [Joinery.Rule("Leg", "Apron", "tenon", depth=50)])

    def test_loose_tenon(self):
        rule = Joinery.Rule(
            "Leg", "Apron", "loose_tenon", depth=20, shoulder=10, fastener="t", per_joint=1
        )
        result = Joinery.apply(self.table(), [rule])
        self.assertEqual(result.boxes[2].size[0], 450)  # the apron keeps its length
        apron_mortises = [p for i, p in result.pockets if i == 2]
        self.assertEqual(sorted(p.pos[0] for p in apron_mortises), [45, 475])  # 20 into each end
        self.assertEqual(len([p for i, p in result.pockets if i in (0, 1)]), 2)
        self.assertEqual(result.fasteners, {"t": 2})

    def test_holes(self):
        side, _, bottom = self.carcass()
        rule = Joinery.Rule("*side", "Bottom", fastener="d", spacing=200, edge=50, hole=[8, 15, 20])
        result = Joinery.apply([side, bottom], [rule])
        holes = [(i, p) for i, p in result.pockets if p.role == "hole"]
        self.assertEqual(len(holes), 8)  # 4 dowels, a hole in each part
        side_holes = sorted(p.pos for i, p in holes if i == 0)
        # Along y: 50 from the ends of the 560 contact, 460 / 3 apart; centred on the
        # bottom's 18 thickness (z 9); 15 into the side from its inner face at x = 18.
        self.assertEqual([round(p[1] + 4, 1) for p in side_holes], [50, 203.3, 356.7, 510])
        self.assertEqual({(p[0], p[2] + 4) for p in side_holes}, {(3, 9)})
        bottom_hole = next(p for i, p in holes if i == 1)
        self.assertEqual(
            (bottom_hole.pos[0], bottom_hole.size[0], bottom_hole.grain), (18, 20, "x")
        )
        rules = {"hole_wall_min_mm": 3}
        parts = [("ply", p) for p in result.boxes]
        self.assertEqual(Checks.build(parts, result, rules, {}), [])
        thin = Parts.Part("Bottom", "", (564, 560, 12), (18, 0, 0))  # 8 mm hole in 12 mm
        result = Joinery.apply([side, thin], [rule])
        found = Checks.build([("ply", p) for p in result.boxes], result, rules, {})
        # Centred on 12 mm, the 8 mm holes leave 2 mm in the bottom and 2 mm to the side's
        # lower edge (flush with the bottom).
        self.assertEqual([c for c, _, _ in found], ["Hole wall, Left side", "Hole wall, Bottom"])

    def test_bridle(self):
        # Two 45 x 95 rails overlapping at a frame corner.
        a = Parts.Part("Stile", "", (45, 95, 1000), (0, 0, 0))
        b = Parts.Part("Rail", "", (600, 95, 45), (0, 0, 955))
        result = Joinery.apply([a, b], [Joinery.Rule("Stile", "Rail", "bridle")])
        slot = [p for i, p in result.pockets if i == 0]
        cheeks = [p for i, p in result.pockets if i == 1]
        ((pos, size),) = [(p.pos[1], p.size[1]) for p in slot]
        self.assertAlmostEqual(pos, 95 / 3)
        self.assertAlmostEqual(size, 95 / 3)
        low, high = sorted(p.pos[1] for p in cheeks)
        self.assertEqual(low, 0)
        self.assertAlmostEqual(high, 2 * 95 / 3)
        self.assertIn((0, "bridle slot 31.7 wide"), result.operations)

    def corner(self):
        # Two 18 mm boards, 200 wide (z), overlapping at an L corner (0..18, 0..18).
        return [
            Parts.Part("Side", "", (18, 400, 200), (0, 0, 0)),
            Parts.Part("Front", "", (500, 18, 200), (0, 0, 0)),
        ]

    def test_box_joint_and_dovetail(self):
        result = Joinery.apply(self.corner(), [Joinery.Rule("Side", "Front", "box_joint")])
        fingers = sorted((p.pos[2], i) for i, p in result.pockets)
        # 200 / 18 -> 11 fingers (odd), alternating: the inserted part loses the even ones.
        self.assertEqual(len(fingers), 11)
        self.assertEqual([i for _, i in fingers], [1, 0] * 5 + [1])
        self.assertEqual(result.operations[0][1], "box joint: 11 fingers 18.2 wide")
        result = Joinery.apply(self.corner(), [Joinery.Rule("Side", "Front", "dovetail")])
        texts = dict((i, t) for i, t in result.operations)
        self.assertEqual(texts[1], "dovetails: 6 tails, 18.2 wide")

    def test_miter(self):
        result = Joinery.apply(self.corner(), [Joinery.Rule("Side", "Front", "miter")])
        (i, a), (j, b) = result.pockets
        # Side runs along y (body past the corner's high side), Front along x: each
        # loses the triangle on the other's side of the diagonal.
        self.assertEqual(a.profile, ("triangle", 1, 0, 0, 1))
        self.assertEqual(b.profile, ("triangle", 1, 1, 0, 0))
        with self.assertRaises(ValueError):  # parallel boards cannot miter
            Joinery.apply(
                [
                    Parts.Part("A", "", (500, 18, 200), (0, 0, 0)),
                    Parts.Part("B", "", (500, 18, 200), (400, 0, 0)),
                ],
                [Joinery.Rule("A", "B", "miter")],
            )

    def test_presets_from_library(self):
        items = Library.load()
        joints = Library.of_category(items, "joint")
        self.assertGreaterEqual(len(joints), 10)
        for joint in joints:
            rule = Joinery.rule(joint, "Leg", "Apron")
            self.assertIn(
                rule.kind,
                (
                    "housing",
                    "tenon",
                    "loose_tenon",
                    "half_lap",
                    "bridle",
                    "box_joint",
                    "dovetail",
                    "miter",
                    "fastened",
                ),
                joint["id"],
            )
            if rule.fastener:
                self.assertEqual(items[rule.fastener]["category"], "hardware", joint["id"])
        pocket = Joinery.rule(items["joint.pocket_screw"], "Leg", "Apron")
        result = Joinery.apply(self.table(), [pocket])
        # Contact 100 tall: 50 between the end screws -> 2 per apron end.
        self.assertEqual(result.fasteners, {"hardware.pocket_screw": 4})
        self.assertEqual(result.operations, [(2, "2 pocket holes"), (2, "2 pocket holes")])

    def test_meets(self):
        legs_and_apron = self.table()
        leg, _, apron = legs_and_apron
        self.assertEqual(Joinery.meets(leg, apron), "end_to_face")
        top = Parts.Part("Top", "", (540, 45, 20), (0, 0, 700))
        self.assertEqual(Joinery.meets(apron, top), "face_to_face")  # top on the apron's edge
        self.assertIsNone(Joinery.meets(leg, Parts.Part("x", "", (5, 5, 5), (200, 200, 0))))
        self.assertEqual(Joinery.meets(leg, top), "face_to_face")
        side = Parts.Part("Side", "", (450, 20, 100), (45, 32.5, 600))
        self.assertEqual(Joinery.meets(apron, side), "face_to_face")
        rail = Parts.Part("Rail", "", (20, 200, 50), (100, 0, 610))
        self.assertEqual(Joinery.meets(apron, rail), "crossing")


class TestBuild(unittest.TestCase):
    ITEMS = Library.load()
    LEG = "lumber.metric.hw.45x45"
    APRON = "lumber.metric.hw.20x95"

    def table(self, joints=()):
        parts = [
            ("Leg 1", self.LEG, 600, "", "", 0, 0, 0, "z", "x"),
            ("Leg 2", self.LEG, 600, "", "", 455, 0, 0, "z", "x"),
            ("Apron 1", self.APRON, 410, "", "", 45, 5, 505, "x", "y"),
            ("Top", "sheet.metric.edge_glued.18", 500, 500, "", 0, -20, 600, "x", "z"),
        ]
        return Build.build(parts, list(joints), self.ITEMS)

    def test_parts_from_rows(self):
        parts, _ = self.table()
        sizes = {p.name: (m, p.size, p.role, p.grain) for m, p in parts}
        self.assertEqual(sizes["Leg 1"], (self.LEG, (45, 45, 600), "board", "z"))
        self.assertEqual(sizes["Apron 1"], (self.APRON, (410, 20, 95), "board", "x"))
        self.assertEqual(sizes["Top"][1:3], ((500, 500, 18), "panel"))
        with self.assertRaises(ValueError):  # a panel needs a width
            Build.part(
                ("P", "sheet.metric.edge_glued.18", 500, "", "", 0, 0, 0, "x", "z"),
                {"sheet.metric.edge_glued.18": self.ITEMS["sheet.metric.edge_glued.18"]},
            )
        with self.assertRaises(ValueError):
            Build.part(("B", "nope", 500, "", "", 0, 0, 0, "x", "z"), self.ITEMS)

    def test_joints_from_presets(self):
        joints = [
            ("Leg*", "Apron*", "joint.mortise_tenon", "depth=20"),
            ("Apron*", "Top", "joint.figure8", ""),
        ]
        parts, result = self.table(joints)
        apron = dict((p.name, p) for _, p in parts)["Apron 1"]
        self.assertEqual(apron.size[0], 410 + 2 * 20)
        self.assertIn("tenon 75 x 6.7 x 20 long", apron.operations)
        leg = dict((p.name, p) for _, p in parts)["Leg 1"]
        self.assertEqual(leg.operations, ("mortise 75 x 6.7 x 20 deep",))
        # Top on the apron's top edge, 410 long: 260 between the end fasteners -> 2.
        self.assertEqual(result.fasteners, {"hardware.figure8": 2})
        self.assertIn("2 figure-8 recesses", apron.operations)
        rows = CutList.rows(parts)
        ops = CutList.operations(parts)
        self.assertEqual(len(ops), len(rows))
        self.assertEqual(sum(r[6] for r in rows), 4)
        self.assertIn("mortise 75 x 6.7 x 20 deep", ops)
        with self.assertRaises(ValueError):
            self.table([("Leg*", "Apron*", "joint.nope", "")])

    def test_options_and_names(self):
        self.assertEqual(Build.options("depth=30, shoulder=5"), {"depth": 30.0, "shoulder": 5.0})
        self.assertEqual(Build.options(""), {})
        self.assertEqual(Build.similar("Leg 3"), "Leg*")
        self.assertEqual(Build.similar("Top"), "Top")
        self.assertEqual(Build.new_name(["Board 1", "Board 2"], "Board"), "Board 3")

    def test_between(self):
        parts, _ = self.table()
        legs = [p for _, p in parts if p.name.startswith("Leg")]
        length, x, y, z, along, thick = Build.between(*legs, (20, 95))
        # Gap 455 - 45 = 410 along x; 20 thick centred on the legs' 45; top flush at 600.
        self.assertEqual((length, x, y, z, along, thick), (410, 45, 12.5, 505, "x", "y"))
        with self.assertRaises(ValueError):
            Build.between(legs[0], legs[0], (20, 95))

    def test_end_table_template(self):
        parts, result = Build.build(*Build.end_table(), self.ITEMS)
        self.assertEqual(len(parts), 9)
        self.assertEqual(result.fasteners, {"hardware.figure8": 8})
        # The two mortises in each leg (front and side aprons) must not meet.
        for leg in range(4):
            a, b = [p for i, p in result.pockets if i == leg]
            self.assertIsNone(Joinery.overlap(a, b))
        with self.assertRaises(ValueError):
            Build.end_table(width=100)
        with self.assertRaises(ValueError):
            Build.end_table(setback=30)

    def test_checks(self):
        rules = self.ITEMS["rules.generic-example"]

        def checks(**kw):
            parts, result = Build.build(*Build.end_table(**kw), self.ITEMS)
            return Checks.build(parts, result, rules, self.ITEMS)

        good = checks()
        self.assertEqual(len(good), 8)  # one mortise wall per apron end
        self.assertEqual({status for _, status, _ in good}, {Checks.OK})
        # Thinnest wall: 10 mm above the mortise, left by the tenon's 10 mm top shoulder
        # (the face side is 5 + (20 - 6.7) / 2 = 11.7 mm, the back 45 - 25 = 20 mm).
        self.assertIn("10.0 mm", good[0][2])
        names = [c for c, s, _ in checks(top_joint="joint.screw") if s == Checks.WARNING]
        # Rigid screws on a solid top, and 30 mm screw holes in an 18 mm top.
        self.assertEqual(names, ["Hole wall, Top", "Wood movement, Top"])

        def warnings(options):
            parts = Build.end_table()[0]
            joints = [("Leg*", "Apron*", "joint.mortise_tenon", options)]
            built, result = Build.build(parts, joints, self.ITEMS)
            found = Checks.build(built, result, rules, self.ITEMS)
            return {c for c, s, _ in found if s == Checks.WARNING}

        self.assertIn("Mortise wall, Leg 1", warnings("shoulder=3"))  # 3 mm above
        self.assertIn("Joints meet inside Leg 1", warnings("depth=40"))

    def test_dining_table_and_workbench(self):
        rules = self.ITEMS["rules.generic-example"]
        parts, result = Build.build(*Build.dining_table(), self.ITEMS)
        rows = {r[1]: r for r in CutList.rows(parts)}
        # Legs 70 at 50 from the edges: front aprons 1600 - 2 x 50 - 2 x 70 = 1360 + 2 x 25.
        self.assertEqual(rows["Apron 1"][2], 1410)
        # Top: 900 / 145 -> 7 boards, all ripped to 900 / 7.
        boards = [p for _, p in parts if p.name.startswith("Top board")]
        self.assertEqual(len(boards), 7)
        self.assertAlmostEqual(boards[0].size[1], 900 / 7)
        # Figure-8s: front and back aprons 1360 -> 5 each; the side aprons cross all
        # 7 boards, 1 per board.
        self.assertEqual(result.fasteners, {"hardware.figure8": 24})
        statuses = {s for _, s, _ in Checks.build(parts, result, rules, self.ITEMS)}
        self.assertEqual(statuses, {Checks.OK})  # no anchoring for a table
        # Screwing the glued-up top on flags the whole 900 mm glue-up once.
        parts, result = Build.build(*Build.dining_table(top_joint="joint.glue"), self.ITEMS)
        found = [c for c, s, _ in Checks.build(parts, result, rules, self.ITEMS) if s != Checks.OK]
        self.assertEqual(found, ["Wood movement, Top board 1 (glue-up of 7)"])
        parts, result = Build.build(*Build.workbench(), self.ITEMS)
        names = {p.name for _, p in parts}
        self.assertTrue({"Shelf", "Stretcher 1", "Top board 5"} <= names)
        # The shelf rests on the front and back stretchers: 10 pocket screws each.
        self.assertEqual(result.fasteners["hardware.pocket_screw"], 20)
        # 900 tall on a 600 deep footprint: not slender enough to need anchoring.
        self.assertFalse(Checks.build_anchored([p for _, p in parts], rules))

    def test_template_merge(self):
        old = [("A", 1), ("B", 2), ("C", 3)]
        new = [("A", 10), ("B", 20), ("D", 40)]  # C gone, D new
        current = [("A", 1), ("B", 5), ("C", 3), ("X", 9)]  # B edited, X added
        merged = Build.merge(old, new, current, lambda r: r[0])
        self.assertEqual(
            merged, [(("A", 10), False), (("B", 5), True), (("X", 9), False), (("D", 40), False)]
        )
        # Table values come back as floats: 1.0 is still the untouched 1.
        self.assertEqual(Build.merge(old, new, [("A", 1.0)], lambda r: r[0])[0], (("A", 10), False))

    def test_template_round_trip(self):
        template, arguments = Build.preset_arguments("dining_table")
        values = Build.property_values(template, arguments)
        self.assertEqual(values["TopBoards"], "lumber.metric.hw.20x145")
        self.assertEqual(values["Shelf"], "none")

        def lumber(i):
            item = self.ITEMS[i]
            return Library.mm(item, "w"), Library.mm(item, "h")

        def sheet(i):
            return Library.mm(self.ITEMS[i], "t")

        again = Build.template_arguments(template, values, lumber, sheet)
        self.assertEqual(Build.table(**again), Build.dining_table())

    def test_snap(self):
        leg = Parts.Part("Leg", "", (45, 45, 600), (0, 0, 0))
        board = Parts.Part("Board", "", (400, 20, 95), (100, 200, 300))
        # Within 15 mm of the leg's face: against it. Else the 5 mm grid.
        self.assertEqual(Build.snap(board, (52, 213, 300), (0, 1), [leg]), (45, 215, 300))
        self.assertEqual(Build.snap(board, (120, 213, 300), (0, 1), [leg]), (120, 215, 300))
        # Flush: the board's end lines up with the leg's far face.
        self.assertEqual(Build.snap(board, (-350, 200, 300), (0,), [leg])[0], -355)

    def test_bookcase_template(self):
        parts, result = Build.build(*Build.bookcase(), self.ITEMS)
        rows = {r[1]: r for r in CutList.rows(parts)}
        # Top, bottom and 4 shelves: 800 - 2 x 18 = 764 between the sides, + 6 dado each end.
        self.assertEqual(rows["Top"][2:], (776, 300, 18, "yes", 6))
        ops = dict(zip((r[1] for r in CutList.rows(parts)), CutList.operations(parts)))
        self.assertEqual(ops["Left side"], "6 x housing 18 x 6 deep")
        # Back: sides 1800 -> 1750 between end nails at 150 -> 13 each; top and bottom
        # 776 -> 6 each. Kick board: 2 pocket screws each end.
        self.assertEqual(result.fasteners, {"hardware.brad_nail": 38, "hardware.pocket_screw": 4})
        rules = self.ITEMS["rules.generic-example"]
        checks = Checks.build(parts, result, rules, self.ITEMS)
        self.assertEqual([(c, s) for c, s, _ in checks], [("Wall anchoring", Checks.REQUIRED)])
        boxes = [p for _, p in parts]
        self.assertTrue(Checks.build_anchored(boxes, rules))
        table = [p for _, p in Build.build(*Build.end_table(), self.ITEMS)[0]]
        self.assertFalse(Checks.build_anchored(table, rules))  # 600 mm: no anchoring
        with self.assertRaises(ValueError):
            Build.bookcase(height=300, shelves=10)

    def test_on_face(self):
        leg = Parts.Part("Leg", "board", (45, 45, 600), (0, 0, 0), "z")
        # A 20 x 95 board on the leg's +x face: vertical, 600 long, 20 thick along x.
        self.assertEqual(Build.on_face(leg, 0, 1, 20, 95), (600, 95, 45, 0, 0, "z", "x"))
        # A panel under the leg covers the 45 x 45 face, 18 thick, below z = 0.
        self.assertEqual(Build.on_face(leg, 2, -1, 18), (45, 45, 0, 0, -18, "x", "z"))


class TestBeamSupports(unittest.TestCase):
    def test_supports(self):
        values = {"Fb_MPa": 10, "E_MPa": 10000}
        # 45 x 195, 1000 mm, 2 N/mm: M = wL^2/8 simply supported, wL^2/2 cantilevered.
        section = 45 * 195**2 / 6
        _, simple = Checks.beam(1000, 45, 195, values, 2.0, 360)
        _, cantilever = Checks.beam(1000, 45, 195, values, 2.0, 360, "cantilever")
        self.assertIn(f"bending {2 * 1000**2 / 8 / section:.1f}", simple)
        self.assertIn(f"bending {2 * 1000**2 / 2 / section:.1f}", cantilever)
        self.assertIn("of 5.6 mm", cantilever)  # limit on twice the overhang: 2000/360
        found = {
            c for c, _, _ in Checks.deck(Framing.Deck(), {"floor_joist_deflection_limit": 360})
        }
        self.assertIn("Joist cantilever", found)


class TestFastening(unittest.TestCase):
    def schedule(self):
        item = Library.load()["fastening.generic-example"]
        return [Joinery.Rule(**r) for r in item["rules"]]

    def test_wall(self):
        wall = Framing.Wall(length=3600, height=2440, spacing=600, top_plates=2)
        # 7 studs x 2 nails into the bottom plate and 2 into the lower top plate (28),
        # top plates face-nailed: (3600 - 200) / 400 -> 9 spaces, 10 nails. 38.
        self.assertEqual(Framing.fasteners(wall, self.schedule()), {"hardware.nail_framing": 38})

    def test_floor(self):
        floor = Framing.Floor(length=3600, width=3000, spacing=400)
        # 10 joists x 2 rims x 3 nails.
        self.assertEqual(Framing.fasteners(floor, self.schedule()), {"hardware.nail_framing": 60})

    def test_deck(self):
        deck = Framing.Deck(length=3600, projection=3000, height=600)
        self.assertEqual(
            Framing.fasteners(deck, self.schedule()),
            {
                "hardware.joist_hanger": 10,  # each joist at the ledger
                "hardware.nail_framing": 30 + 20 + 10,  # rim 3 x 10, beam 1 x 10 x 2 plies, plies
                "hardware.deck_screw": 2 * 24 * 10,  # 24 boards over 10 joists
            },
        )

    def test_roofs_and_stairs_per_piece(self):
        # 14 rafters x 6, 7 ceiling joists x 6, 8 gable studs x 4.
        roof = Framing.GableRoof()
        self.assertEqual(
            Framing.fasteners(roof, self.schedule()), {"hardware.nail_framing": 84 + 42 + 32}
        )
        self.assertEqual(
            Framing.fasteners(Framing.ShedRoof(), self.schedule()), {"hardware.nail_framing": 42}
        )
        stair = Framing.fasteners(Framing.Stair(), self.schedule())
        self.assertEqual(stair["hardware.stringer_hanger"], 3)

    def test_wall_with_door_uses_the_schedule(self):
        wall = Framing.Wall(length=4800, openings=Framing.parse_openings("door 900x2100 @ 700"))
        nails = Framing.fasteners(wall, self.schedule())["hardware.nail_framing"]
        self.assertGreater(nails, 38)  # kings, jacks, header and cripple joints add nails


class TestChecks(unittest.TestCase):
    RULES = Library.load()["rules.generic-example"]

    def status(self, results, check):
        return next(s for c, s, _ in results if c.startswith(check))

    def test_spacing_and_slenderness(self):
        ok = Checks.wall(Framing.Wall(spacing=600), self.RULES)
        self.assertEqual(self.status(ok, "Stud spacing"), Checks.OK)
        self.assertEqual(self.status(ok, "Stud slenderness"), Checks.OK)  # 2305/95 = 24
        wide = Checks.wall(Framing.Wall(spacing=800), self.RULES)
        self.assertEqual(self.status(wide, "Stud spacing"), Checks.WARNING)
        tall = Checks.wall(Framing.Wall(height=6000), self.RULES)
        self.assertEqual(self.status(tall, "Stud slenderness"), Checks.WARNING)  # 5865/95 = 62

    def test_header_not_checked_without_user_values(self):
        w = Framing.Wall(openings=Framing.parse_openings("door 900x2100 @ 600"))
        self.assertEqual(self.status(Checks.wall(w, self.RULES), "Header"), Checks.NOT_CHECKED)
        values = {"Fb_MPa": 10, "E_MPa": 10000}
        self.assertEqual(
            self.status(Checks.wall(w, self.RULES, values, header_load=0), "Header"),
            Checks.NOT_CHECKED,
        )
        self.assertEqual(
            self.status(Checks.wall(w, self.RULES, values, header_load=5), "Header"), Checks.OK
        )

    def test_header_mechanics(self):
        # Hand calculation: span 2000 mm, 2 plies 45x195, 5 N/mm.
        # M = 5*2000^2/8 = 2.5e6 N mm; S = 90*195^2/6 = 570375 mm3 -> 4.38 MPa.
        # I = 90*195^3/12 = 55.61e6 mm4; deflection = 5*5*2000^4/(384*10000*I) = 1.87 mm.
        status, detail = Checks.header(2000, (45, 195), 2, {"Fb_MPa": 10, "E_MPa": 10000}, 5, 360)
        self.assertEqual(status, Checks.OK)
        self.assertIn("bending 4.4 of 10 MPa", detail)
        self.assertIn("deflection 1.9 of 5.6 mm", detail)
        status, _ = Checks.header(2000, (45, 195), 2, {"Fb_MPa": 4, "E_MPa": 10000}, 5, 360)
        self.assertEqual(status, Checks.WARNING)  # 4.38 MPa > 4
        status, _ = Checks.header(4000, (45, 195), 2, {"Fb_MPa": 40, "E_MPa": 10000}, 5, 360)
        self.assertEqual(status, Checks.WARNING)  # 16 x the deflection: 30 mm > 11.1 mm

    def test_floor_joists(self):
        floor = Framing.Floor(width=3000, spacing=400, joist=(45, 195))
        self.assertEqual(Checks.floor(floor, self.RULES)[0][1], Checks.NOT_CHECKED)
        # Span 2955 mm, w = 2 kPa x 400 mm = 0.8 N/mm: M = 0.873e6 N mm,
        # S = 285188 mm3 -> 3.06 MPa; deflection 2.86 mm of 8.2 mm (span/360).
        name, status, detail = Checks.floor(floor, self.RULES, {"Fb_MPa": 10, "E_MPa": 10000}, 2)[0]
        self.assertEqual(status, Checks.OK)
        self.assertIn("bending 3.1 of 10 MPa", detail)
        self.assertIn("deflection 2.9 of 8.2 mm", detail)
        weak = Checks.floor(floor, self.RULES, {"Fb_MPa": 10, "E_MPa": 2500}, 2)[0]
        self.assertEqual(weak[1], Checks.WARNING)  # 11.4 mm > 8.2 mm

    def test_roof(self):
        roof = Framing.GableRoof()
        results = {c: s for c, s, _ in Checks.roof(roof, self.RULES)}
        self.assertEqual(results["Rafters"], Checks.NOT_CHECKED)
        self.assertEqual(results["Birdsmouth"], Checks.OK)  # 95 sin 26.6 = 42 <= 48
        self.assertEqual(results["Ridge board depth"], Checks.OK)  # 195 >= 162
        self.assertEqual(results["Rafter ties"], Checks.OK)
        shallow = Framing.GableRoof(ridge=(45, 145), seat=140, ties=False)
        results = {c: s for c, s, _ in Checks.roof(shallow, self.RULES)}
        self.assertEqual(results["Ridge board depth"], Checks.WARNING)
        self.assertEqual(results["Birdsmouth"], Checks.WARNING)  # 140 sin 26.6 = 63 > 48
        self.assertEqual(results["Rafter ties"], Checks.WARNING)

    def test_stair(self):
        good = Framing.Stair(stringer=(38.1, 285.75))
        results = {c: s for c, s, _ in Checks.stair(good, self.RULES)}
        self.assertEqual(results["Riser height"], Checks.OK)  # 185.7 <= 190
        self.assertEqual(results["Tread run"], Checks.OK)  # 271 >= 250
        self.assertEqual(results["Comfort (2 x riser + tread)"], Checks.OK)  # 2 x 185.7 + 271 = 642
        self.assertEqual(results["Stringer throat"], Checks.OK)
        self.assertEqual(results["Handrail"], Checks.OK)  # 900 within 850..1000
        self.assertEqual(results["Guards"], Checks.OK)  # 900 high, gaps up to 100
        self.assertEqual(results["Headroom"], Checks.NOT_CHECKED)
        shallow = {c: s for c, s, _ in Checks.stair(Framing.Stair(), self.RULES)}
        self.assertEqual(shallow["Stringer throat"], Checks.WARNING)  # 45x220: 67 < 90
        low = {c: s for c, s, _ in Checks.stair(Framing.Stair(total_rise=500), self.RULES)}
        self.assertNotIn("Guards", low)  # 500 mm rise
        self.assertNotIn("Handrail", low)  # 3 risers
        bad = Framing.Stair(handrail_height=1100, max_baluster_gap=150)
        bad_results = {c: st for c, st, _ in Checks.stair(bad, self.RULES)}
        self.assertEqual(bad_results["Handrail"], Checks.WARNING)
        self.assertEqual(bad_results["Guards"], Checks.WARNING)
        walled = {c: st for c, st, _ in Checks.stair(Framing.Stair(open_sides="none"), self.RULES)}
        self.assertNotIn("Guards", walled)
        long_treads = Framing.Stair(tread_boards=3)  # run 422: 2 x 185.7 + 422 = 793
        comfort = {c: s for c, s, _ in Checks.stair(long_treads, self.RULES)}
        self.assertEqual(comfort["Comfort (2 x riser + tread)"], Checks.WARNING)

    def test_deck(self):
        results = {c: s for c, s, _ in Checks.deck(Framing.Deck(height=600), self.RULES)}
        self.assertEqual(results["Joists"], Checks.NOT_CHECKED)
        self.assertEqual(results["Beam"], Checks.NOT_CHECKED)
        self.assertEqual(results["Ledger attachment"], Checks.REQUIRED)
        self.assertEqual(results["Footings"], Checks.REQUIRED)
        self.assertNotIn("Guards", results)  # 600 mm <= 750 mm
        high = {c: s for c, s, _ in Checks.deck(Framing.Deck(height=1200), self.RULES)}
        self.assertEqual(high["Guards"], Checks.REQUIRED)
        values = {"Fb_MPa": 10, "E_MPa": 10000}
        # Joists: span 2555 - 45 = 2510, 2 kPa x 400 = 0.8 N/mm -> 2.2 MPa, 1.5 of 7.0 mm.
        # Beam: posts 1752.5 apart, tributary 1255 + 400 + 45 = 1700 -> 3.4 N/mm on two
        # 45 x 195 plies -> 2.3 MPa, 0.75 mm.
        values = {"Fb_MPa": 10, "E_MPa": 10000}
        loaded = {
            c: (s, d) for c, s, d in Checks.deck(Framing.Deck(), self.RULES, values, values, 2)
        }
        self.assertEqual(loaded["Joists"][0], Checks.OK)
        self.assertIn("bending 2.2 of 10 MPa; deflection 1.5 of 7.0 mm", loaded["Joists"][1])
        self.assertEqual(loaded["Beam"][0], Checks.OK)
        self.assertIn("bending 2.3 of 10 MPa; deflection 0.8 of 4.9 mm", loaded["Beam"][1])

    def test_cabinet_anchoring(self):
        for kind, expected in (("wall", 1), ("tall", 1), ("base", 0), ("sink", 0)):
            results = Checks.cabinet(Cabinet.defaults(kind), self.RULES)
            self.assertEqual(len(results), expected, kind)
        items = Library.load()
        hw = dict(CutList.hardware(items, anchored_cabinets=3))
        self.assertEqual(hw[items["hardware.wall_anchor"]["name"]], 6)


HERE = os.path.dirname(os.path.abspath(__file__))
TUTORIALS = next(
    (
        folder
        for folder in (
            os.path.join(HERE, "Tutorials"),  # installed with the workbench
            os.path.join(HERE, "..", "..", "..", "docs", "tutorials", "construction"),  # source
        )
        if os.path.isdir(folder)
    ),
    "",
)


class TestTutorials(unittest.TestCase):
    """Runs every ```pycon block in docs/tutorials/construction with doctest, so
    the tutorials' examples and printed results stay true."""

    def test_examples(self):
        import doctest
        import re

        if not TUTORIALS:
            self.skipTest("tutorials not found")
        parser = doctest.DocTestParser()
        runner = doctest.DocTestRunner(optionflags=doctest.NORMALIZE_WHITESPACE)
        blocks = 0
        for name in sorted(os.listdir(TUTORIALS)):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(TUTORIALS, name), encoding="utf-8") as f:
                text = f.read()
            # One namespace per tutorial: later blocks build on earlier ones.
            source = "\n".join(re.findall(r"```pycon\n(.*?)```", text, re.S))
            if not source:
                continue
            test = parser.get_doctest(source, {}, name, name, 0)
            blocks += 1
            result = runner.run(test)
            self.assertEqual(result.failed, 0, f"{name}: {result.failed} example(s) failed")
        self.assertGreater(blocks, 0)


class TestModulesImport(unittest.TestCase):
    """The FreeCAD-facing modules cannot run here; importing them against stubs
    still catches definition-order and name errors before a build does."""

    def test_import_with_stubs(self):
        import types

        stubs = {}
        for name in ("FreeCAD", "FreeCADGui", "Part", "ArchStructure"):
            module = types.ModuleType(name)
            stubs[name] = module
        stubs["FreeCAD"].GuiUp = False
        stubs["ArchStructure"]._Structure = object  # BIM's base class of members
        stubs["FreeCAD"].Qt = types.SimpleNamespace(
            translate=lambda c, t: t, QT_TRANSLATE_NOOP=lambda c, t: t
        )
        stubs["FreeCADGui"].addCommand = lambda name, command: None
        saved = {
            n: sys.modules.get(n)
            for n in list(stubs) + ["ConstructionObjects", "ConstructionCommands"]
        }
        try:
            sys.modules.update(stubs)
            sys.modules.pop("ConstructionObjects", None)
            sys.modules.pop("ConstructionCommands", None)
            import ConstructionCommands  # noqa: F401
            import ConstructionObjects

            self.assertTrue(
                issubclass(ConstructionObjects.GableRoofFeature, ConstructionObjects.FramingFeature)
            )
        finally:
            for n, m in saved.items():
                if m is None:
                    sys.modules.pop(n, None)
                else:
                    sys.modules[n] = m


class TestLibrary(unittest.TestCase):
    def test_shipped_items_are_complete(self):
        items = Library.load()
        sheets = Library.of_category(items, Library.SHEET_GOODS)
        self.assertTrue(sheets)
        for item in sheets:
            self.assertGreater(Library.mm(item, "t"), 0, item["id"])
            self.assertGreater(Library.mm(item, "w") * Library.mm(item, "h"), 0, item["id"])
        self.assertEqual({i["region"] for i in sheets}, {"US", "metric"})

    def test_lumber_items_take_file_defaults(self):
        items = Library.load()
        lumber = Library.of_category(items, Library.LUMBER)
        self.assertEqual({i["region"] for i in lumber}, {"US", "metric"})
        for item in lumber:
            self.assertTrue(item["stock_lengths_mm"], item["id"])
            self.assertLess(Library.mm(item, "w"), Library.mm(item, "h") + 1e-9, item["id"])
        self.assertAlmostEqual(Library.mm(items["lumber.us.2x4"], "h"), 88.9)  # 3-1/2 in

    def test_user_dir_overrides(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "metric"))
            item = {
                "id": "sheet.metric.plywood.18",
                "category": "sheet_goods",
                "region": "metric",
                "actual": {"w": 1, "h": 1, "t": 17.5},
            }
            with open(os.path.join(tmp, "metric", "mine.json"), "w") as f:
                json.dump({"items": [item]}, f)
            with open(os.path.join(tmp, "metric", "broken.json"), "w") as f:
                f.write("{not json")
            items = Library.load([Library.LIBRARY_DIR, tmp])
            self.assertEqual(Library.mm(items["sheet.metric.plywood.18"], "t"), 17.5)


if __name__ == "__main__":
    unittest.main()

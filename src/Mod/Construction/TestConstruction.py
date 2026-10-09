# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: tests for the Construction workbench core. Run inside the app via the
# test runner (registered in Init.py) or standalone: python3 TestConstruction.py

import itertools
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Cabinet  # noqa: E402
import Checks  # noqa: E402
import CutList  # noqa: E402
import Framing  # noqa: E402
import Library  # noqa: E402
import Member  # noqa: E402
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
        side = Cabinet.Part("Side", "carcass", (18, 574, 770), (0, 0, 0), "z")
        self.assertEqual(side.cut_size(), (770, 574, 18))
        shelf = Cabinet.Part("Shelf", "carcass", (562, 554, 18), (0, 0, 0), "x")
        self.assertEqual(shelf.cut_size(), (562, 554, 18))  # grain along the shorter side kept
        mdf = Cabinet.Part("Panel", "carcass", (300, 18, 500), (0, 0, 0), None)
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
        item = Library.load()["hardware.hinge"]
        self.assertEqual(CutList.hinges(700, item), 2)
        self.assertEqual(CutList.hinges(900, item), 2)
        self.assertEqual(CutList.hinges(901, item), 3)
        self.assertEqual(CutList.hinges(2400, item), 5)
        self.assertEqual(CutList.hinges(2401, item), 6)  # one per started 400 mm beyond
        self.assertEqual(CutList.hinges(2900, item), 7)

    def test_cabinet_hardware(self):
        items = Library.load()
        c = Cabinet.Cabinet(width=800, fronts="drawer_over_doors", shelves=1)
        hw = dict(CutList.hardware(c.parts(), items))
        self.assertEqual(hw[items["hardware.hinge"]["name"]], 4)  # 2 doors x 2 hinges
        self.assertEqual(hw[items["hardware.shelf_pin"]["name"]], 4)
        self.assertEqual(hw[items["hardware.drawer_slide"]["name"] + ", 550 mm"], 1)
        tall = Cabinet.defaults("tall")  # 2000 mm doors: 4 hinges each
        tall_hw = dict(CutList.hardware(tall.parts(), items))
        self.assertEqual(tall_hw[items["hardware.hinge"]["name"]], 4)


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

    def test_cabinet_anchoring(self):
        for kind, expected in (("wall", 1), ("tall", 1), ("base", 0), ("sink", 0)):
            results = Checks.cabinet(Cabinet.defaults(kind), self.RULES)
            self.assertEqual(len(results), expected, kind)
        items = Library.load()
        hw = dict(CutList.hardware([], items, anchored_cabinets=3))
        self.assertEqual(hw[items["hardware.wall_anchor"]["name"]], 6)


TUTORIALS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "..",
    "docs",
    "tutorials",
    "construction",
)


class TestTutorials(unittest.TestCase):
    """Runs every ```pycon block in docs/tutorials/construction with doctest, so
    the tutorials' examples and printed results stay true."""

    def test_examples(self):
        import doctest
        import re

        if not os.path.isdir(TUTORIALS):
            self.skipTest("tutorials not installed (source tree only)")
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
        for name in ("FreeCAD", "FreeCADGui", "Part"):
            module = types.ModuleType(name)
            stubs[name] = module
        stubs["FreeCAD"].GuiUp = False
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

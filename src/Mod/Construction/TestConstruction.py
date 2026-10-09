# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: tests for the Construction workbench core. Run inside the app via the
# test runner (registered in Init.py) or standalone: python3 TestConstruction.py

import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Cabinet  # noqa: E402
import CutList  # noqa: E402
import Framing  # noqa: E402
import Library  # noqa: E402
import Member  # noqa: E402

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


def piece_box(piece, wall):
    """Axis-aligned bounds (lo, hi) of a framing piece."""
    w, h = wall.stud if piece.section == "stud" else wall.header
    _, x, y, z = Member.frame(piece.start, piece.end, piece.roll)
    lo, hi = [], []
    for i in range(3):
        half = abs(x[i]) * w / 2 + abs(y[i]) * h / 2
        a, b = sorted((piece.start[i], piece.end[i]))
        lo.append(a - half)
        hi.append(b + half)
    return lo, hi


def boxes_overlap(a, b):
    return all(a[0][i] < b[1][i] - 1e-6 and b[0][i] < a[1][i] - 1e-6 for i in range(3))


class TestFraming(unittest.TestCase):
    def check_no_overlap(self, wall):
        pieces = wall.pieces()
        boxes = [piece_box(p, wall) for p in pieces]
        for (pa, a), (pb, b) in itertools.combinations(zip(pieces, boxes), 2):
            self.assertFalse(
                boxes_overlap(a, b), f"{pa.name} {pa.start} overlaps {pb.name} {pb.start}"
            )
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

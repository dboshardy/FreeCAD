# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: tests for the Construction workbench core. Run inside the app via the
# test runner (registered in Init.py) or standalone: python3 TestConstruction.py

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Cabinet  # noqa: E402
import CutList  # noqa: E402
import Library  # noqa: E402


def bbox(parts):
    lo = [min(p.pos[i] for p in parts) for i in range(3)]
    hi = [max(p.pos[i] + p.size[i] for p in parts) for i in range(3)]
    return lo, hi


def overlaps(a, b):
    return all(
        a.pos[i] < b.pos[i] + b.size[i] - 1e-9 and b.pos[i] < a.pos[i] + a.size[i] - 1e-9
        for i in range(3)
    )


class TestCabinet(unittest.TestCase):
    def test_carcass_fills_outer_size(self):
        c = Cabinet.BaseCabinet(width=800, height=870, depth=580)
        body = [p for p in c.parts() if p.role != "door"]
        lo, hi = bbox(body)
        self.assertEqual(lo, [0, 0, 0])
        self.assertEqual(hi, [800, 580, 870])

    def test_no_parts_overlap(self):
        for shelves in (0, 1, 3):
            parts = Cabinet.BaseCabinet(width=900, shelves=shelves).parts()
            for i, a in enumerate(parts):
                for b in parts[i + 1 :]:
                    self.assertFalse(overlaps(a, b), f"{a.name} overlaps {b.name}")

    def test_doors_cover_width_with_gaps(self):
        for width, count in ((450, 1), (600, 1), (601, 2), (1000, 2)):
            c = Cabinet.BaseCabinet(width=width)
            doors = [p for p in c.parts() if p.role == "door"]
            self.assertEqual(len(doors), count)
            total = sum(d.size[0] for d in doors) + c.door_gap * count
            self.assertAlmostEqual(total, width)
            self.assertAlmostEqual(doors[0].pos[0], c.door_gap / 2)

    def test_shelf_count_and_fit(self):
        c = Cabinet.BaseCabinet(width=600, shelves=2)
        shelves = [p for p in c.parts() if p.name.startswith("Shelf")]
        self.assertEqual(len(shelves), 2)
        self.assertAlmostEqual(shelves[0].size[0], 600 - 2 * 18 - 2 * 1)

    def test_rejects_impossible_sizes(self):
        for kwargs in (
            {"width": 30},
            {"height": 120},
            {"depth": 100},
            {"thickness": 0},
            {"shelves": -1},
            {"door_gap": 700},
            {"plinth_setback": 600},
        ):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                Cabinet.BaseCabinet(**kwargs).parts()

    def test_cut_size_follows_grain(self):
        side = Cabinet.Part("Side", "carcass", (18, 574, 770), (0, 0, 0), "z")
        self.assertEqual(side.cut_size(), (770, 574, 18))
        shelf = Cabinet.Part("Shelf", "carcass", (562, 554, 18), (0, 0, 0), "x")
        self.assertEqual(shelf.cut_size(), (562, 554, 18))  # grain along the shorter side kept
        mdf = Cabinet.Part("Panel", "carcass", (300, 18, 500), (0, 0, 0), None)
        self.assertEqual(mdf.cut_size(), (500, 300, 18))


class TestCutList(unittest.TestCase):
    def test_groups_identical_parts(self):
        parts = Cabinet.BaseCabinet(width=600, shelves=0).parts()
        rows = CutList.rows(("ply", p) for p in parts)
        sides = [r for r in rows if r[1] == "Left side"]
        self.assertEqual(len(sides), 1)
        self.assertEqual(sides[0][6], 2)  # left and right side share a row
        self.assertEqual(sum(r[6] for r in rows), len(parts))

    def test_sheet_estimate(self):
        rows = [("ply", "A", 1000, 500, 18, "yes", 4)]  # 2.0 m2
        self.assertEqual(CutList.sheet_estimate(rows, {"ply": 2_000_000}, waste=0.0), {"ply": 1})
        self.assertEqual(CutList.sheet_estimate(rows, {"ply": 2_000_000}, waste=0.1), {"ply": 2})
        self.assertEqual(CutList.sheet_estimate(rows, {}), {})  # unknown sheet size: skipped


class TestLibrary(unittest.TestCase):
    def test_shipped_items_are_complete(self):
        items = Library.load()
        sheets = Library.sheets(items)
        self.assertTrue(sheets)
        for item in sheets:
            self.assertGreater(Library.mm(item, "t"), 0, item["id"])
            self.assertGreater(Library.mm(item, "w") * Library.mm(item, "h"), 0, item["id"])
        self.assertEqual({i["region"] for i in sheets}, {"US", "metric"})

    def test_user_dir_overrides(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "metric"))
            with open(os.path.join(tmp, "metric", "mine.json"), "w") as f:
                json.dump(
                    {
                        "items": [
                            {
                                "id": "sheet.metric.plywood.18",
                                "category": "sheet_goods",
                                "region": "metric",
                                "actual": {"w": 1, "h": 1, "t": 17.5},
                            }
                        ]
                    },
                    f,
                )
            items = Library.load([Library.LIBRARY_DIR, tmp])
            self.assertEqual(Library.mm(items["sheet.metric.plywood.18"], "t"), 17.5)


if __name__ == "__main__":
    unittest.main()

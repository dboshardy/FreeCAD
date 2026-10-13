# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs in stock FreeCAD: FreeCADCmd -t TestSketch."""

import math
import time
import unittest

import FreeCAD
import Part
import Sketcher

import SketchTools

V = FreeCAD.Vector


def new_sketch(doc):
    return doc.addObject("Sketcher::SketchObject", "Sketch")


def rectangle(sk, x, y, w, h, fully=True):
    """Four lines with coincident corners, horizontal and vertical sides; with `fully`,
    also the size and the position of the lower left corner. Returns the first geometry id."""
    g = sk.addGeometry(
        [
            Part.LineSegment(V(x, y, 0), V(x + w, y, 0)),
            Part.LineSegment(V(x + w, y, 0), V(x + w, y + h, 0)),
            Part.LineSegment(V(x + w, y + h, 0), V(x, y + h, 0)),
            Part.LineSegment(V(x, y + h, 0), V(x, y, 0)),
        ],
        False,
    )[0]
    C = Sketcher.Constraint
    sk.addConstraint(
        [C("Coincident", g, 2, g + 1, 1), C("Coincident", g + 1, 2, g + 2, 1),
         C("Coincident", g + 2, 2, g + 3, 1), C("Coincident", g + 3, 2, g, 1),
         C("Horizontal", g), C("Horizontal", g + 2), C("Vertical", g + 1), C("Vertical", g + 3)]
    )
    if fully:
        sk.addConstraint(
            [C("DistanceX", g, 1, g, 2, w), C("DistanceY", g + 1, 1, g + 1, 2, h),
             C("DistanceX", -1, 1, g, 1, x), C("DistanceY", -1, 1, g, 1, y)]
        )
    return g


class SketchCase(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("SketchTest")
        self.sk = new_sketch(self.doc)

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)


class TestTangentCircle(SketchCase):
    def test_three_lines_give_the_incircle(self):
        sk = self.sk
        sk.addGeometry(
            [Part.LineSegment(V(0, 0, 0), V(100, 0, 0)), Part.LineSegment(V(100, 0, 0), V(0, 100, 0)),
             Part.LineSegment(V(0, 100, 0), V(0, 0, 0))],
            False,
        )
        circle = SketchTools.tangent_circle(sk, [0, 1, 2])
        c = sk.Geometry[circle]
        r = (100 + 100 - math.hypot(100, 100)) / 2  # right triangle: (a + b - c) / 2
        self.assertAlmostEqual(c.Radius, r, places=4)
        self.assertAlmostEqual(c.Center.x, r, places=4)
        self.assertAlmostEqual(c.Center.y, r, places=4)

    def test_two_lines_and_a_circle(self):
        sk = self.sk
        sk.addGeometry([Part.LineSegment(V(0, 0, 0), V(200, 0, 0)), Part.LineSegment(V(0, 0, 0), V(0, 200, 0))], False)
        sk.addGeometry(Part.Circle(V(100, 100, 0), V(0, 0, 1), 20), False)
        sk.addConstraint(Sketcher.Constraint("Radius", 2, 20))
        sk.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 2, 3, 100))
        sk.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 2, 3, 100))
        circle = SketchTools.tangent_circle(sk, [0, 1, 2])
        c = sk.Geometry[circle]
        # tangent to both axes: centre at (r, r) (or the mirror positions) and to the circle at (100, 100)
        self.assertAlmostEqual(abs(c.Center.x), abs(c.Center.y), places=4)
        d = (c.Center - V(100, 100, 0)).Length  # outside or inside tangent: both are solutions
        self.assertTrue(abs(d - (c.Radius + 20)) < 1e-3 or abs(d - abs(c.Radius - 20)) < 1e-3, (d, c.Radius))

    def test_one_curve_leaves_it_free(self):
        self.sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(100, 0, 0)), False)
        circle = SketchTools.tangent_circle(self.sk, [0])
        c = self.sk.Geometry[circle]
        self.assertAlmostEqual(abs(c.Center.y), c.Radius, places=4)

    def test_rejects_wrong_counts_and_types(self):
        self.sk.addGeometry(Part.Point(V(1, 1, 0)), False)
        with self.assertRaises(ValueError):
            SketchTools.tangent_circle(self.sk, [])
        with self.assertRaises(ValueError):
            SketchTools.tangent_circle(self.sk, [0])  # a point


class TestStretch(SketchCase):
    def test_stretching_the_right_side_lengthens_the_rectangle(self):
        g = rectangle(self.sk, 0, 0, 100, 50, fully=False)
        self.sk.solve()
        right = [(g + 1, 1), (g + 1, 2)]
        self.assertEqual(SketchTools.stretch(self.sk, right, V(20, 0, 0)), 0)
        xs = [p.x for geo in self.sk.Geometry for p in (geo.StartPoint, geo.EndPoint)]
        self.assertAlmostEqual(max(xs), 120, places=4)
        self.assertAlmostEqual(min(xs), 0, places=4)
        ys = [p.y for geo in self.sk.Geometry for p in (geo.StartPoint, geo.EndPoint)]
        self.assertAlmostEqual(max(ys) - min(ys), 50, places=4)


class TestDiagnose(SketchCase):
    def test_a_sound_sketch_has_nothing_to_diagnose(self):
        rectangle(self.sk, 0, 0, 100, 50)
        self.assertEqual(SketchTools.diagnose(self.sk), [])

    def test_names_the_constraint_whose_removal_fixes_a_conflict(self):
        g = rectangle(self.sk, 0, 0, 100, 50)
        self.sk.addConstraint(Sketcher.Constraint("DistanceX", g, 1, g, 2, 120))  # width twice, differently
        self.assertTrue(self.sk.ConflictingConstraints or self.sk.solve() != 0)
        found = SketchTools.diagnose(self.sk)
        self.assertTrue(found)
        numbers = [n for n, *_ in found]
        self.assertIn(len(self.sk.Constraints), numbers)  # the one added last
        self.assertEqual(found[0][0], len(self.sk.Constraints))
        self.assertIn("Remove constraint", found[0][3])

    def test_leaves_no_probe_behind_and_changes_nothing(self):
        g = rectangle(self.sk, 0, 0, 100, 50)
        self.sk.addConstraint(Sketcher.Constraint("DistanceX", g, 1, g, 2, 120))
        before = (len(self.sk.Constraints), len(self.sk.Geometry), len(self.doc.Objects))
        SketchTools.diagnose(self.sk)
        self.assertEqual((len(self.sk.Constraints), len(self.sk.Geometry), len(self.doc.Objects)), before)


class TestRegions(SketchCase):
    def test_square_with_a_circle_inside_gives_a_ring_and_a_disc(self):
        rectangle(self.sk, 0, 0, 100, 100, fully=False)
        self.sk.addGeometry(Part.Circle(V(50, 50, 0), V(0, 0, 1), 20), False)
        self.doc.recompute()
        found = SketchTools.regions(self.sk)
        self.assertEqual([r["depth"] for r in found], [0, 1])
        self.assertAlmostEqual(found[0]["face"].Area, 100 * 100 - math.pi * 400, delta=0.5)
        self.assertAlmostEqual(found[1]["face"].Area, math.pi * 400, delta=0.5)

    def test_three_levels_alternate_ring_and_disc(self):
        rectangle(self.sk, 0, 0, 100, 100, fully=False)
        self.sk.addGeometry(Part.Circle(V(50, 50, 0), V(0, 0, 1), 30), False)
        self.sk.addGeometry(Part.Circle(V(50, 50, 0), V(0, 0, 1), 10), False)
        self.doc.recompute()
        found = SketchTools.regions(self.sk)
        self.assertEqual([r["depth"] for r in found], [0, 1, 2])
        self.assertAlmostEqual(sum(r["face"].Area for r in found), 100 * 100, delta=1)

    def test_two_separate_loops_are_two_regions(self):
        rectangle(self.sk, 0, 0, 50, 50, fully=False)
        rectangle(self.sk, 100, 0, 50, 50, fully=False)
        self.doc.recompute()
        self.assertEqual([r["depth"] for r in SketchTools.regions(self.sk)], [0, 0])

    def test_an_open_chain_has_no_region(self):
        self.sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(10, 0, 0)), False)
        self.doc.recompute()
        self.assertEqual(SketchTools.regions(self.sk), [])

    def test_crossing_loops_are_refused(self):
        rectangle(self.sk, 0, 0, 100, 100, fully=False)
        self.sk.addGeometry(Part.Circle(V(100, 50, 0), V(0, 0, 1), 30), False)
        self.doc.recompute()
        with self.assertRaises(ValueError):
            SketchTools.regions(self.sk)

    def test_show_regions_replaces_its_group_and_follows_the_placement(self):
        rectangle(self.sk, 0, 0, 100, 100, fully=False)
        self.sk.Placement = FreeCAD.Placement(V(0, 0, 10), FreeCAD.Rotation())
        self.doc.recompute()
        group = SketchTools.show_regions(self.sk)
        self.assertEqual(len(group.Group), 1)
        self.assertAlmostEqual(group.Group[0].Shape.BoundBox.ZMin, 10, places=6)
        again = SketchTools.show_regions(self.sk)
        self.assertEqual(len([o for o in self.doc.Objects if o.Name.startswith("SketchRegions")]), 2)  # group + 1 region
        self.assertEqual(len(again.Group), 1)


class TestExitCriteria(SketchCase):
    """Design doc Phase 1: a fully constrained 100-entity sketch solves in < 50 ms, dimension
    edits propagate, the conflict diagnosis identifies the offending constraint."""

    def build(self):
        for i in range(25):  # 25 rectangles of 4 lines = 100 entities
            rectangle(self.sk, 30 * (i % 5), 30 * (i // 5), 20, 10)
        self.doc.recompute()

    def test_hundred_entities_fully_constrained(self):
        self.build()
        self.assertEqual(len(self.sk.Geometry), 100)
        self.assertEqual(self.sk.solve(), 0)
        self.assertEqual(self.sk.FullyConstrained, True)

    def test_solve_under_50_ms(self):
        self.build()
        runs = []
        for _ in range(5):
            t = time.perf_counter()
            self.sk.solve()
            runs.append((time.perf_counter() - t) * 1000)
        self.assertLess(min(runs), 50, runs)

    def test_dimension_edit_propagates(self):
        self.build()
        index = next(i for i, c in enumerate(self.sk.Constraints) if c.Type == "DistanceX" and c.First == 0 and c.Second == 0)
        self.sk.setDatum(index, FreeCAD.Units.Quantity("35 mm"))
        self.doc.recompute()
        line = self.sk.Geometry[0]
        self.assertAlmostEqual(line.EndPoint.x - line.StartPoint.x, 35, places=6)
        top = self.sk.Geometry[2]  # the opposite side follows through the coincident corners
        self.assertAlmostEqual(abs(top.StartPoint.x - top.EndPoint.x), 35, places=6)

    def test_conflict_is_identified(self):
        self.build()
        self.sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 40))  # contradicts the 20
        found = SketchTools.diagnose(self.sk)
        self.assertEqual(found[0][0], len(self.sk.Constraints))


class TestSelection(SketchCase):
    def test_parse_vector(self):
        self.assertEqual(SketchTools.parse_vector("10, -5"), V(10, -5, 0))
        self.assertEqual(SketchTools.parse_vector("3 4"), V(3, 4, 0))
        with self.assertRaises(ValueError):
            SketchTools.parse_vector("3")

    def test_selection_of_edges_vertices_and_external_edges(self):
        g = rectangle(self.sk, 0, 0, 10, 10, fully=False)

        class Sel:
            Object = self.sk
            SubElementNames = ["Edge1", "Edge3", "ExternalEdge1", "Vertex1"]

        sketch, edges, points = SketchTools.selection_in([Sel])
        self.assertIs(sketch, self.sk)
        self.assertEqual(edges, [0, 2, -3])
        self.assertEqual(points, [tuple(self.sk.getGeoVertexIndex(0))])

    def test_selection_needs_one_sketch(self):
        with self.assertRaises(ValueError):
            SketchTools.selection_in([])

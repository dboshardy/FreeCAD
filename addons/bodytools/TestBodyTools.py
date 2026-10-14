# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs in stock FreeCAD: FreeCADCmd -t TestBodyTools."""

import json
import math
import os
import tempfile
import unittest

import FreeCAD
import Part
import Sketcher

import Features
import History
import Inspect
import Parameters

V = FreeCAD.Vector


def box(x=10, y=20, z=30):
    return Part.makeBox(x, y, z)


class TestParameters(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("P")
        self.sheet = self.doc.addObject("Spreadsheet::Sheet", "Params")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def test_json_load(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p.json")
            json.dump({"plate_l": 100, "plate_w": "60 mm"}, open(p, "w"))
            self.assertEqual(Parameters.load_json(self.sheet, p), ["plate_l", "plate_w"])
        self.assertEqual(self.sheet.get("plate_l"), 100)
        self.assertAlmostEqual(self.sheet.get("plate_w").getValueAs("mm").Value, 60)

    def test_json_reload_updates(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p.json")
            json.dump({"plate_l": 1}, open(p, "w"))
            Parameters.load_json(self.sheet, p)
            json.dump({"plate_l": 2}, open(p, "w"))
            Parameters.load_json(self.sheet, p)
        self.assertEqual(self.sheet.get("plate_l"), 2)

    def test_json_rejects_bad(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p.json")
            for bad in ([1], {"a b": 1}, {"a": [1]}, {"a": True}):
                json.dump(bad, open(p, "w"))
                with self.assertRaises(ValueError):
                    Parameters.load_json(self.sheet, p)

    def test_variants(self):
        Parameters.set_parameter(self.sheet, "plate_l", 10)
        b = self.doc.addObject("Part::Box", "Box")
        b.setExpression("Length", "Params.plate_l")
        t = Parameters.VariantTable(self.doc, self.sheet)
        t.define("small", params={"plate_l": 10})
        t.define("big", params={"plate_l": 50}, props={"Box.Width": 7})
        self.assertEqual(sorted(t.names()), ["big", "small"])
        self.assertEqual(t.apply("big"), [])
        self.assertAlmostEqual(b.Length.Value, 50)
        self.assertAlmostEqual(b.Width.Value, 7)
        self.assertEqual(t.apply("small"), [])
        self.assertAlmostEqual(b.Length.Value, 10)
        self.assertEqual(t.obj.Active, "small")
        t.set_row("small", "params", "plate_l", 12)
        t.apply("small")
        self.assertAlmostEqual(b.Length.Value, 12)
        self.assertIn(("big", "props", "Box.Width", 7), t.as_rows())
        # saved with the document
        t2 = Parameters.VariantTable(self.doc, self.sheet)
        self.assertEqual(sorted(t2.names()), ["big", "small"])


class TestFeatures(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("F")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def _sketch(self, geos):
        sk = self.doc.addObject("Sketcher::SketchObject", "Sk")
        for g in geos:
            sk.addGeometry(g)
        self.doc.recompute()
        return sk

    def test_thin_wall_closed(self):
        sk = self._sketch([Part.Circle(V(0, 0, 0), V(0, 0, 1), 10)])
        f = Features.make_thin_wall(sk)
        f.Thickness, f.Length = 2, 5
        self.doc.recompute()
        # ring between r=9 and r=11
        self.assertAlmostEqual(f.Shape.Volume, math.pi * (11**2 - 9**2) * 5, delta=1e-6)

    def test_thin_wall_circle_symmetric_stays_exact(self):
        sk = self._sketch([Part.Circle(V(0, 0, 0), V(0, 0, 1), 10)])
        f = Features.make_thin_wall(sk)
        f.Thickness, f.Length, f.Symmetric = 2, 6, True
        self.doc.recompute()
        self.assertAlmostEqual(f.Shape.Volume, math.pi * (11**2 - 9**2) * 6, delta=1e-5)
        self.assertAlmostEqual(f.Shape.BoundBox.ZMin, -3, places=6)

    def test_thin_wall_open_and_symmetric(self):
        line = Part.LineSegment(V(0, 0, 0), V(20, 0, 0))
        sk = self._sketch([line])
        f = Features.make_thin_wall(sk)
        f.Thickness, f.Length, f.Symmetric = 2, 10, True
        self.doc.recompute()
        self.assertAlmostEqual(f.Shape.Volume, 2 * 20 * 10 + 0, delta=2 * 2 * 10 * 1.0 + 1e-6)
        self.assertAlmostEqual(f.Shape.BoundBox.ZMin, -5, places=6)
        self.assertAlmostEqual(f.Shape.BoundBox.ZMax, 5, places=6)

    def test_rib_fused_to_base(self):
        base = self.doc.addObject("Part::Box", "Base")
        base.Length, base.Width, base.Height = 20, 20, 2
        sk = self._sketch([Part.LineSegment(V(0, 10, 0), V(20, 10, 0))])
        rib = Features.make_rib(sk, base)
        rib.Thickness, rib.Length = 2, 8
        self.doc.recompute()
        self.assertEqual(len(rib.Shape.Solids), 1)
        self.assertGreater(rib.Shape.Volume, base.Shape.Volume)

    def test_variable_fillet_volume_between_constant_fillets(self):
        b = self.doc.addObject("Part::Box", "B")
        b.Length = b.Width = b.Height = 20
        self.doc.recompute()
        e = [i + 1 for i, ed in enumerate(b.Shape.Edges)
             if abs(ed.BoundBox.XLength - 20) < 1e-6 and ed.BoundBox.ZMin > 19 and ed.BoundBox.YMin < 1]
        self.assertEqual(len(e), 1)
        f = Features.make_variable_fillet(b, e)
        f.StartRadius, f.EndRadius = 1, 3
        self.doc.recompute()
        full = 20**3
        # material removed by a constant fillet of radius r over length 20: (1 - pi/4) r^2 * 20
        removed = full - f.Shape.Volume
        lo, hi = (1 - math.pi / 4) * 1 * 20, (1 - math.pi / 4) * 9 * 20
        self.assertTrue(lo < removed < hi, removed)

    def test_fill_pattern(self):
        face = Part.Face(Part.makePolygon([V(0, 0, 0), V(30, 0, 0), V(30, 20, 0), V(0, 20, 0), V(0, 0, 0)]))
        pts = Features.fill_points(face, pitch=10, margin=5)
        self.assertEqual(sorted((p.x, p.y) for p in pts), [(5, 5), (5, 15), (15, 5), (15, 15), (25, 5), (25, 15)])
        tool = Part.makeCylinder(1, 2)
        comp = Features.fill_pattern_shape(tool, face, 10, 5)
        self.assertAlmostEqual(comp.Volume, 6 * math.pi * 2, places=6)
        hexp = Features.fill_points(face, 10, 5, hexagonal=True)
        self.assertTrue(len(hexp) >= 4)


class TestInspect(unittest.TestCase):
    def test_draft(self):
        cone = Part.makeCone(10, 8, 20)  # 2 mm over 20 mm: atan(0.1) deg of draft
        res = {i: a for i, a, ok in Inspect.draft_analysis(cone, V(0, 0, 1), 1.0)}
        side = [a for a in res.values() if 0 < a < 45]
        self.assertEqual(len(side), 1)
        self.assertAlmostEqual(side[0], math.degrees(math.atan(2 / 20)), places=4)
        cyl = Part.makeCylinder(10, 20)
        self.assertFalse(all(ok for _, _, ok in Inspect.draft_analysis(cyl, V(0, 0, 1), 1.0)))

    def test_curvature(self):
        cyl = Part.makeCylinder(5, 10)
        rows = Inspect.curvature(cyl)
        ks = [max(abs(lo), abs(hi)) for _, lo, hi in rows]
        self.assertTrue(any(abs(k - 1 / 5) < 1e-9 for k in ks))

    def test_interference(self):
        a, b, c = box(), box(), box()
        b.translate(V(5, 0, 0))
        c.translate(V(100, 0, 0))
        hits = Inspect.interference({"a": a, "b": b, "c": c})
        self.assertEqual([(x, y) for x, y, _ in hits], [("a", "b")])
        self.assertAlmostEqual(hits[0][2], 5 * 20 * 30, places=6)

    def test_wall_thickness(self):
        outer = Part.makeBox(20, 20, 20)
        inner = Part.makeBox(16, 16, 16)
        inner.translate(V(2, 2, 2))
        shell = outer.cut(inner)
        th = dict(Inspect.wall_thickness(shell))
        self.assertAlmostEqual(min(th.values()), 2, places=3)


def _bracket(doc):
    """30-feature plate with 12 holes, driven by 5 spreadsheet parameters. Returns (body, volume fn)."""
    import Sketcher as S

    sheet = doc.addObject("Spreadsheet::Sheet", "Params")
    values = dict(plate_l=100, plate_w=60, plate_t=6, hole_r=4, boss_h=10)
    for name, v in values.items():
        Parameters.set_parameter(sheet, name, v)
    doc.recompute()
    body = doc.addObject("PartDesign::Body", "Body")
    xy = body.Origin.OriginFeatures[3]

    def sketch(name, z_expr=None):
        sk = body.newObject("Sketcher::SketchObject", name)
        sk.AttachmentSupport = [(xy, "")]
        sk.MapMode = "FlatFace"
        if z_expr:
            sk.setExpression("AttachmentOffset.Base.z", z_expr)
        return sk

    def rect(sk, x0, y0, wx, wy, xexpr, yexpr, wxexpr, wyexpr):
        pts = [V(x0, y0, 0), V(x0 + wx, y0, 0), V(x0 + wx, y0 + wy, 0), V(x0, y0 + wy, 0)]
        for i in range(4):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
        for i in range(4):
            sk.addConstraint(S.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
        sk.addConstraint(S.Constraint("Horizontal", 0))
        sk.addConstraint(S.Constraint("Horizontal", 2))
        sk.addConstraint(S.Constraint("Vertical", 1))
        sk.addConstraint(S.Constraint("Vertical", 3))
        cx = sk.addConstraint(S.Constraint("DistanceX", -1, 1, 0, 1, x0))
        cy = sk.addConstraint(S.Constraint("DistanceY", -1, 1, 0, 1, y0))
        w = sk.addConstraint(S.Constraint("DistanceX", 0, 1, 0, 2, wx))
        h = sk.addConstraint(S.Constraint("DistanceY", 1, 1, 1, 2, wy))
        for idx, nm, ex in ((cx, "posx", xexpr), (cy, "posy", yexpr), (w, "wide", wxexpr), (h, "tall", wyexpr)):
            sk.renameConstraint(idx, nm)
            sk.setExpression("Constraints." + nm, ex)

    sk = sketch("PlateSketch")
    rect(sk, 0, 0, 100, 60, "0 mm", "0 mm", "Params.plate_l", "Params.plate_w")
    pad = body.newObject("PartDesign::Pad", "Plate")
    pad.Profile = sk
    pad.setExpression("Length", "Params.plate_t")
    doc.recompute()

    for i in range(4):
        for j in range(3):
            sk = sketch("HoleSketch%d_%d" % (i, j), "Params.plate_t")
            sk.addGeometry(Part.Circle(V(100 * (i + 1) / 5, 60 * (j + 1) / 4, 0), V(0, 0, 1), 4))
            cx = sk.addConstraint(S.Constraint("DistanceX", -1, 1, 0, 3, 100 * (i + 1) / 5))
            cy = sk.addConstraint(S.Constraint("DistanceY", -1, 1, 0, 3, 60 * (j + 1) / 4))
            r = sk.addConstraint(S.Constraint("Radius", 0, 4))
            for idx, nm, ex in (
                (cx, "posx", "Params.plate_l * %s" % ((i + 1) / 5)),
                (cy, "posy", "Params.plate_w * %s" % ((j + 1) / 4)),
                (r, "holeradius", "Params.hole_r"),
            ):
                sk.renameConstraint(idx, nm)
                sk.setExpression("Constraints." + nm, ex)
            pk = body.newObject("PartDesign::Pocket", "Hole%d_%d" % (i, j))
            pk.Profile = sk
            pk.Type = 1  # through all
            doc.recompute()

    sk = sketch("BossSketch", "Params.plate_t")
    rect(sk, 0, 0, 10, 7.5, "0 mm", "0 mm", "Params.plate_l / 10", "Params.plate_w / 8")
    boss = body.newObject("PartDesign::Pad", "Boss")
    boss.Profile = sk
    boss.setExpression("Length", "Params.boss_h")
    sk = sketch("TabSketch", "Params.plate_t")
    rect(sk, 90, 52.5, 10, 7.5, "Params.plate_l * 0.9", "Params.plate_w - Params.plate_w / 8", "Params.plate_l / 10", "Params.plate_w / 8")
    tab = body.newObject("PartDesign::Pad", "Tab")
    tab.Profile = sk
    tab.setExpression("Length", "Params.boss_h / 2")
    doc.recompute()

    def volume(L, W, T, R, H):
        return L * W * T - 12 * math.pi * R**2 * T + (L / 10) * (W / 8) * (H + H / 2)

    return body, sheet, volume


class TestExitCriteria(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("Bracket")
        self.body, self.sheet, self.volume = _bracket(self.doc)

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def _broken(self):
        return [o.Name for o in self.doc.Objects if "Invalid" in o.State or "Error" in o.State]

    def _check(self, **p):
        short = dict(plate_l="L", plate_w="W", plate_t="T", hole_r="R", boss_h="H")
        v = dict(L=100, W=60, T=6, R=4, H=10)
        v.update({short[k]: x for k, x in p.items()})
        got = self.body.Shape.Volume
        want = self.volume(**v)
        self.assertLess(abs(got - want) / want, 1e-6, (got, want, p))
        self.assertEqual(self._broken(), [])

    def test_thirty_features(self):
        feats = [o for o in self.body.Group if o.isDerivedFrom("PartDesign::Feature") or o.isDerivedFrom("Sketcher::SketchObject")]
        self.assertEqual(len(feats), 30)
        self._check()

    def test_each_parameter_rebuilds(self):
        for name, value in dict(plate_l=140, plate_w=80, plate_t=9, hole_r=3, boss_h=15).items():
            Parameters.set_parameter(self.sheet, name, value)
            self.doc.recompute()
            self._check(**{name: value})
            Parameters.set_parameter(self.sheet, name, dict(plate_l=100, plate_w=60, plate_t=6, hole_r=4, boss_h=10)[name])
            self.doc.recompute()
        Parameters.set_parameter(self.sheet, "plate_l", 130)
        Parameters.set_parameter(self.sheet, "plate_t", 8)
        self.doc.recompute()
        self._check(plate_l=130, plate_t=8)

    def test_mass_matches_density(self):
        rho = 7.85e-6  # kg/mm^3
        v = self.volume(100, 60, 6, 4, 10)
        self.assertLess(abs(self.body.Shape.Volume * rho - v * rho) / (v * rho), 1e-6)

    def test_suppress(self):
        hole = self.doc.getObject("Hole1_1")
        hole.Suppressed = True
        self.doc.recompute()
        want = self.volume(100, 60, 6, 4, 10) + math.pi * 16 * 6
        self.assertLess(abs(self.body.Shape.Volume - want) / want, 1e-6)
        self.assertEqual(self._broken(), [])
        hole.Suppressed = False
        self.doc.recompute()
        self._check()

    def test_reorder(self):
        boss, tab = self.doc.getObject("Boss"), self.doc.getObject("Tab")
        ok, why = History.can_move(self.body, boss, 0)
        self.assertFalse(ok, why)  # boss pad would precede its own sketch
        ok, why = History.can_move(self.body, self.doc.getObject("Plate"), len(self.body.Group) - 1)
        self.assertFalse(ok, why)  # holes would have nothing to cut
        # move the two end pads (with their sketches) ahead of the holes: volume unchanged
        for pad, sk in ((tab, self.doc.getObject("TabSketch")), (boss, self.doc.getObject("BossSketch"))):
            target = self.body.Group.index(self.doc.getObject("Hole0_0").Profile[0])
            History.move(self.body, sk, target)
            History.move(self.body, pad, target + 1)
        self.assertLess(self.body.Group.index(tab), self.body.Group.index(self.doc.getObject("Hole0_0")))
        self.assertEqual(self._broken(), [])
        self._check()

    def test_marker(self):
        hole = self.doc.getObject("Hole0_0")
        History.set_marker(self.body, hole)
        want = 100 * 60 * 6 - math.pi * 16 * 6
        self.assertLess(abs(self.body.Shape.Volume - want) / want, 1e-6)
        History.set_marker(self.body, self.doc.getObject("Tab"))
        self._check()

    def test_variants_on_bracket(self):
        t = Parameters.VariantTable(self.doc, self.sheet)
        t.define("thick", params={"plate_t": 10, "hole_r": 3})
        t.define("light", params={"plate_t": 4, "hole_r": 4}, suppress={"Hole0_0": True})
        self.assertEqual(t.apply("thick"), [])
        self._check(plate_t=10, hole_r=3)
        self.assertEqual(t.apply("light"), [])
        want = self.volume(100, 60, 4, 4, 10) + math.pi * 16 * 4
        self.assertLess(abs(self.body.Shape.Volume - want) / want, 1e-6)

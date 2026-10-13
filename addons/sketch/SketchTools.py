# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketcher additions on FreeCAD's SketchObject: tangent circle, stretch, conflict diagnosis, regions."""

import math

import FreeCAD
import Part
import Sketcher

V = FreeCAD.Vector
CIRCLE_TYPES = ("Part::GeomCircle", "Part::GeomArcOfCircle")


def _sample(geo):
    """A point on or near a curve and a length scale, for a first guess."""
    if geo.TypeId == "Part::GeomLineSegment":
        return (geo.StartPoint + geo.EndPoint) * 0.5, geo.length()
    if geo.TypeId in CIRCLE_TYPES:
        return geo.Center, geo.Radius * 2
    raise ValueError("a tangent circle needs lines, circles or arcs")


def _block(sketch, geo_ids):
    """Temporarily fixes the curves, so the solver places the new circle instead of
    dragging them. A curve the constraints already pin gets no block (it would be
    redundant). Returns the indices of the blocks added."""
    added = []
    for g in geo_ids:
        index = sketch.addConstraint(Sketcher.Constraint("Block", g))
        sketch.solve()
        if index + 1 in sketch.RedundantConstraints or index + 1 in sketch.ConflictingConstraints:
            sketch.delConstraint(index)
        else:
            added.append(index)
    return added


def _unblock(sketch, blocks):
    for index in sorted(blocks, reverse=True):
        sketch.delConstraint(index)
    sketch.solve()


def tangent_circle(sketch, geo_ids):
    """Adds a circle tangent to 1 to 3 curves (lines, circles, arcs) of the sketch
    and returns its geometry id. With fewer than three curves the circle keeps
    its freedom (radius, position along the solutions): constrain it as needed.
    Tries several first guesses for the solver; ValueError when none converges."""
    if not 1 <= len(geo_ids) <= 3:
        raise ValueError("select one to three curves")
    samples = [_sample(sketch.Geometry[g]) for g in geo_ids]
    blocks = _block(sketch, geo_ids)
    centre = sum((p for p, _ in samples), V()) * (1 / len(samples))
    scale = max(10.0, max(s for _, s in samples) / 4)
    for factor in (0.5, 1.0, 2.0):
        for k in range(8):
            a = k * math.pi / 4
            guess = centre + V(math.cos(a), math.sin(a), 0) * (scale * factor)
            gid = sketch.addGeometry(Part.Circle(guess, V(0, 0, 1), scale * factor / 2), False)
            for g in geo_ids:
                sketch.addConstraint(Sketcher.Constraint("Tangent", gid, g))
            if sketch.solve() == 0 and not sketch.ConflictingConstraints and not sketch.RedundantConstraints:
                _unblock(sketch, blocks)
                return gid
            sketch.delGeometry(gid)  # takes its constraints with it
    _unblock(sketch, blocks)
    raise ValueError("no circle tangent to these curves was found")


def stretch(sketch, points, vector):
    """Moves points [(geoId, posId)] of the sketch by `vector`, letting the
    constraints drag what is attached (a rectangle's side lengthens). Returns
    the solver result of the last move (0 = solved)."""
    # Targets first: a move can drag the next point along (a vertical side), which
    # must not be moved a second time.
    targets = [(g, p, sketch.getPoint(g, p) + vector) for g, p in points]
    for geo_id, pos, target in targets:
        sketch.moveGeometry(geo_id, pos, target, False)
    return sketch.solve()


def _copy(sketch):
    doc = sketch.Document
    copy = doc.addObject("Sketcher::SketchObject", "_SketchDiagnosis")
    for i, geo in enumerate(sketch.Geometry):
        copy.addGeometry(geo, sketch.getConstruction(i))
    copy.addConstraint(list(sketch.Constraints))
    return copy


def _clean(sketch):
    return sketch.solve() == 0 and not sketch.ConflictingConstraints and not sketch.RedundantConstraints


def diagnose(sketch):
    """For a sketch with conflicting or redundant constraints: the constraints
    whose removal alone makes it solve, last added first.
    Returns [(1-based index, type, name, text)]; [] when the sketch is fine or
    no single removal fixes it."""
    sketch.solve()
    suspects = sorted(set(sketch.ConflictingConstraints) | set(sketch.RedundantConstraints))
    if not suspects:
        return []
    doc, out = sketch.Document, []
    for number in sorted(suspects, reverse=True):
        probe = _copy(sketch)
        try:
            probe.delConstraint(number - 1)
            if _clean(probe):
                c = sketch.Constraints[number - 1]
                label = f" '{c.Name}'" if c.Name else ""
                out.append((number, c.Type, c.Name, f"Remove constraint {number} ({c.Type}{label}): the sketch then solves"))
        finally:
            doc.removeObject(probe.Name)
    return out


def regions(sketch):
    """Closed regions of the sketch's non-construction geometry, with nesting.
    Returns [{"face", "depth", "wires"}]: a loop with loops inside it gives a face
    with holes; each inner loop gives its own region (depth + 1). Crossing loops
    are not split: ValueError."""
    edges = list(sketch.Shape.Edges)
    loops = [Part.Wire(group) for group in Part.sortEdges(edges)] if edges else []
    loops = [w for w in loops if w.isClosed()]
    faces = [Part.Face(w) for w in loops]
    for i, a in enumerate(faces):
        for b in faces[i + 1 :]:
            if a.Wires[0].distToShape(b.Wires[0])[0] < 1e-6:
                raise ValueError("closed loops touch or cross: regions are not defined")
    inside = [
        [j for j, other in enumerate(faces) if j != i and other.isInside(loops[i].Vertexes[0].Point, 1e-7, True)]
        for i in range(len(faces))
    ]
    out = []
    for i, face in enumerate(faces):
        children = [j for j in range(len(faces)) if i in inside[j] and not any(i in inside[k] and k in inside[j] for k in range(len(faces)) if k != j)]
        shape = face.cut([faces[j] for j in children]) if children else face
        out.append({"face": shape, "depth": len(inside[i]), "wires": [i] + children})
    return sorted(out, key=lambda r: r["depth"])


def show_regions(sketch):
    """Group '<sketch>Regions' with one coloured face per region (depth 0 blue,
    1 orange, 2 green ...), where the sketch is. Replaces an earlier group."""
    doc = sketch.Document
    name = f"{sketch.Name}Regions"
    old = doc.getObject(name)
    if old:
        for child in list(old.Group):
            doc.removeObject(child.Name)
        doc.removeObject(old.Name)
    group = doc.addObject("App::DocumentObjectGroup", name)
    palette = [(0.25, 0.5, 0.9), (0.95, 0.6, 0.2), (0.3, 0.75, 0.4), (0.8, 0.35, 0.7)]
    for n, region in enumerate(regions(sketch), start=1):
        obj = doc.addObject("Part::Feature", f"{name}{n}")
        obj.Label = f"Region {n} (depth {region['depth']})"
        obj.Shape = region["face"]  # already in the sketch's placement (sketch.Shape is global)
        group.addObject(obj)
        if FreeCAD.GuiUp:
            obj.ViewObject.ShapeColor = palette[region["depth"] % len(palette)]
            obj.ViewObject.Transparency = 50
    doc.recompute()
    return group


def parse_vector(text):
    """'10, 5' or '10 5' (mm) to a vector in the sketch plane."""
    parts = text.replace(",", " ").split()
    if len(parts) != 2:
        raise ValueError("enter two numbers: dx, dy in mm")
    return V(float(parts[0]), float(parts[1]), 0)


def selection_in(selection):
    """(sketch, curve geo ids, vertices [(geoId, posId)]) from selection objects of a single sketch;
    in edit mode the selection holds sub-element names of the edited sketch."""
    sketch, edges, points = None, [], []
    for sel in selection:
        obj = sel.Object
        if obj.TypeId != "Sketcher::SketchObject":
            continue
        if sketch is not None and obj != sketch:
            raise ValueError("select elements of one sketch")
        sketch = obj
        for name in sel.SubElementNames:
            if name.startswith("Edge") and name[4:].isdigit():
                edges.append(int(name[4:]) - 1)
            elif name.startswith("ExternalEdge") and name[12:].isdigit():
                edges.append(-int(name[12:]) - 2)
            elif name.startswith("Vertex") and name[6:].isdigit():
                points.append(tuple(sketch.getGeoVertexIndex(int(name[6:]) - 1)))
    if sketch is None:
        raise ValueError("select a sketch")
    return sketch, edges, points

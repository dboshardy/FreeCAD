# SPDX-License-Identifier: LGPL-2.1-or-later
"""Thin-wall extrude, rib, variable-radius fillet and fill pattern.

Each is a Part::FeaturePython with ordinary properties, so spreadsheet expressions
can drive them. They are plain Part features: placing them inside a PartDesign Body
is not supported (see docs/gaps/phase-2.md).
"""

import math

import FreeCAD
import Part


def _wire_of(sketch):
    wires = sketch.Shape.Wires
    if not wires:
        raise ValueError("%s has no wire" % sketch.Name)
    return wires[0]


def _normal(sketch):
    return sketch.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))


def thin_wall_shape(wire, thickness, length, normal, symmetric=False):
    """Sweep `wire` along `normal` by `length`, then thicken the surface by `thickness`
    (half each side). Works for open and closed wires, straight lines included.
    """
    n = FreeCAD.Vector(normal)
    n.normalize()
    if symmetric:
        # move the wire, not the solid: Shape.translate only sets Placement, which a
        # Part feature overwrites, and transformGeometry turns curves into splines
        wire = wire.copy()
        wire.translate(n * (-length / 2.0))
    surface = wire.extrude(n * length)
    half = thickness / 2.0
    # fill=True makes a solid between the surface and its offset: one side per call
    side_a = surface.makeOffsetShape(half, 1e-6, False, False, 0, 2, True)
    side_b = surface.makeOffsetShape(-half, 1e-6, False, False, 0, 2, True)
    solid = side_a.fuse(side_b).removeSplitter()
    return solid


def rib_shape(wire, thickness, length, normal, base=None):
    """Rib: open profile thickened and extruded symmetrically; fused to `base` if given."""
    rib = thin_wall_shape(wire, thickness, length, normal, symmetric=True)
    return rib if base is None else base.fuse(rib).removeSplitter()


def variable_fillet(shape, edge_indices, r_start, r_end):
    """Fillet the edges (1-based indices) with radius going from r_start to r_end along each edge."""
    edges = [shape.Edges[i - 1] for i in edge_indices]
    return shape.makeFillet(r_start, r_end, edges)


def fill_points(face, pitch, margin, hexagonal=False):
    """Grid points inside `face` at least `margin` from its boundary."""
    bb = face.BoundBox
    plane_z = face.CenterOfMass.z
    pts = []
    row = 0
    y = bb.YMin + margin
    while y <= bb.YMax - margin + 1e-9:
        x = bb.XMin + margin + (pitch / 2.0 if hexagonal and row % 2 else 0.0)
        while x <= bb.XMax - margin + 1e-9:
            p = FreeCAD.Vector(x, y, plane_z)
            if face.isInside(p, 1e-7, True):
                dist = min(e.distToShape(Part.Vertex(p))[0] for e in face.OuterWire.Edges)
                if dist >= margin - 1e-9:
                    pts.append(p)
            x += pitch
        y += pitch * (math.sqrt(3) / 2.0 if hexagonal else 1.0)
        row += 1
    return pts


def fill_pattern_shape(tool, face, pitch, margin, hexagonal=False):
    """Copies of `tool` (shape centred on the origin) at every fill point of `face`."""
    copies = []
    for p in fill_points(face, pitch, margin, hexagonal):
        c = tool.copy()
        c.translate(p)  # location inside a compound is kept
        copies.append(c)
    return Part.makeCompound(copies)


class _Feature:
    def __init__(self, obj):
        obj.Proxy = self

    def onChanged(self, obj, prop):
        pass


class ThinWall(_Feature):
    def __init__(self, obj, sketch):
        super().__init__(obj)
        obj.addProperty("App::PropertyLink", "Profile", "ThinWall").Profile = sketch
        obj.addProperty("App::PropertyLength", "Thickness", "ThinWall").Thickness = 2
        obj.addProperty("App::PropertyLength", "Length", "ThinWall").Length = 10
        obj.addProperty("App::PropertyBool", "Symmetric", "ThinWall").Symmetric = False

    def execute(self, obj):
        obj.Shape = thin_wall_shape(
            _wire_of(obj.Profile), obj.Thickness.Value, obj.Length.Value,
            _normal(obj.Profile), obj.Symmetric
        )


class Rib(_Feature):
    def __init__(self, obj, sketch, base=None):
        super().__init__(obj)
        obj.addProperty("App::PropertyLink", "Profile", "Rib").Profile = sketch
        obj.addProperty("App::PropertyLink", "Base", "Rib").Base = base
        obj.addProperty("App::PropertyLength", "Thickness", "Rib").Thickness = 2
        obj.addProperty("App::PropertyLength", "Length", "Rib").Length = 10

    def execute(self, obj):
        base = obj.Base.Shape if obj.Base else None
        obj.Shape = rib_shape(
            _wire_of(obj.Profile), obj.Thickness.Value, obj.Length.Value, _normal(obj.Profile), base
        )


class VariableFillet(_Feature):
    def __init__(self, obj, base, edges):
        super().__init__(obj)
        obj.addProperty("App::PropertyLink", "Base", "Fillet").Base = base
        obj.addProperty("App::PropertyIntegerList", "Edges", "Fillet").Edges = list(edges)
        obj.addProperty("App::PropertyLength", "StartRadius", "Fillet").StartRadius = 1
        obj.addProperty("App::PropertyLength", "EndRadius", "Fillet").EndRadius = 2

    def execute(self, obj):
        obj.Shape = variable_fillet(
            obj.Base.Shape, obj.Edges, obj.StartRadius.Value, obj.EndRadius.Value
        )


def _make(cls, name, *args):
    doc = FreeCAD.ActiveDocument
    obj = doc.addObject("Part::FeaturePython", name)
    cls(obj, *args)
    return obj


def make_thin_wall(sketch, name="ThinWall"):
    return _make(ThinWall, name, sketch)


def make_rib(sketch, base=None, name="Rib"):
    return _make(Rib, name, sketch, base)


def make_variable_fillet(base, edges, name="VariableFillet"):
    return _make(VariableFillet, name, base, edges)

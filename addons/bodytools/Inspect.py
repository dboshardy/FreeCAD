# SPDX-License-Identifier: LGPL-2.1-or-later
"""Inspection: draft, curvature, interference and wall thickness. Read-only, return plain data."""

import math

import FreeCAD
import Part


def draft_analysis(shape, pull, min_angle_deg=1.0):
    """Draft angle of every face against pull direction `pull`.

    Draft angle = 90 degrees minus the angle between the face normal and the pull
    direction, measured at the face centre. Returns [(face index 1-based, angle deg, ok)].
    ok is True when the face leans away from the pull by at least `min_angle_deg`
    (angle >= min); faces parallel to the pull (0 deg) and undercuts (negative) fail.
    Planar faces perpendicular to the pull are reported as 90 deg.
    """
    pull = FreeCAD.Vector(pull)
    pull.normalize()
    out = []
    for i, f in enumerate(shape.Faces, 1):
        u0, u1, v0, v1 = f.ParameterRange
        n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        angle = 90.0 - math.degrees(math.acos(max(-1.0, min(1.0, n.dot(pull)))))
        out.append((i, angle, abs(angle) >= min_angle_deg and angle > 0))
    return out


def curvature(shape, samples=5):
    """Per face (min, max) principal curvature seen over a samples x samples grid.

    Returns [(face index 1-based, k_min, k_max)]. Curvatures are 1/length, sign
    follows the face normal. Sample points that the kernel cannot evaluate are skipped.
    """
    out = []
    for i, f in enumerate(shape.Faces, 1):
        u0, u1, v0, v1 = f.ParameterRange
        lo, hi = math.inf, -math.inf
        for a in range(samples):
            for b in range(samples):
                u = u0 + (u1 - u0) * (a + 0.5) / samples
                v = v0 + (v1 - v0) * (b + 0.5) / samples
                try:
                    k1, k2 = f.curvatureAt(u, v)
                except Exception:
                    continue
                lo = min(lo, k1, k2)
                hi = max(hi, k1, k2)
        out.append((i, lo, hi))
    return out


def interference(shapes, min_volume=1e-9):
    """Pairs of `shapes` (name -> Shape) whose solids overlap: [(a, b, overlap volume)]."""
    names = list(shapes)
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if not shapes[a].BoundBox.intersect(shapes[b].BoundBox):
                continue
            vol = shapes[a].common(shapes[b]).Volume
            if vol > min_volume:
                out.append((a, b, vol))
    return out


def wall_thickness(shape, samples=3, limit=None):
    """Estimated wall thickness per face: [(face index 1-based, min thickness)].

    For each sample point on a face, a ray goes inward along the reversed normal. The
    thickness is the distance to the first point where the ray leaves the solid.
    Only the sampled points are checked, so a thin spot between samples can be missed.
    `limit` is the ray length, default the bounding-box diagonal.
    """
    limit = limit or shape.BoundBox.DiagonalLength
    out = []
    for i, f in enumerate(shape.Faces, 1):
        u0, u1, v0, v1 = f.ParameterRange
        best = math.inf
        for a in range(samples):
            for b in range(samples):
                u = u0 + (u1 - u0) * (a + 0.5) / samples
                v = v0 + (v1 - v0) * (b + 0.5) / samples
                p = f.valueAt(u, v)
                n = f.normalAt(u, v)
                # Orientation of a face on a solid can flip the normal: test with inside
                probe = p - n * 1e-4
                if not shape.isInside(probe, 1e-7, True):
                    n = -n
                    probe = p - n * 1e-4
                    if not shape.isInside(probe, 1e-7, True):
                        continue
                ray = Part.makeLine(p - n * 1e-4, p - n * limit)
                inside = shape.common(ray)
                if inside.Edges:
                    best = min(best, max(e.Length for e in inside.Edges) + 1e-4)
        out.append((i, best))
    return out

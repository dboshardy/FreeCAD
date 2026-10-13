# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: structural member geometry (design doc §5.2). No FreeCAD imports.
"""A member is a lumber profile (thickness x depth) swept along the straight
line from start to end, centred on that line. Square end cuts.

Profile orientation (before roll): the depth runs as close to vertical as the
member allows, so joists, rafters and headers stand on edge; a vertical member
(stud, post) has its depth along global Y. roll turns the profile about the
member's own axis (90 lays a joist flat, e.g. for a wall plate).
"""

import math


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _scale(a, k):
    return tuple(x * k for x in a)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return _scale(a, 1 / n)


def end_extension(depth, angle):
    """How far an end cut at `angle` degrees from square reaches past the
    member's end point on its long side (the cut passes through the end point
    on the centre line)."""
    return depth / 2 * abs(math.tan(math.radians(angle)))


def frame(start, end, roll=0.0):
    """(length, x, y, z): member length and unit axes. z runs start -> end,
    y is the profile depth direction, x the thickness direction (x = y cross z).
    Raises ValueError for a zero-length member."""
    axis = _sub(end, start)
    length = math.sqrt(_dot(axis, axis))
    if length < 1e-6:
        raise ValueError("member start and end are the same point")
    z = _unit(axis)
    up = (0.0, 0.0, 1.0)
    if abs(_dot(z, up)) > 0.999:
        y = (0.0, 1.0, 0.0)
    else:
        y = _unit(_sub(up, _scale(z, _dot(up, z))))
    x = _cross(y, z)
    if roll:
        a = math.radians(roll)
        c, s = math.cos(a), math.sin(a)
        x, y = (
            tuple(c * xi + s * yi for xi, yi in zip(x, y)),
            tuple(-s * xi + c * yi for xi, yi in zip(x, y)),
        )
    return length, x, y, z

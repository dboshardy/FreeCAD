# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: the one part model of the Construction workbench (design doc §5.1.1).
# No FreeCAD imports.
"""A part: a named, axis-aligned box of one material in one coordinate frame.

Cabinets, framing, sheathing and joinery all describe their pieces as Parts,
so the cut list, joinery and drawings handle every object the same way.
"""

from dataclasses import dataclass, replace


@dataclass
class Part:
    name: str
    role: str  # what the part is for, e.g. "carcass", "door", "member", "pocket"
    size: tuple  # (dx, dy, dz)
    pos: tuple  # (x, y, z) of the minimum corner
    grain: str | None = None  # axis the grain runs along: "x", "y", "z" or None
    operations: tuple = ()  # shop work for the cut list, e.g. "mortise 80 x 7 x 25 deep"
    # A pocket that is not its whole box: ("triangle", a, ca, b, cb) is the
    # prism along the third axis whose cross-section is the triangle of the
    # box's (a, b) rectangle with its right angle at the corner (ca, cb)
    # (0 = the low side, 1 = the high side): a miter's waste.
    profile: tuple = ()

    def lo(self, k):
        return self.pos[k]

    def hi(self, k):
        return self.pos[k] + self.size[k]

    def cut_size(self):
        """(length, width, thickness): length along the grain, or the longest side."""
        dims = dict(zip("xyz", self.size))
        thick_axis = min(dims, key=dims.get)
        faces = [a for a in "xyz" if a != thick_axis]
        if self.grain in faces:
            length_axis = self.grain
        else:
            length_axis = max(faces, key=dims.get)
        width_axis = next(a for a in faces if a != length_axis)
        return dims[length_axis], dims[width_axis], dims[thick_axis]

    def moved(self, dx):
        return replace(self, pos=(self.pos[0] + dx, self.pos[1], self.pos[2]))

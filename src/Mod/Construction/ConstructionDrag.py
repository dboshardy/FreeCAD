# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: dragging parts of a build in the 3D view (design doc Phase 5.2).
"""Move a part of a build with the mouse: select one of its faces, run Move,
and the part follows the cursor in the plane of that face, snapping to the
faces of the other parts (against or flush) or to a grid (Build.snap). A
click places it; Esc puts it back. The move writes the part's X, Y, Z cells,
so it is one undo step like any edit."""

import FreeCAD
import FreeCADGui

import Build

translate = FreeCAD.Qt.translate


class DragPart:
    """Moving one part of a build. move_to(point) is what the mouse does; the
    tests call it directly."""

    def __init__(self, build, part, axis, plane):
        self.build, self.part_name, self.axis = build, part, axis
        drawn = build.Proxy.drawn_parts(build)
        self.part = drawn[part]
        self.others = [p for name, p in drawn.items() if name != part]
        self.axes = [k for k in range(3) if k != axis]
        self.start = self.part.pos
        self.grab = None  # first point under the cursor, in build coordinates
        self.plane = plane  # coordinate of the grabbed face along axis
        self.row = next(
            r for r, row in enumerate(build.Proxy.part_rows(build), start=2) if row[0] == part
        )
        build.Document.openTransaction(translate("Construction", "Move {}").format(part))

    def move_to(self, point):
        """point: (x, y, z) in the build's coordinates on the face's plane."""
        if self.grab is None:
            self.grab = point
            return self.start
        target = [self.start[k] + point[k] - self.grab[k] for k in range(3)]
        pos = Build.snap(self.part, target, self.axes, self.others)
        self._write(pos)
        return pos

    def _write(self, pos):
        sheet = self.build.PartsTable
        for k, col in enumerate("FGH"):
            sheet.set(f"{col}{self.row}", f"{pos[k]:g}")
        self.build.touch()
        self.build.Document.recompute()

    def finish(self):
        self.build.Document.commitTransaction()

    def cancel(self):
        self._write(self.start)
        self.build.Document.abortTransaction()
        self.build.Document.recompute()


class MouseDrag:
    """Feeds the mouse to a DragPart: the cursor's ray meets the grabbed
    face's plane (orthographic view: along the view direction)."""

    def __init__(self, drag):
        self.drag = drag
        self.view = FreeCADGui.ActiveDocument.ActiveView
        self.inverse = drag.build.Placement.inverse()
        self.callbacks = [
            ("SoLocation2Event", self.view.addEventCallback("SoLocation2Event", self.on_move)),
            ("SoMouseButtonEvent", self.view.addEventCallback("SoMouseButtonEvent", self.on_click)),
            ("SoKeyboardEvent", self.view.addEventCallback("SoKeyboardEvent", self.on_key)),
        ]
        FreeCAD.Console.PrintMessage(
            translate("Construction", "Move {}: click to place, Esc to cancel\n").format(
                drag.part_name
            )
        )

    def point(self, position):
        p = self.inverse.multVec(self.view.getPoint(*position))
        d = self.inverse.Rotation.multVec(self.view.getViewDirection())
        k = self.drag.axis
        if abs(d[k]) < 1e-9:
            return None  # looking along the face: no intersection
        t = (self.drag.plane - p[k]) / d[k]
        return (p.x + t * d.x, p.y + t * d.y, p.z + t * d.z)

    def on_move(self, event):
        point = self.point(event["Position"])
        if point is not None:
            self.drag.move_to(point)

    def on_click(self, event):
        if event["State"] == "DOWN" and event["Button"] == "BUTTON1":
            self.close()
            self.drag.finish()

    def on_key(self, event):
        if event["Key"] == "ESCAPE" and event["State"] == "DOWN":
            self.close()
            self.drag.cancel()

    def close(self):
        for kind, callback in self.callbacks:
            self.view.removeEventCallback(kind, callback)
        self.callbacks = []


def start(build, part, axis, plane):
    """Starts dragging `part` of `build` with the mouse; returns the MouseDrag."""
    return MouseDrag(DragPart(build, part, axis, plane))

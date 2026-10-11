# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: frameless cabinet generator (design doc §5.4). No FreeCAD imports.
"""Frameless (32 mm system) cabinets with butt-jointed carcasses, and cabinet
runs along a wall.

Axes: x = width (left to right), y = depth (front face of the carcass at
y = 0, back towards +y), z = up from the cabinet's base (floor for base and
tall cabinets, bottom of the carcass for wall cabinets). Sizes in millimetres.
Fronts (doors, drawer fronts) are full overlay and sit in front of the carcass
(y < 0).
"""

import math
from dataclasses import dataclass, replace

import Build
import Joinery
from Parts import Part

KINDS = ("base", "wall", "tall", "sink")
FRONTS = ("doors", "drawers", "drawer_over_doors", "false_front_over_doors")
BLIND_SIDES = ("left", "right")
SLIDE_STEP = 50.0  # drawer slides are sold in 50 mm length steps
MIN_SLIDE = 250.0
MIN_DRAWER_BOX_HEIGHT = 60.0


@dataclass
class Cabinet:
    # base: top stretchers, plinth. wall / tall: full top panel. sink: base with
    # a front stretcher only and no back (open for plumbing).
    kind: str = "base"
    width: float = 600.0
    height: float = 870.0  # base to top of carcass, plinth included
    depth: float = 580.0  # carcass + back, fronts excluded
    thickness: float = 18.0  # carcass and front panels
    back_thickness: float = 6.0  # back and drawer bottoms
    plinth_height: float = 100.0  # 0 for none
    plinth_setback: float = 50.0  # front kick board behind the carcass front
    stretcher_width: float = 100.0
    shelves: int = 1  # ignored with fronts == "drawers"
    shelf_setback: float = 20.0  # from the front edge
    shelf_clearance: float = 1.0  # per side, for adjustable shelves
    fronts: str = "doors"
    doors: int = 0  # 0 = automatic: one up to 600 mm wide, else two
    door_gap: float = 3.0  # between fronts; half of it at the outer edges
    drawers: int = 3  # with fronts == "drawers"
    drawer_front_height: float = 150.0  # top drawer with fronts == "drawer_over_doors"
    drawer_thickness: float = 15.0  # drawer box sides, front and back
    drawer_side_clearance: float = 13.0  # per side, from the slide maker's data
    drawer_height_clearance: float = 40.0  # opening height minus drawer box height
    drawer_rear_clearance: float = 10.0  # behind the drawer box
    # Blind corner: this width of the front is hidden by the run that meets the
    # cabinet and gets a fixed blind panel; doors cover the rest. 0 = none.
    blind_width: float = 0.0
    blind_side: str = "left"
    # Library joint preset joining the sides to the bottom, top and stretchers.
    carcass_joint: str = "joint.confirmat"

    # ------------------------------------------------------------- derived

    def carcass_height(self):
        return self.height - self.plinth_height

    def inner_width(self):
        return self.width - 2 * self.thickness

    def carcass_depth(self):
        return self.depth if self.kind == "sink" else self.depth - self.back_thickness

    def open_width(self):
        """Front width not covered by a blind panel."""
        return self.width - self.blind_width

    def door_count(self):
        return self.doors or (1 if self.open_width() <= 600 else 2)

    def door_width(self):
        n = self.door_count()
        return (self.open_width() - self.door_gap * n) / n

    def slots(self):
        """Front slots bottom to top as (role, z_low, z_high): contiguous bands of
        the carcass face, each holding one row of fronts."""
        k, h, gap = self.plinth_height, self.height, self.door_gap
        if self.fronts == "doors":
            return [("door", k, h)]
        if self.fronts == "drawers":
            step = self.carcass_height() / self.drawers
            return [("drawer", k + i * step, k + (i + 1) * step) for i in range(self.drawers)]
        split = h - self.drawer_front_height - gap
        top = "drawer" if self.fronts == "drawer_over_doors" else "false_front"
        return [("door", k, split), (top, split, h)]

    def drawer_box(self, z_low, z_high):
        """(x, z, width, height, depth) of the drawer box for a drawer slot."""
        t, c = self.thickness, self.drawer_height_clearance
        low = max(z_low, self.plinth_height + t)
        high = min(z_high, self.height - t)
        width = self.inner_width() - 2 * self.drawer_side_clearance
        depth = (
            math.floor((self.carcass_depth() - self.drawer_rear_clearance) / SLIDE_STEP)
            * SLIDE_STEP
        )
        return t + self.drawer_side_clearance, low + c / 2, width, high - low - c, depth

    # ------------------------------------------------------------- checks

    def validate(self):
        """Raises ValueError for sizes that cannot be built."""
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(KINDS)}")
        if self.fronts not in FRONTS:
            raise ValueError(f"fronts must be one of {', '.join(FRONTS)}")
        positive = (
            "width",
            "height",
            "depth",
            "thickness",
            "back_thickness",
            "stretcher_width",
            "drawer_thickness",
        )
        for name in positive:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        non_negative = (
            "plinth_height",
            "plinth_setback",
            "shelf_setback",
            "shelf_clearance",
            "door_gap",
            "drawer_side_clearance",
            "drawer_height_clearance",
            "drawer_rear_clearance",
        )
        for name in non_negative:
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")
        if self.shelves < 0 or self.doors < 0:
            raise ValueError("shelves and doors must not be negative")
        if self.fronts == "drawers" and self.drawers < 1:
            raise ValueError("a drawer bank needs at least one drawer")
        if self.blind_side not in BLIND_SIDES:
            raise ValueError("blind side must be left or right")
        if self.blind_width < 0:
            raise ValueError("blind width must not be negative")
        if self.blind_width and self.fronts != "doors":
            raise ValueError("blind corner cabinets take doors only")
        if self.blind_width and self.open_width() <= self.door_gap:
            raise ValueError("blind width leaves no room for a door")
        t = self.thickness
        if self.inner_width() <= 2 * self.shelf_clearance:
            raise ValueError("width too small for the panel thickness")
        if self.carcass_height() <= 2 * t:
            raise ValueError("height too small for the plinth, top and bottom")
        if self.carcass_depth() <= max(2 * self.stretcher_width, self.shelf_setback):
            raise ValueError("depth too small for stretchers and shelves")
        if self.plinth_height and self.plinth_setback + t > self.carcass_depth() - t:
            raise ValueError("plinth setback too large for the depth")
        if self.door_width() <= 0:
            raise ValueError("door gap too large for the width")
        if self.kind == "sink" and self.carcass_depth() <= self.stretcher_width:
            raise ValueError("depth too small for the stretcher")
        for role, low, high in self.slots():
            if high - low <= self.door_gap:
                raise ValueError("fronts too small for the door gap")
            if role == "false_front":
                continue
            if role == "door":
                opening = min(high, self.height - t) - (self.plinth_height + t)
                if self.shelves and opening / (self.shelves + 1) <= t:
                    raise ValueError("too many shelves for the height")
                if opening <= 0:
                    raise ValueError("drawer front too high for the cabinet")
            else:
                _, _, width, height, depth = self.drawer_box(low, high)
                if width <= 2 * self.drawer_thickness:
                    raise ValueError("cabinet too narrow for a drawer box")
                if height < MIN_DRAWER_BOX_HEIGHT:
                    raise ValueError("drawer front too low for a drawer box")
                if depth < MIN_SLIDE:
                    raise ValueError("cabinet too shallow for drawer slides")

    # ------------------------------------------------------------- parts

    def parts(self):
        self.validate()
        t, tb, k = self.thickness, self.back_thickness, self.plinth_height
        w, h, gap = self.width, self.height, self.door_gap
        box_h, inner_w, carcass_d = self.carcass_height(), self.inner_width(), self.carcass_depth()
        out = [
            Part("Left side", "carcass", (t, carcass_d, box_h), (0, 0, k), "z"),
            Part("Right side", "carcass", (t, carcass_d, box_h), (w - t, 0, k), "z"),
            Part("Bottom", "carcass", (inner_w, carcass_d, t), (t, 0, k), "x"),
        ]
        if self.kind != "sink":
            out.append(Part("Back", "back", (w, tb, box_h), (0, carcass_d, k), "z"))
        if self.kind in ("base", "sink"):
            s = self.stretcher_width
            # Hidden parts: grain None lets the sheet layout rotate them.
            out.append(Part("Front stretcher", "carcass", (inner_w, s, t), (t, 0, h - t)))
        if self.kind == "base":
            out.append(
                Part("Back stretcher", "carcass", (inner_w, s, t), (t, carcass_d - s, h - t))
            )
        if self.kind in ("wall", "tall"):
            out.append(Part("Top", "carcass", (inner_w, carcass_d, t), (t, 0, h - t), "x"))
        if k > 0:
            out.append(Part("Kick board", "plinth", (w, t, k), (0, self.plinth_setback, 0), "x"))
            out.append(Part("Plinth rail", "plinth", (w, t, k), (0, carcass_d - t, 0)))

        slots = self.slots()
        drawer_slots = [(low, high) for role, low, high in slots if role == "drawer"]
        for role, low, high in slots:
            if role == "door":
                out += self._door_parts(low, high)
            elif role == "false_front":
                size = (w - gap, t, high - low - gap)
                out.append(
                    Part("False front", "drawer_front", size, (gap / 2, -t, low + gap / 2), "x")
                )
        for i, (low, high) in enumerate(reversed(drawer_slots)):  # numbered from the top
            label = "Drawer" if len(drawer_slots) == 1 else f"Drawer {i + 1}"
            out += self._drawer_parts(label, low, high)
        return out

    def joint_rows(self):
        """Joints table rows (see Build.py) for parts(): the carcass joint,
        the back nailed on, hinges on the side each door hangs from, shelf
        pins and one slide pair per drawer (counted at the left side)."""
        rows = [
            (side, part, self.carcass_joint, "")
            for side in ("Left side", "Right side")
            for part in ("Bottom", "Top", "Front stretcher", "Back stretcher")
        ]
        rows += [
            (part, "Back", "joint.brad_nail", "")
            for part in ("Left side", "Right side", "Bottom", "Top", "Back stretcher")
        ]
        n, hinge = self.door_count(), "joint.concealed_hinge"
        if n == 1:  # hung from the side away from a blind panel
            rows.append(
                (
                    "Right side" if self.blind_width and self.blind_side == "left" else "Left side",
                    "Door",
                    hinge,
                    "",
                )
            )
        else:
            rows += [("Left side", "Door 1", hinge, ""), ("Right side", f"Door {n}", hinge, "")]
        pins = f"gap={self.shelf_clearance:g}"
        rows += [
            (side, "Shelf *", "joint.shelf_pins", pins) for side in ("Left side", "Right side")
        ]
        slides = f"gap={self.drawer_side_clearance:g}"
        rows.append(("Left side", "Drawer*side", "joint.drawer_slide", slides))
        return rows

    def joined(self, items):
        """Joinery.Result of parts() with joint_rows(); items: the library."""
        return Joinery.apply(self.parts(), Build.rules(self.joint_rows(), items))

    def _door_parts(self, low, high):
        t, gap, k = self.thickness, self.door_gap, self.plinth_height
        n, dw, b = self.door_count(), self.door_width(), self.blind_width
        front_h = high - low - gap
        out = []
        x0 = b if self.blind_side == "left" else 0.0  # left edge of the door area
        for i in range(n):
            label = "Door" if n == 1 else f"Door {i + 1}"
            pos = (x0 + gap / 2 + i * (dw + gap), -t, low + gap / 2)
            out.append(Part(label, "door", (dw, t, front_h), pos, "z"))
        if b:
            # Blind panel: flush with the cabinet's blind edge, half a gap to the doors.
            x = 0.0 if self.blind_side == "left" else self.width - b + gap / 2
            out.append(
                Part(
                    "Blind panel",
                    "blind_panel",
                    (b - gap / 2, t, front_h),
                    (x, -t, low + gap / 2),
                    "z",
                )
            )
        # Shelves evenly spaced in the opening behind the doors.
        bottom = k + t
        opening = min(high, self.height - t) - bottom
        width = self.inner_width() - 2 * self.shelf_clearance
        for i in range(self.shelves):
            z = bottom + (i + 1) * opening / (self.shelves + 1) - t / 2
            size = (width, self.carcass_depth() - self.shelf_setback, t)
            pos = (t + self.shelf_clearance, self.shelf_setback, z)
            out.append(Part(f"Shelf {i + 1}", "shelf", size, pos, "x"))
        return out

    def _drawer_parts(self, label, low, high):
        t, gap, tb, td = self.thickness, self.door_gap, self.back_thickness, self.drawer_thickness
        x, z, bw, bh, bd = self.drawer_box(low, high)
        side_h = bh - tb
        return [
            Part(
                f"{label} front",
                "drawer_front",
                (self.width - gap, t, high - low - gap),
                (gap / 2, -t, low + gap / 2),
                "x",
            ),
            Part(f"{label} bottom", "drawer_bottom", (bw, bd, tb), (x, 0, z), "x"),
            Part(f"{label} side", "drawer_box", (td, bd, side_h), (x, 0, z + tb), "y"),
            Part(f"{label} side", "drawer_box", (td, bd, side_h), (x + bw - td, 0, z + tb), "y"),
            Part(
                f"{label} box front",
                "drawer_box",
                (bw - 2 * td, td, side_h),
                (x + td, 0, z + tb),
                "x",
            ),
            Part(
                f"{label} box back",
                "drawer_box",
                (bw - 2 * td, td, side_h),
                (x + td, bd - td, z + tb),
                "x",
            ),
        ]


# Starting points by preset; heights and depths are common kitchen practice,
# adjust per job. "corner" is a blind-corner base cabinet: 600 mm blind for an
# adjoining run 580 mm deep plus clearance for its door handles.
DEFAULTS = {
    "base": {},
    "wall": {"height": 720.0, "depth": 320.0, "plinth_height": 0.0, "shelves": 2},
    "tall": {"height": 2100.0, "shelves": 4},
    "sink": {"kind": "sink", "width": 800.0, "shelves": 0, "fronts": "false_front_over_doors"},
    "corner": {"width": 1000.0, "blind_width": 600.0},
}
# Bottom of wall cabinets above the floor (900 mm counter + 500 mm clearance).
WALL_ELEVATION = 1400.0


PRESETS = tuple(DEFAULTS)


def defaults(preset):
    """Cabinet for a preset name (a kind, or "corner")."""
    values = {"kind": preset if preset in KINDS else "base", **DEFAULTS[preset]}
    return Cabinet(**values)


# ------------------------------------------------------------------ runs

STANDARD_WIDTHS = (300.0, 400.0, 450.0, 500.0, 600.0, 800.0, 900.0)
FILLER_SIDES = ("both", "left", "right")


def fill_widths(length, standard=STANDARD_WIDTHS):
    """Cabinet widths (largest first) that leave the least filler in `length`;
    among equal fillers, the fewest cabinets. Whole millimetres."""
    total = int(math.floor(length))
    sizes = sorted({int(round(w)) for w in standard if w > 0})
    if not sizes:
        raise ValueError("no standard widths given")
    # fewest[n] = fewest cabinets summing exactly to n mm; choice[n] = last width.
    fewest = [0] + [math.inf] * total
    choice = [0] * (total + 1)
    for n in range(1, total + 1):
        for size in sizes:
            if size <= n and fewest[n - size] + 1 < fewest[n]:
                fewest[n] = fewest[n - size] + 1
                choice[n] = size
    best = max(n for n in range(total + 1) if fewest[n] < math.inf)
    widths = []
    while best:
        widths.append(float(choice[best]))
        best -= choice[best]
    return sorted(widths, reverse=True)


# Per-cabinet styles in a run: a front style, a sink, a blind corner (blind
# panel on that side; the run's corner end), or a gap left for an appliance.
RUN_STYLES = FRONTS + ("sink", "blind_left", "blind_right", "gap")
GAP = "gap"  # an empty space in a run: a range, fridge or dishwasher


def styled(cabinet, style):
    """The run template cabinet changed for one entry's style (None: unchanged)."""
    if style is None:
        return cabinet
    if style not in RUN_STYLES:
        raise ValueError(f"unknown style '{style}'; use one of {', '.join(RUN_STYLES)}")
    if style in FRONTS:
        return replace(cabinet, fronts=style)
    if style == "sink":
        if cabinet.kind != "base":
            raise ValueError("sink cabinets go in base runs only")
        return replace(cabinet, kind="sink", fronts="false_front_over_doors", shelves=0)
    blind = DEFAULTS["corner"]["blind_width"]
    return replace(cabinet, fronts="doors", blind_width=blind, blind_side=style[len("blind_") :])


def format_entries(widths, styles=()):
    """Inverse of parse_entries: ((600, 800), ("drawers",)) -> '600 drawers, 800'."""
    styles = list(styles) + [None] * (len(widths) - len(styles))
    return ", ".join(f"{w:g} {s}" if s else f"{w:g}" for w, s in zip(widths, styles))


def parse_entries(text, allow_styles=True):
    """'1000 blind_left, 600 drawers, 600' -> ((1000.0, 600.0, 600.0),
    ('blind_left', 'drawers', None)). Raises ValueError with a usage hint."""
    widths, styles = [], []
    for entry in text.replace(";", ",").split(","):
        words = entry.split()
        if not words:
            continue
        try:
            width = float(words[0])
        except ValueError:
            raise ValueError(f"'{entry.strip()}': start each entry with a width in mm")
        if width <= 0:
            raise ValueError(f"'{entry.strip()}': widths must be positive")
        if len(words) > 2 or (len(words) == 2 and not allow_styles):
            hint = "e.g. 600 drawers" if allow_styles else "numbers only"
            raise ValueError(f"'{entry.strip()}': one width per entry ({hint})")
        style = words[1] if len(words) == 2 else None
        if style is not None and style not in RUN_STYLES:
            raise ValueError(f"unknown style '{style}'; use one of {', '.join(RUN_STYLES)}")
        widths.append(width)
        styles.append(style)
    while styles and styles[-1] is None:
        styles.pop()
    return tuple(widths), tuple(styles)


@dataclass
class Run:
    """Cabinets side by side along a wall, fillers making up the rest."""

    cabinet: Cabinet  # template; its width is replaced per cabinet
    length: float = 2400.0
    widths: tuple = ()  # empty: chosen by fill_widths()
    standard: tuple = STANDARD_WIDTHS
    filler_side: str = "both"
    styles: tuple = ()  # per entry of widths, None = template; needs explicit widths

    def layout(self):
        """(cabinet widths, left filler, right filler)."""
        if not 0 < self.length <= 100_000:
            raise ValueError("length must be between 0 and 100 m")
        if self.filler_side not in FILLER_SIDES:
            raise ValueError(f"filler side must be one of {', '.join(FILLER_SIDES)}")
        if len(self.styles) > len(self.widths):
            raise ValueError("styles need a width for every cabinet")
        widths = list(self.widths) or fill_widths(self.length, self.standard)
        if not widths:
            raise ValueError("wall too short for the smallest standard width")
        filler = self.length - sum(widths)
        if filler < 0:
            raise ValueError("cabinet widths exceed the run length")
        left = {"both": filler / 2, "left": filler, "right": 0.0}[self.filler_side]
        # A blind corner cabinet sits in the corner: no filler on its side.
        styles = list(self.styles) + [None] * (len(widths) - len(self.styles))
        corner_left = styles[0] == "blind_left"
        corner_right = styles[-1] == "blind_right"
        if corner_left and corner_right and filler >= 1.0:
            raise ValueError("with blind corners at both ends the widths must fill the length")
        if corner_left:
            left = 0.0
        elif corner_right:
            left = filler
        return widths, left, filler - left

    def parts(self):
        return self.joined(None).boxes

    def joined(self, items):
        """Joinery.Result of every cabinet (each joined on its own, then moved
        into place) and the fillers. items None: no joinery."""
        widths, left, right = self.layout()
        c = self.cabinet
        styles = list(self.styles) + [None] * (len(widths) - len(self.styles))
        result = Joinery.Result([])
        out = result.boxes
        x = left
        for width, style in zip(widths, styles):
            if style == GAP:
                x += width
                continue
            cabinet = styled(replace(c, width=width), style)
            part = cabinet.joined(items) if items is not None else Joinery.Result(cabinet.parts())
            base = len(out)
            out += [p.moved(x) for p in part.boxes]
            result.pockets += [(base + i, p.moved(x)) for i, p in part.pockets]
            result.operations += [(base + i, text) for i, text in part.operations]
            for key, count in part.fasteners.items():
                result.fasteners[key] = result.fasteners.get(key, 0) + count
            x += width
        # Fillers in the plane of the fronts, between the end cabinets and the walls.
        size_z = c.carcass_height()
        for fx, fw in ((0.0, left), (x, right)):
            if fw >= 1.0:
                out.append(
                    Part(
                        "Filler",
                        "filler",
                        (fw, c.thickness, size_z),
                        (fx, -c.thickness, c.plinth_height),
                        "z",
                    )
                )
        return result

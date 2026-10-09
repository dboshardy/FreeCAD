<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Tutorial 2: Framing

You will place single boards, frame a wall with a door and a window, frame a
floor and a gable roof, sheathe them, and get a lumber buying plan.

Framing follows conventional platform-framing practice. It is a planning aid:
read the [safety notes](README.md#safety) before building.

## 1. Single boards: Member

A member is a length of lumber between two points.

- With nothing selected, **Member** makes a free 2400 mm stud; edit **Start**
  and **End**.
- Select straight edges, or a whole sketch, and **Member** makes one member per
  straight line. Each stays linked to its line: edit the sketch and the lumber
  follows. Arcs and curves are skipped.

Pick the size in **Material** (e.g. `lumber.us.2x4`, `lumber.metric.45x95`).
Lumber is modelled at its real dressed size: a 2x4 is 38.1 × 88.9 mm
(1-1/2 × 3-1/2 in).

How the board is turned:

| Member runs | Its depth (wide face) | Use |
|---|---|---|
| Horizontal | Vertical (on edge) | Joists, rafters, headers |
| Vertical | Along Y | Studs in a wall running along X |
| Horizontal, **Roll** = 90° | Horizontal (flat) | Plates |

```pycon
>>> import Member
>>> length, x, y, z = Member.frame((0, 0, 0), (3000, 0, 0))
>>> length, y
(3000.0, (0.0, 0.0, 1.0))
>>> length, x, y, z = Member.frame((0, 0, 0), (3000, 0, 0), roll=90)
>>> [round(v, 6) + 0.0 for v in x]
[0.0, 0.0, 1.0]
```

The first board stands on edge (its depth `y` points up); rolled 90° it lies
flat (its thickness `x` points up).

## 2. A wall with a door and a window

1. Click **Wall Framing**. A 3600 mm wall appears along X, 2440 mm high.
2. Set **Length** to `4800`.
3. Set **Openings** to
   `door 900x2100 @ 700, window 1200x1000 @ 2600 sill 900`.
   Each entry is `kind width x height @ left edge`, rough opening sizes in mm;
   windows add `sill` (rough opening bottom above the bottom of the wall).

You get, from conventional practice:

- a bottom plate, cut out at the door, and two top plates (**TopPlates**);
- studs every **StudSpacing** (600 mm here; 406.4 mm is 16 in) measured from
  the wall start, plus one at each end;
- at each opening: king and jack studs on both sides, a header of two plies
  on edge (as many as fit the wall thickness, **HeaderMaterial**), cripples on
  the stud layout above the header, and for windows a sill with cripples below.

```pycon
>>> import Framing
>>> wall = Framing.Wall(
...     length=4800,
...     openings=Framing.parse_openings(
...         "door 900x2100 @ 700, window 1200x1000 @ 2600 sill 900"),
... )
>>> from collections import Counter
>>> sorted(Counter(p.name for p in wall.pieces()).items())
[('Bottom plate', 2), ('Cripple', 5), ('Header', 4), ('Jack stud', 4), ('King stud', 4), ('Sill', 1), ('Stud', 5), ('Top plate', 2)]
```

Corners: where another wall butts against this one, set **CornerStart** or
**CornerEnd** to that wall's depth (e.g. `95`). A corner stud is added just
past it, so the inside corner has backing for the interior lining.

Long walls: a plate longer than the longest stock length of the stud lumber is
spliced over a stud centre, and the two top plates' joints are kept at least a
stud bay apart.

```pycon
>>> long_wall = Framing.Wall(length=12000, max_piece=4800)
>>> [round(p.length()) for p in long_wall.pieces() if p.name == "Bottom plate"]
[4800, 4800, 2400]
```

Openings that do not fit (too close to an end or to each other, a header that
runs into the top plates, a sill below the bottom plate) are refused with a
message.

## 3. A floor

Click **Floor Framing**: rim joists along X (**Length**), joists along Y
(**Width**) every **JoistSpacing**. Rims longer than stock are spliced over a
joist.

```pycon
>>> floor = Framing.Floor(length=3600, width=3000, spacing=400)
>>> sorted(Counter(p.name for p in floor.pieces()).items())
[('Joist', 10), ('Rim joist', 2)]
```

## 4. A gable roof

Click **Gable Roof**. Its origin sits on the top of the wall plates; the ridge
runs along X.

| Property | Meaning |
|---|---|
| **Span** | Outer face to outer face of the walls the rafters bear on |
| **Pitch** | Slope in degrees: 26.57 is 6 in 12, 18.43 is 4 in 12 |
| **Overhang** | Eave overhang, horizontal from the wall face |
| **Seat** | Birdsmouth seat width: the top plate width |
| **CeilingJoists** | Ceiling joists as rafter ties (on by default) |

Rafters get a plumb cut at the ridge and the tail and a birdsmouth over the
wall. The ridge board's top is flush with the rafter tops. Ceiling joists sit on
the plates beside each rafter, with their outer ends cut to the roof slope.
With **GableStuds** on, the gable triangles over the end walls get studs on the
rafter layout, standing on the end walls' top plates, their tops cut to the
roof and stopped under the ridge board; the end ceiling joists move inside the
end walls to clear them.

Keep **CeilingJoists** on unless an engineer has designed a structural ridge
beam: a ridge board does not hold the rafters up by itself, and without ties
the rafters push the walls apart. **Check** warns when they are off.

```pycon
>>> roof = Framing.GableRoof(length=3600, span=3000, pitch=26.565, overhang=300)
>>> round(roof.heel()), round(roof.plumb_depth())
(47, 162)
>>> sorted(Counter(b.name for b in roof.boards()).items())
[('Ceiling joist', 7), ('Gable stud', 8), ('Rafter', 14)]
>>> rafter = next(b for b in roof.boards() if b.name == "Rafter")
>>> round(rafter.cut_length())
2060
```

The heel (the vertical cut of the birdsmouth) is 47 mm on a 162 mm plumb
depth; each rafter needs a board of at least 2060 mm.

## 5. Sheathing

Select a wall, floor or roof framing object and click **Sheathing**:

- floors: sheets with the long side across the joists, seams staggered;
- walls: sheets upright on the outer face, openings cut out;
- roofs: both slopes, long side across the rafters, and the gable ends (cut
  to the gable outline) when the roof has gable studs.

Seams are staggered only where a row needs more than one sheet. Sheathing
follows its framing when you move it. Pick the sheet in **Material**.

```pycon
>>> import Sheathing
>>> panels = Sheathing.cover((3600, 3000), (2440, 1220))
>>> [(u, v, du, dv) for u, v, du, dv in panels]
[(0.0, 0, 2440.0, 1220), (2440.0, 0, 1160.0, 1220), (0.0, 1220, 1220.0, 1220), (1220.0, 1220, 2380.0, 1220), (0.0, 2440, 2440.0, 560), (2440.0, 2440, 1160.0, 560)]
```

## 6. The lumber buying plan

**Cut List** includes every member and framing object. For lumber it writes:

- in **CutList**, how many boards of each stock length to buy per size;
- in **LumberPlan**, each board's stock length, the cuts to take from it, and
  the offcut.

Cuts allow one blade width (kerf) between pieces; a piece that uses a whole
stock length (a precut stud) needs no cut:

```pycon
>>> import CutList
>>> boards = CutList.plan_lengths([("Stud", 2305)] * 3 + [("Plate", 1200)] * 2,
...                               [2400, 3000, 3600])
>>> [(b.stock, [name for name, _ in b.cuts], round(b.offcut(), 1)) for b in boards]
[(3600, ['Stud', 'Plate'], 88.6), (3600, ['Stud', 'Plate'], 88.6), (2400, ['Stud'], 91.8)]
```

## From the Python console

```py
import ConstructionObjects
wall = ConstructionObjects.make_wall_frame()
wall.Length = 4800
wall.Openings = "door 900x2100 @ 700, window 1200x1000 @ 2600 sill 900"
roof = ConstructionObjects.make_gable_roof()
ConstructionObjects.make_sheathing(wall)
App.ActiveDocument.recompute()
ConstructionObjects.write_cut_list(App.ActiveDocument)
```

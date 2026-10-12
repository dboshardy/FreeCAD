<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Tutorial 1: Cabinets

You will build a small kitchen: a base cabinet with a drawer, a run of base
cabinets with a sink and a blind corner, and wall cabinets above, then get
everything needed to buy and cut it.

All cabinets are frameless (32 mm system) with butt-jointed carcasses and
full-overlay fronts.

## 1. A base cabinet

1. Click **Base Cabinet**. A 600 mm wide cabinet appears: sides, bottom, two top
   stretchers, back, plinth (kick board and rear rail), one shelf and a door.
2. In the Property view set **Width** to `800`. It now gets two doors: one
   door up to 600 mm wide, two above that (set **Doors** to force a count).
3. Set **Fronts** to `drawer_over_doors`. A 150 mm drawer (**DrawerFrontHeight**)
   appears above the doors, with a drawer box behind it.

Front styles:

| Fronts | Result |
|---|---|
| `doors` | Doors over the whole face; **Shelves** behind them |
| `drawers` | A drawer bank of **Drawers** equal fronts (shelves are left out) |
| `drawer_over_doors` | One drawer of **DrawerFrontHeight**, doors below |
| `false_front_over_doors` | A fixed front without a drawer box (sinks), doors below |

**DoorStyle** `shaker` makes each door a frame of stiles and rails
(**FrameWidth** wide, doweled) around a thin panel of the **BackMaterial**,
housed 10 mm into grooves; the hinges go on the stile at the side. Drawer
fronts stay slabs.

Drawer boxes are sized from the slide clearances: **SlideClearance** per side
(take it from your slide maker's data), **DrawerHeightClearance** and
**DrawerRearClearance**. Box depth is rounded down to the 50 mm steps slides are
sold in.

The same cabinet, computed by the standalone module (handy for checking sizes):

```pycon
>>> import Cabinet
>>> cabinet = Cabinet.Cabinet(width=800, fronts="drawer_over_doors", shelves=1)
>>> sorted({p.name for p in cabinet.parts() if p.role in ("door", "drawer_front")})
['Door 1', 'Door 2', 'Drawer front']
>>> role, low, high = cabinet.slots()[-1]  # the drawer's band of the cabinet face
>>> x, z, box_width, box_height, slide = cabinet.drawer_box(low, high)
>>> box_width, slide
(738.0, 550.0)
```

The box is the interior width, 800 − 2 × 18 = 764 mm, less 13 mm slide
clearance per side: 738 mm. The carcass is 580 − 6 = 574 mm deep inside; less
10 mm rear clearance that leaves 564 mm, so it takes 550 mm slides.

## 2. Other cabinet types

| Command | What you get |
|---|---|
| **Wall Cabinet** | 720 mm high, 320 mm deep, full top, no plinth, two shelves; created with its bottom 1400 mm above the floor (move it with **Placement**) |
| **Tall Cabinet** | 2100 mm high, four shelves, full top |
| **Sink Cabinet** | 800 mm wide, no back (open for plumbing), front stretcher only, false front over two doors |
| **Blind Corner Cabinet** | 1000 mm wide; a 600 mm fixed **blind panel** covers the part hidden by the run that meets it, a door covers the rest |

For a blind corner, set **BlindWidth** to the depth of the meeting run plus room
for its door handles, and **BlindSide** to the side that goes into the corner.
Blind corners take doors only: a drawer cannot open behind the blind panel.

Wall and tall cabinets must be fixed to the wall framing: wall cabinets hang
from it and tall cabinets can tip over. The cut list adds two wall anchors for
each, and **Check** lists them as required.

## 3. Fill a wall with a cabinet run

1. Click **Base Cabinet Run**.
2. Set **Length** to the wall length, e.g. `2475`.
3. Leave **Widths** empty: the run picks cabinet widths from **StandardWidths**
   (300 to 900 mm) that leave the least filler, then uses the fewest cabinets.
   **Layout** shows the result; fillers go at both ends (**FillerSide**).

```pycon
>>> run = Cabinet.Run(Cabinet.Cabinet(), length=2475)
>>> run.layout()
([900.0, 800.0, 450.0, 300.0], 12.5, 12.5)
```

All standard widths are multiples of 50 mm, so 25 mm is left as two 12.5 mm
fillers.

### Choose each cabinet yourself

Double-click the run (or click **Edit**) and list the cabinets left to
right, each with a width and a style from the dropdown. The panel writes the
**Widths** property, which you can also type, each width optionally followed
by a style:

```
1000 blind_left, 600 drawers, 800 sink, 600
```

Styles: `doors`, `drawers`, `drawer_over_doors`, `false_front_over_doors`,
`sink`, `blind_left`, `blind_right`, and `gap`: an empty space for a range,
fridge or dishwasher (`600 gap`). A blind corner cabinet at an end stays in
the corner, so the leftover length goes to the other end:

```pycon
>>> run = Cabinet.Run(Cabinet.Cabinet(), length=3100,
...                   widths=(1000, 600, 800, 600),
...                   styles=("blind_left", "drawers", "sink"))
>>> run.layout()
([1000, 600, 800, 600], 0.0, 100.0)
```

For an L-shaped kitchen, make two runs and put the blind corner at the end of
one where the other meets it. Do the same along the upper wall with **Wall
Cabinet Run** (wall runs cannot take `sink`).

## 3b. From a measured room

For a whole kitchen, start from the room instead of single runs. Click
**Room**; its panel has four lists:

1. **Walls**, measured along the inside faces, in order: the length and which
   way the next wall turns. An L kitchen: `3600, left` then `2400, left`.
   (Or draw the walls as a sketch with square corners and set the room's
   **Base** to it.)
2. **Doors and windows**: the wall number, kind, size, position from the
   wall's start, and a window's sill height.
3. **Appliance gaps**: the wall, the appliance (range, dishwasher, fridge,
   other), its position and width. A fridge also keeps the wall cabinets
   away.
4. **Cabinets on each wall**: base and/or wall cabinets.

Click **OK** and the room makes a base cabinet run (and wall cabinet run) for
each chosen wall, backed onto the wall: where two runs meet at a corner, the
first ends in a blind corner cabinet and the second starts past it; runs stop
at doors and appliance gaps, wall cabinets also at windows; leftover space
becomes fillers. Set **FrameWalls** to also get wall framing with the doors
and windows. The runs are ordinary cabinet runs: double-click one to change a
cabinet's width or style. Double-click the room to change the measurements and
everything is laid out again.

## 4. Cut list, sheet layout and hardware

Click **Cut List**. It collects every construction object in the document and
writes:

| Output | Contents |
|---|---|
| Spreadsheet **CutList** | Every part grouped by size: material, length (along the grain), width, thickness, grain, quantity. Below: sheets per material, lumber boards, hardware |
| Spreadsheet **SheetLayout** | Each part's sheet number and position for the panel saw |
| **SheetLayoutView** | A flat drawing of the sheets with the parts on them |

Parts with visible grain keep it along the sheet length; hidden parts (top
stretchers, plinth rail) may be turned to save material. The layout respects
the saw blade width and edge trim (see tutorial 4).

Parts are grouped when their sizes match:

```pycon
>>> import CutList
>>> rows = CutList.rows(("ply", p) for p in cabinet.parts() if p.role == "carcass")
>>> [(name, length, width, qty) for _, name, length, width, _, _, qty in rows]
[('Left side', 770.0, 574.0, 2), ('Bottom', 764.0, 574.0, 1), ('Front stretcher', 764.0, 100.0, 2)]
```

Hardware comes from the cabinet's joints, the same joints from the library
that you use in a build (tutorial 5): the carcass joint (**CarcassJoint**,
confirmat screws unless you pick another, such as dowels or a dado), the
back nailed on at most 150 mm apart, hinges
on the side each door hangs from (door height decides the count), a slide
pair per drawer and two pins at each end of a shelf. For the 800 mm cabinet:

```pycon
>>> import Library
>>> items = Library.load()
>>> joined = cabinet.joined(items)
>>> for name, qty in CutList.hardware(items, fasteners=joined.fasteners):
...     print(qty, name)
24 Brad nail, 1.2 x 25 mm
4 Concealed hinge, 35 mm cup, full overlay
12 Confirmat screw, 7 x 50 mm
1 Drawer slide pair, side mount, full extension, 550 mm
9.9 Edge banding, metres
4 Shelf pin, 5 mm
```

The joints also add shop work to the cut list's **Operations** column, such
as the hinge cups in each door:

```pycon
>>> sorted({text for _, text in joined.operations if not text.startswith("edge band")})
['1 confirmat hole', '2 hinge cups, 35 mm', '2 shelf pin holes, 5 mm', '4 confirmat holes']
>>> [p.operations for p in joined.boxes if p.name == "Door 1"]
[('2 hinge cups, 35 mm', 'edge band 397', 'edge band 397', 'edge band 614', 'edge band 614')]
```

**EdgeBanding** (on by default) bands the edges that show: the fronts all
round and the front edges of the sides, bottom, top and shelves. Each banded
edge is an operation in the cut list, and the hardware list gets the banding
in metres: 9.0 m of edges plus 50 mm per edge to trim flush. Parts are cut to
their finished size; with thick banding, take its thickness off the panel.

## 5. Materials

Each cabinet has **CarcassMaterial** (sides, bottom, top, shelves, fronts,
plinth, fillers), **BackMaterial** (back and drawer bottoms) and
**DrawerMaterial** (drawer box sides, fronts, backs). Panel thicknesses come
from the chosen material, so picking `sheet.us.plywood.3-4` gives 18.26 mm
(23/32 in, what "3/4 in" plywood actually measures). Add your own sheets in
[tutorial 4](04-libraries-and-checks.md).

## From the Python console

```py
import ConstructionObjects
cab = ConstructionObjects.make_cabinet("base")      # or "wall", "tall", "sink", "corner"
cab.Width = 800
cab.Fronts = "drawer_over_doors"
run = ConstructionObjects.make_cabinet_run("base")
run.Length = 3100
run.Widths = "1000 blind_left, 600 drawers, 800 sink, 600"
App.ActiveDocument.recompute()
ConstructionObjects.write_cut_list(App.ActiveDocument)
```

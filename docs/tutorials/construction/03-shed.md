<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Tutorial 3: Build a Shed

You will create a 3.6 × 3.0 m gable shed from the template, change it, check
it, and produce the buying and cutting lists. This is the Construction
workbench's end-to-end example.

## 1. Create it

Click **Gable Shed**. One object appears with:

- a floor platform (joists at 400 mm) with sheathing;
- four stud walls: front and back run the full length, the sides fit between
  them, and a corner stud at each end of the front and back walls backs the
  inside corners; a door centred in the front wall;
- a gable roof with the ridge along the front, ceiling joists as rafter ties,
  and studs in the gable triangles over the side walls;
- sheathing on the walls (the side walls' sheathing wraps the corners), the
  gable ends and both roof slopes.

What it contains, counted:

```pycon
>>> import Shed
>>> from collections import Counter
>>> shed = Shed.Shed()  # the template's defaults
>>> for c in shed.components():
...     names = [p.name for p in c.model.pieces()]
...     names += [b.name for b in getattr(c.model, "boards", list)()]
...     print(c.name, sorted(Counter(names).items()))
Floor [('Joist', 10), ('Rim joist', 2)]
Front wall [('Bottom plate', 2), ('Corner stud', 2), ('Cripple', 1), ('Header', 2), ('Jack stud', 2), ('King stud', 2), ('Stud', 6), ('Top plate', 2)]
Back wall [('Bottom plate', 1), ('Corner stud', 2), ('Stud', 7), ('Top plate', 2)]
Left wall [('Bottom plate', 1), ('Stud', 6), ('Top plate', 2)]
Right wall [('Bottom plate', 1), ('Stud', 6), ('Top plate', 2)]
Roof [('Ceiling joist', 7), ('Gable stud', 8), ('Rafter', 14), ('Ridge board', 1)]
```

Check against a hand count: the front wall is 3600 mm with studs at 600 mm;
the door (900 mm, from 1350 to 2250) takes the 1800 mm stud's place, so 6 studs
remain (both ends, 600, 1200, 2400, 3000), with king and jack studs each side
and one cripple above the header at 1800. The side walls are
3000 − 2 × 95 = 2810 mm long: ends plus 600, 1200, 1800, 2400.

## 2. Change it

Everything is driven by the shed's properties. Try:

| Change | Property | What regenerates |
|---|---|---|
| Taller walls | **WallHeight** `2700` | Studs, king/jack studs, sheathing; the roof moves up |
| Wider door | **DoorWidth** `1200` | Header, jacks, cripples, bottom plate cut, sheathing cut-out |
| Steeper roof | **Pitch** `33.69` (8 in 12) | Rafters, ridge height, ties, roof sheathing |
| Bigger shed | **Length**, **Width** | Everything |
| US lumber | **StudMaterial** `lumber.us.2x4`, **JoistMaterial** `lumber.us.2x8`, ... | Sizes and the buying plan |

```pycon
>>> taller = {c.name: c for c in Shed.Shed(wall_height=2700, door_width=1200).components()}
>>> round(taller["Roof"].origin[2])  # roof bears on the top plates: joists + floor sheet + walls
2913
>>> header = next(p for p in taller["Front wall"].model.pieces() if p.name == "Header")
>>> round(header.length())  # door width plus a jack stud each side
1290
```

A door wider than the front wall, or a header that runs into the top plates,
is refused with a message.

## 3. What to buy and cut

Click **Cut List**:

- **CutList**: every part by size; sheets per material (shop parts and
  sheathing listed separately); lumber boards per stock length; hardware.
- **SheetLayout** and **SheetLayoutView**: where each sheathing panel comes
  from. Sheathing is cut against the factory edges, so no edge trim is taken.
- **LumberPlan**: board by board, which pieces to cut.

The sheathing, by hand: the floor (3600 × 3000) needs 4 sheets of
1220 × 2440 mm; each wall needs 3 (two whole sheets and one cut); the two roof
slopes need 6 and the two gable ends 2 more.

```pycon
>>> import CutList, Sheathing
>>> floor = {c.name: c for c in shed.components()}["Floor"]
>>> surface = Shed.sheathing_surfaces(floor)[0]
>>> pieces = [("Subfloor", du, dv, True)
...           for _, _, du, dv in Sheathing.cover(surface.size, (2440, 1220))]
>>> len(CutList.layout_sheets(pieces, 1220, 2440, kerf=3.2, trim=0))
4
```

## 4. Check it

Click **Check**. The **Checks** spreadsheet starts with this note, which applies
to everything in it:

> Advisory only. Not a building code compliance check. Verify against the code
> adopted where you build and have the design reviewed by your building official
> or a qualified professional.

With the defaults you will see stud spacing and slenderness, birdsmouth depth,
ridge board depth and rafter ties as `ok`, and the header, floor joists and
rafters as `not checked`: those need the loads for your site and the design
values of your lumber grade. Tutorial 4 shows how to enter them.

## 5. Drawing

For a framing drawing, first turn the shed's **ShowSheathing** off: the
sheathing would hide the framing (the cut list still counts it). Then select the
shed and click **Drawing**. You get two A3 pages (TechDraw):

- **FramingDrawing**: front, top and right views, scaled to fit, with a
  numbered tag on each kind of framing member in the front view. The numbers
  match the **Tag** column of the cut list.
- **FramingCutList**: the cut list as a table.

Print them, or switch to the TechDraw workbench and use **Export Page as PDF**.
With nothing selected, the drawing shows every construction object in the
document.

## Not in the template yet

- Foundation (skids, piers), roofing, trim, windows.

Add those yourself with **Member** and **Sheathing**, or as ordinary FreeCAD
parts.

## From the Python console

```py
import ConstructionObjects
shed = ConstructionObjects.make_shed()
shed.WallHeight = 2700
shed.DoorWidth = 1200
App.ActiveDocument.recompute()
ConstructionObjects.write_cut_list(App.ActiveDocument)
ConstructionObjects.write_checks(App.ActiveDocument)
```

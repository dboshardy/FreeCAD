<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork (design doc Phase 5.1).
-->

# Tutorial 5: Build an End Table

You will build a 500 × 500 × 600 mm end table twice: by hand, part by part and
joint by joint, and then from the template. Both give the same parts, cut list
and hardware. The same steps work for any furniture or joinery: a bookcase, a
workbench, a frame.

## How a build works

A **Build** is one object in the document holding two tables (spreadsheets,
shown under it in the Tree view):

- **Parts table**: one row per board or panel: name, stock (from the
  library), length, width, thickness, position (X, Y, Z of its lowest corner),
  the axis its length runs along (**Along**) and the axis of its thickness
  (**Thick**). Leave width and thickness empty to use the stock's size.
- **Joints table**: one row per joint: receiving part, inserted part, joint
  (from the library) and options such as `depth=30`. Names may use `*`:
  `Leg*` means every part whose name starts with "Leg".

Every part is a solid of the build. Click a part's face in the 3D view to
select that part. To change a part, edit its row; the build regenerates.

## 1. Legs, by hand

Click **Build**. Set its **BoardStock** to *Hardwood leg blank 45x45*, then
click **Board** four times and fill in the rows:

| Name | Stock | Length | X | Y | Z | Along | Thick |
|---|---|---|---|---|---|---|---|
| Leg 1 | lumber.metric.hw.45x45 | 582 | 25 | 25 | 0 | z | x |
| Leg 2 | lumber.metric.hw.45x45 | 582 | 430 | 25 | 0 | z | x |
| Leg 3 | lumber.metric.hw.45x45 | 582 | 430 | 430 | 0 | z | x |
| Leg 4 | lumber.metric.hw.45x45 | 582 | 25 | 430 | 0 | z | x |

582 is the table height less the 18 mm top. The legs stand 25 mm in from the
edges of the top (the overhang).

## 2. Aprons between the legs

Set **BoardStock** to *Hardwood PAR 20x95*. Select a face of Leg 1 and a
face of Leg 2 (Ctrl+click) and click **Board Between**: a board fills the
gap, 430 − 70 = 360 mm long, flush with the tops of the legs. Rename it
"Apron 1" and set its Y to 30, so its face sits 5 mm back from the legs'
outer faces. (To line a part up with another, select the face to line up
with, then the part's face, and click **Align**.) Do the same for the other
three sides ("Apron 2" to "Apron 4").

Add the top with **Panel**: stock *Edge-glued hardwood panel 18 mm*, 500 ×
500, at Z 582. (With a face selected, **Board** lays a board along it and
**Panel** covers it: select the top of a leg and click **Panel** to start a
panel there, then set its size and position in the table.)

## 3. Joints

Select a face of Leg 1 and a face of Apron 1 and press **J** (or click
**Joint**). The list shows only joints that fit an end meeting a face:
mortise and tenon, dowels, pocket screws, screws, confirmat, biscuits,
housing. Pick **Mortise and tenon**. Next you can change its sizes (the
preset's are filled in, e.g. `depth=25, thickness=0, shoulder=10`; thickness
0 means a third of the apron). The joint is then added and shown in the
model, and you choose: **Keep for this pair**, **Apply to every similar
pair** or **Undo**. Pick **Apply to every similar pair**: the row reads
`Leg*`, `Apron*` and all eight apron ends get tenons.

Then select an apron and the top, press **J** and pick **Tabletop fasteners,
figure-8**, again for every apron. Figure-8 fasteners let a solid top move
with the seasons; screwing or gluing it to the aprons can split it.

The joints change the parts. Each apron grows by a 25 mm tenon at each end,
and each leg gets two mortises. The same build, in the standalone modules:

```pycon
>>> import Build, CutList, Library
>>> items = Library.load()
>>> legs = [(f"Leg {n}", "lumber.metric.hw.45x45", 582, "", "", x, y, 0, "z", "x")
...         for n, (x, y) in enumerate([(25, 25), (430, 25), (430, 430), (25, 430)], 1)]
>>> aprons = [
...     ("Apron 1", "lumber.metric.hw.20x95", 360, "", "", 70, 30, 487, "x", "y"),
...     ("Apron 2", "lumber.metric.hw.20x95", 360, "", "", 450, 70, 487, "y", "x"),
...     ("Apron 3", "lumber.metric.hw.20x95", 360, "", "", 70, 450, 487, "x", "y"),
...     ("Apron 4", "lumber.metric.hw.20x95", 360, "", "", 30, 70, 487, "y", "x")]
>>> top = [("Top", "sheet.metric.edge_glued.18", 500, 500, "", 0, 0, 582, "x", "z")]
>>> joints = [("Leg*", "Apron*", "joint.mortise_tenon", ""),
...           ("Apron*", "Top", "joint.figure8", "")]
>>> parts, result = Build.build(legs + aprons + top, joints, items)
>>> for row, ops in zip(CutList.rows(parts), CutList.operations(parts)):
...     print(row[1], row[2:5], "qty", row[6], "|", ops)
Apron 1 (410.0, 95.0, 20.0) qty 4 | 2 figure-8 recesses; 2 x tenon 75 x 6.7 x 25 long
Leg 1 (582.0, 45.0, 45.0) qty 4 | 2 x mortise 75 x 6.7 x 25 deep
Top (500.0, 500.0, 18.0) qty 1 |
>>> result.fasteners
{'hardware.figure8': 8}

```

Check by hand: the tenon is a third of the apron's 20 mm (6.7 mm) and 95 −
2 × 10 mm shoulders = 75 mm wide. Each apron is 360 mm between the legs,
leaving 360 − 2 × 75 = 210 mm between the end fasteners; at up to 400 mm
apart that is 2 per apron, 8 in all.

To change a joint, edit its row: `depth=20` in **Options** makes 20 mm
tenons; `shoulder=5` leaves 5 mm shoulders.

## 4. The same table from the template

Click **End Table**. You get a build with the same tables filled in:

```pycon
>>> rows, joint_rows = Build.end_table(width=500, depth=500, height=600)
>>> Build.build(rows, joint_rows, items)[0] == parts
True

```

The template's sizes are its arguments: `width`, `depth`, `height`,
`overhang`, `setback`, the leg, apron and top stock, `joint` and
`top_joint`. After creating it, edit it like any build.

## 5. Check it

Click **Check**. For a build the **Checks** sheet lists the wall left around
each mortise (the thinnest is the 10 mm above it, kept by the tenon's top
shoulder), cuts that meet inside a part (two tenons that run into each other
in a leg), and solid wood wider than the rule set's limit that is fixed
rigidly, and holes that leave too thin a wall or break through. Change the
top's joint to **Screws through the face** and the top is flagged twice: a
500 mm solid top moves with the seasons, and the preset's 30 mm screw holes
are deeper than the 18 mm top.

```pycon
>>> import Checks
>>> rules = items["rules.generic-example"]
>>> screwed = Build.end_table(top_joint="joint.screw")
>>> built, result = Build.build(*screwed, items)
>>> [c for c, status, _ in Checks.build(built, result, rules, items) if status == Checks.WARNING]
['Hole wall, Top', 'Wood movement, Top']

```

Like every check in the workbench, these are advisory, from the example rule
set; see [tutorial 4](04-libraries-and-checks.md).

## 6. Cut list and drawing

Click **Cut List**. The **Operations** column lists the mortises, tenons and
fastener recesses for each row; the hardware list counts the figure-8
fasteners; the boards are planned from stock lengths and the top from a
panel. Click **Drawing** for front, top and right views tagged with the cut
list's row numbers.

## Other templates

The end table is one case of a general table template (`Build.table`):
**Dining Table** is 1600 × 900 × 750 mm with its top glued up from boards
(all ripped to the same width, glued edge to edge), and **Workbench** adds
stretchers and a plywood shelf low down. Any of them takes the same
arguments, so an end table with a shelf is
`Build.end_table(shelf=("sheet.metric.plywood.18", 18))`.

A glued-up top moves as one board: the checks measure the whole glue-up, so
screwing a 900 mm dining table top down rigidly is flagged once for the
glue-up, not passed because each board is narrow.

**Bookcase** makes a build the same way: two sides, a top, a bottom on a
kick board and fixed shelves, all in dados, with a back nailed on. Anything
taller than the rule set's `anchor_furniture_height_mm` (700 mm in the
example) and slender (height over 1.5 × its narrower footprint side,
`anchor_furniture_slenderness`) must be fixed to the wall against tipping: the checks say so and
the hardware list gets the anchors.

```pycon
>>> parts, result = Build.build(*Build.bookcase(height=1800, shelves=4), items)
>>> [(c, status) for c, status, _ in Checks.build(parts, result, rules, items)]
[('Wall anchoring', 'required')]

```

## From the Python console

```py
import ConstructionObjects as CO
table = CO.make_end_table(height=650, overhang=30)
CO.write_cut_list(App.ActiveDocument)
```

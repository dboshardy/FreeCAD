<!--
SPDX-License-Identifier: LGPL-2.1-or-later
-->

# Tutorial 6: Construction Objects Are FreeCAD Objects

Members, stairs, slabs, deck guards and sheet layouts are made from FreeCAD's own
BIM objects. The Construction workbench adds the lumber sizes, rules, checks and
quantities on top. This tutorial shows what that gives you: you can use the BIM
tools on these objects, export them as IFC, and read their density from the
Material workbench.

It assumes tutorials 2 and 3. All sizes are in millimetres.

## 1. A member is an Arch_Structure

Click **Member** with nothing selected. In the **Tree view** the new member has
two children:

- **profile_…**, a BIM rectangle profile. Its Width and Height are set from
  the **Lumber** choice (a 45x95 gives 45 × 95).
- a line (a Draft wire) that is the path the profile is extruded along.

Select the member. In the **Property view**:

| Property | Meaning |
|---|---|
| **Lumber** | Library size. Changing it resizes the profile |
| **StartCut**, **EndCut** | Angled end cuts, degrees from square. 45 is a miter |
| **IfcType** | `Beam`. The IFC export uses it |
| **BaseRotation** | Roll about the line, from BIM. Roll 90 lays a plate flat |
| **ToolOffsetFirst**, **ToolOffsetLast** | Set for you from the end cuts so the stock stays long enough. Do not edit them |

Because it is a BIM object, BIM tools that take structures accept it, for
example a BIM building part. Not every BIM tool has been tried on it.

Edit the line (double-click it, or change its points in the **Property
view**) and the board follows.

**Check:** set **StartCut** to 45 and look at the end of the board in the 3D
view. The end is cut at 45° across the board's depth.

## 2. Stairs: the Arch_Stairs holds the geometry

Click **Stair**. Two objects appear: **Stairs** (an `Arch_Stairs`) and **Stair**
(the lumber). Change the rise, number of steps, width, nosing and railings on
**Stairs**; the lumber is rebuilt from it. Tutorial 2, section 5 lists what
the Stair object makes.

The Stair object works on a straight flight. A landing is supported only at the
center of the flight. The **Stairs** object is hidden; the Stair object shows
a copy of its shape.

## 3. Slabs are BIM slabs

Click **Slab**, or create a shed with a slab foundation (tutorial 3). The
object has a **BimSlab** property: a BIM structure with **IfcType** `Slab`.
Its Length, Width, Height and Placement are expressions of the Slab object.

1. Select the Slab. Set **Thickness** to 150.
2. The slab shape follows. To see the link, select the BIM slab in the Tree
   view and look at its **Expressions**: `Height` is `max(Slab.Thickness; 0.001 mm)`.

The concrete volume in the cut list comes from the shape of the BIM slab plus
the thickened edge, so a changed thickness changes the quantity. **Thickness 0**
leaves only a strip footing.

## 4. Deck guards are Arch_Fences

Click **Deck**. When the deck is higher than the rule set's `guard_min_rise_mm`
(set **Guards** to `yes` to force them), the guards are four `Arch_Fence`
objects, one for each side. They are in the group **Deck guards**, with their
path, section and post helper objects hidden.

- The cut list, the hardware list and the checks use the guard parts the
  deck model produces, so the quantities are the same as before this change.
- A side without a guard has an empty fence.
- The deck's **GuardFences** property lists the fence names.

## 5. Sheet layouts are panel sheets

Click **Cut List** (tutorial 1, section 4). Besides the **SheetLayout**
spreadsheet, the group **SheetLayoutView** holds one BIM panel sheet
(`Arch_Panel_Sheet`) for each sheet of plywood or board. Each holds the parts
placed on it, tagged with the part name. Select a panel sheet and read
**FillRatio** for how full it is.

The layout itself is still the workbench's own saw-cut packer. The panel sheets
are the drawing objects for it.

## 6. Density comes from Material cards

Each library item has a `material_card`: a Material workbench card in the
library **Construction**, such as *Plywood* or *OSB*. There are 13 shipped
cards (cement board, glulam, gypsum board in two densities, HDF, hardwood
stock, I-joist, LVL, MDF, OSB, particleboard, plywood, softwood framing
lumber). In the Python console:

```py
import Library
item = Library.load()["lumber.metric.45x95"]
print(Library.density_kg_m3(item))
```

To use your own value, make a card in the **Material** workbench and put its
UUID in the `material_card` of your library item (tutorial 4). An item with no
`material_card` returns `None`.

No cut-list or check column uses the density yet; it is there for your own
scripts and for later weight reports.

## 7. IFC export

Select the objects and use **File > Export** with an `.ifc` file name. The members carry
IFC type `Beam` and the slabs `Slab`; the BIM exporter writes those types. Test that the file opens in the viewer you use: the add-on's test only
checks that the export runs.

## 8. Tutorials in the Help viewer

**Construction > Tutorials** shows these pages in FreeCAD's Help viewer if
your build has Qt WebEngine; otherwise in a plain text window.

## From the Python console

```py
import ConstructionObjects as C
member = C.make_member()
member.StartCut = 45
slab = C.make_slab()
slab.Thickness = 150
deck = C.make_deck()
deck.Height = 900
App.ActiveDocument.recompute()
print(member.IfcType, slab.BimSlab.IfcType, deck.GuardFences)
# Beam Slab ['Fence', 'Fence001', 'Fence002', 'Fence003']
```

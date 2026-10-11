<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork.
-->

# Tutorial 4: Libraries, Settings and Checks

## 1. Your own materials

Lumber sizes, sheet goods, hardware and rule sets come from JSON library files.
The shipped ones are read first, then yours, from

```
<user data folder>/Construction/libraries/<any folder name>/<any name>.json
```

(find the user data folder by typing `App.getUserAppDataDir()` in the Python
console). An item with the same `id`
as a shipped one replaces it. Restart the application after editing.

Example: the plywood your yard sells is 17.5 mm thick, and you also use
2500 × 1250 mm sheets:

```json
{
  "_comment": "My yard's sheets",
  "source": "Measured, March 2026",
  "data_license": "CC0-1.0",
  "items": [
    {"id": "sheet.metric.plywood.18", "category": "sheet_goods", "region": "metric",
     "name": "Plywood 18 mm (measured 17.5)", "material": "plywood",
     "actual": {"w": 1220, "h": 2440, "t": 17.5, "unit": "mm"}, "grain_axis": "length"},
    {"id": "sheet.mine.birch.18", "category": "sheet_goods", "region": "metric",
     "name": "Birch plywood 18 mm 2500x1250", "material": "plywood",
     "actual": {"w": 1250, "h": 2500, "t": 18, "unit": "mm"}, "grain_axis": "length"}
  ]
}
```

- `actual` is what the material measures; `unit` may be `mm` or `in`.
- `grain_axis`: `"length"` keeps grain along the sheet length in layouts;
  `null` (MDF, particleboard) lets parts turn.
- Lumber items use `"category": "dimensional_lumber"`, `actual` `w` (thickness)
  and `h` (depth), and `stock_lengths_mm`.
- A file's `"defaults"` object applies to all its items.
- A broken file is skipped with a message in the Report view; the rest of the
  library still loads.

```pycon
>>> import Library
>>> items = Library.load()
>>> Library.mm(items["lumber.us.2x4"], "h")  # 3-1/2 in
88.9
>>> items["lumber.metric.45x95"]["stock_lengths_mm"]
[2400, 2700, 3000, 3600, 4200, 4800, 5400, 6000]
```

### Prices, volumes and coverings

Give an item a `price` and the cut list fills its **Cost** column and adds a
**Total cost** line (saying how many lines have no price). `price_per` is
`each` (sheets, hardware; the default), `m`, `board_foot` or `m3` (boards).
The lumber lines also give the volume bought in m³ and board feet (board feet
from the nominal size when the item has one, as US lumber is sold).

```pycon
>>> import CutList
>>> stud = {**items["lumber.metric.45x95"], "price": 2.5, "price_per": "m"}
>>> CutList.price(stud, 4, 3000)  # four 3 m boards
30.0
>>> round(CutList.board_feet(items["lumber.us.2x4"], 8 * 304.8), 2)  # a 2x4x8
5.33
```

Area materials (`"category": "area_material"`: shingles, underlayment, house
wrap) are bought by coverage: `coverage_m2` per bundle or roll and a `waste`
allowance. Set a **Covering** on a Sheathing object, or **RoofCovering** and
**WallCovering** on a shed, and the cut list adds a **Coverings** section:

```pycon
>>> CutList.covering_units(items["area.roofing.asphalt_shingles"], 30)  # 30 m² + 15 %
12
```

The library also has engineered lumber (LVL, glulam, I-joists, listed as
lumber so you can pick them for headers, beams and joists: enter their design
values from the maker), gypsum board and cement board.

### Region

**Construction > Library Region** chooses which region's items this document
offers: `metric`, `US` or `all`. Generic items (hardware, joints, rule sets)
are always offered, and a value already chosen stays. New documents follow the
`Region` parameter below.

## 2. Saw settings

**Tools > Edit parameters**, group `BaseApp/Preferences/Mod/Construction`:

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `Kerf` | Float | 3.2 | Saw blade width in mm, between every two cuts |
| `Trim` | Float | 10 | Edge strip taken off every side of a shop sheet (not sheathing) |
| `RuleSet` | String | `rules.generic-example` | Rule set used by **Check** |
| `FasteningSchedule` | String | `fastening.generic-example` | Nails, screws and hangers counted into the cut list's Hardware |
| `Region` | String | `all` | Library region for new documents (`metric`, `US`, `all`) |

The fastening schedule is library data like the rest. Each rule names the part
that receives a fastener and the part fastened to it (patterns on part names),
then a fixed count per joint or a spacing along the joint. The shipped schedule
is an example of conventional practice; enter your own the same way as a rule
set (see `Resources/libraries/generic/fastening.json`).

## 3. Checks, rule sets and loads

**Check** compares the model with a rule set and with beam mechanics. It never
claims code compliance: building codes are copyrighted, differ by place and are
not included. The shipped rule set holds example values from conventional
practice, labelled "verify for your jurisdiction". Make your own from the values
adopted where you build:

```json
{
  "_comment": "Rules adopted for my jurisdiction (entered by me)",
  "source": "Values entered from the code adopted locally; see the code for the text",
  "data_license": "CC0-1.0",
  "items": [
    {"id": "rules.mine", "category": "rule_set", "region": "generic",
     "name": "My jurisdiction",
     "stud_spacing_max_mm": 610, "stud_slenderness_max": 50,
     "header_deflection_limit": 360, "floor_joist_deflection_limit": 360,
     "rafter_deflection_limit": 240, "birdsmouth_max_fraction": 0.333,
     "anchor_cabinet_kinds": ["wall", "tall"]}
  ]
}
```

then set `RuleSet` to `rules.mine`.

### Structural checks need your numbers

Headers, floor joists and rafters are checked as simply supported beams
(bending stress and deflection). They report `not checked` until you give:

1. **Design values** of the lumber grade you buy, added to its library item as
   `"design_values": {"Fb_MPa": ..., "E_MPa": ...}` (allowable bending stress
   and modulus of elasticity, from the grading agency's published values for
   your species and grade).
2. **Loads** for your site on the object: **HeaderLoad** (kN/m on each header),
   **FloorLoad** (kPa), **RoofLoad** (kPa on plan).

The numbers below are made up to show the calculation; they are not values for
any real lumber:

```pycon
>>> import Checks, Framing
>>> example_values = {"Fb_MPa": 10, "E_MPa": 10000}  # NOT real design values
>>> floor = Framing.Floor(width=3000, spacing=400, joist=(45, 195))
>>> rules = items["rules.generic-example"]
>>> for check, status, detail in Checks.floor(floor, rules, example_values, load_kpa=2):
...     print(check, status, detail)
Joists ok bending 3.1 of 10 MPa; deflection 2.9 of 8.2 mm (span/360); span 2955 mm rim to rim, 2 kPa
```

A 2 kPa load on joists 400 mm apart is 0.8 N/mm per joist; over a 2955 mm span
that bends the joist to 3.1 MPa and sags it 2.9 mm, against 8.2 mm allowed at
span/360.

### What the checks cover

| Check | Rule / method |
|---|---|
| Stud spacing | `stud_spacing_max_mm` |
| Stud slenderness | stud length / depth ≤ `stud_slenderness_max` (sheathing assumed to brace the weak axis) |
| Headers, floor joists, rafters | beam bending and deflection with your design values and loads |
| Birdsmouth | notch depth square to the rafter ≤ `birdsmouth_max_fraction` of its depth |
| Ridge board depth | at least the rafter's plumb cut |
| Rafter ties | warns when ceiling joists are turned off |
| Wall anchoring | wall and tall cabinets (`anchor_cabinet_kinds`): required, anchors in the hardware list |

## 4. Shortcuts for the workbench

Keys bound to the Construction workbench only work while it is active and do
not change any other shortcut. Add them to `Hotkeys.json` in the user data
folder, then run **Tools > Reload Hotkeys**:

```json
{
  "bindings": [
    {"keys": ["C", "B"], "command": "Construction_BaseCabinet",
     "layer": "workspace", "scope": "ConstructionWorkbench"},
    {"keys": ["C", "L"], "command": "Construction_CutList",
     "layer": "workspace", "scope": "ConstructionWorkbench"}
  ]
}
```

Press `C` then `B` for a base cabinet. **Reload Hotkeys** reports in the
status bar and lists any conflicting bindings in the Report view.

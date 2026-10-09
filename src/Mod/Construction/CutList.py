# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: cut list and sheet estimate (design doc §5.6). No FreeCAD imports.

import math
from collections import Counter


def rows(parts_by_material):
    """Groups identical parts. parts_by_material: iterable of (material id, Part).
    Returns [(material, name, length, width, thickness, grain, qty)] sorted by
    material, then largest first. Sizes rounded to 0.1 mm."""
    counter = Counter()
    names = {}
    for material, part in parts_by_material:
        length, width, thick = (round(v, 1) for v in part.cut_size())
        key = (material, length, width, thick, part.grain is not None)
        counter[key] += 1
        names.setdefault(key, part.name)
    out = [
        (key[0], names[key], key[1], key[2], key[3], "yes" if key[4] else "no", qty)
        for key, qty in counter.items()
    ]
    out.sort(key=lambda r: (r[0], -r[2] * r[3], r[1]))
    return out


# ponytail: area-based estimate, not a cutting layout. Real layouts come from
# upstream BIM panel sheets / ArchNesting, or a guillotine packer (§5.6) later.
def sheet_estimate(cut_rows, sheet_area_mm2, waste=0.15):
    """material -> sheets needed, from total part area plus a waste allowance."""
    area = Counter()
    for material, _, length, width, _, _, qty in cut_rows:
        area[material] += length * width * qty
    return {
        m: math.ceil(a * (1 + waste) / sheet_area_mm2[m])
        for m, a in area.items()
        if sheet_area_mm2.get(m)
    }

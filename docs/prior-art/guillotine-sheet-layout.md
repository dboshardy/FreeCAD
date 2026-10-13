<!--
SPDX-License-Identifier: LGPL-2.1-or-later
FORK: added by the CADApp fork (design doc §12.4 item 2, risk R7).
-->

# Guillotine Sheet Layout

Implementation: `addons/construction/CutList.py` (`layout_sheets`, `_pack`).

Panel-saw layouts: rectangular parts on rectangular sheets, every cut running
edge to edge of the piece it splits (guillotine cuts), with saw kerf, edge trim,
and parts with grain kept along the sheet length.

| Technique | Source the code follows | Published |
|---|---|---|
| Guillotine cutting of rectangles | P. C. Gilmore, R. E. Gomory, "Multistage cutting stock problems of two and more dimensions", *Operations Research* 13(1) | 1965 |
| Free-rectangle guillotine packing; best-area / best-short-side / best-long-side fit; shorter- or longer-leftover-axis split | J. Jylänki, "A Thousand Ways to Pack the Bin — A Practical Approach to Two-Dimensional Rectangle Bin Packing" (technical report, public domain code alongside) | 2010 |
| Several greedy passes over different part orders, best result kept | Common practice in the bin-packing literature (multi-start greedy) | — |

No code was copied; the implementation is written from the descriptions above.

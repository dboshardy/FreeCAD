# SPDX-License-Identifier: LGPL-2.1-or-later
"""History strip logic: reorder features of a Body and move its tip, with a dependency check."""

import FreeCAD


def features(body):
    """Features in build order (the Origin and other non-features are skipped)."""
    return [o for o in body.Group if hasattr(o, "BaseFeature") or o.isDerivedFrom("Sketcher::SketchObject")]


def _needs(o):
    """Objects `o` really needs: its links, minus the BaseFeature chain, which PartDesign
    relinks on a reorder."""
    skip = getattr(o, "BaseFeature", None)
    return [d for d in o.OutList if d is not skip]


def _starts_a_solid(o):
    """True for features that make material from nothing. Cuts, dress-ups and patterns need a base."""
    # shortcut: by type name, so a Python-made additive feature is not recognised; upgrade
    # when such features need to lead a Body
    return o.TypeId in ("PartDesign::Pad", "PartDesign::Revolution", "PartDesign::Loft", "PartDesign::Pipe",
                        "PartDesign::Helix") or o.TypeId.startswith("PartDesign::Additive")


def depends_on(a, b):
    """True when `a` needs `b` to exist before it (b is in a's dependency closure)."""
    seen, todo = set(), _needs(a)
    while todo:
        d = todo.pop()
        if d.Name in seen:
            continue
        if d is b:
            return True
        seen.add(d.Name)
        todo.extend(_needs(d))
    return False


def can_move(body, feature, new_index):
    """Return (ok, reason). A feature may not move before something it needs, nor after
    something that needs it."""
    order = body.Group
    if feature not in order:
        return False, "%s is not in %s" % (feature.Name, body.Name)
    rest = [o for o in order if o is not feature]
    new_index = max(0, min(new_index, len(rest)))
    before, after = rest[:new_index], rest[new_index:]
    for o in after:
        if depends_on(feature, o):
            return False, "%s depends on %s" % (feature.Name, o.Name)
    for o in before:
        if depends_on(o, feature):
            return False, "%s depends on %s" % (o.Name, feature.Name)
    new_order = before + [feature] + after
    first = next((o for o in new_order if o.isDerivedFrom("PartDesign::Feature")), None)
    if first is not None and not _starts_a_solid(first):
        return False, "%s needs a solid before it" % first.Name
    return True, ""


def move(body, feature, new_index):
    """Move `feature` to `new_index` in `body.Group`. Raises ValueError if a dependency would break.

    Uses Body.removeObject/insertObject so the BaseFeature chain is relinked.
    """
    ok, why = can_move(body, feature, new_index)
    if not ok:
        raise ValueError(why)
    rest = [o for o in body.Group if o is not feature]
    new_index = max(0, min(new_index, len(rest)))
    body.removeObject(feature)
    if new_index == 0:
        body.insertObject(feature, rest[0], False)
    else:
        body.insertObject(feature, rest[new_index - 1], True)
    body.Document.recompute()


def set_marker(body, feature):
    """Move the history marker (Body.Tip) to `feature`: later features are not shown."""
    body.Tip = feature
    body.Document.recompute()

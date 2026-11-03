# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks for the custom-drawn UI that don't need a GPU: wheel geometry and
hit testing, floating card layout and hit testing, and that every card
widget points at an operator / property that exists in this Blender.

    python tests/test_custom_ui.py            # with `pip install bpy`
    blender -b --python tests/test_custom_ui.py
"""

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import addon_utils  # noqa: E402

failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


addon_utils.enable("sculpt_helper", default_set=True, handle_error=None)
from sculpt_helper import floating, menus, wheel  # noqa: E402

# Wheel ---------------------------------------------------------------------
names = [f"B{i}" for i in range(15)]
slots = wheel.layout(names, 1.0)
check(len(slots) == 15, "wheel has a slot per brush (no limit)")
check(abs(slots[0][1]) < 1e-6 and slots[0][2] > 0, "first brush at the top")
radii = sorted({round(math.hypot(x, y)) for _n, x, y, _s in slots})
check(len(radii) == 2, "more than twelve brushes add a second ring")
for i in (0, 3, 7, 13):
    _n, x, y, _s = slots[i]
    check(wheel.hit(slots, x + 3, y - 2, 40) == i, f"hit test finds slot {i}")
check(wheel.hit(slots, 5, 5, 40) is None, "centre picks nothing")
_n, x, y, _s = slots[2]
check(wheel.hit(slots, x * 0.8, y * 0.8, 40) == 2, "pointing toward a slot selects it")

favs = menus.brush_favorites(bpy.context)
wheel.ensure_linked(favs)
linked = [n for n in favs if wheel._find_brush(n) is not None]
check(len(linked) == len(favs), "favourite brushes link from the Essentials library")
b = wheel._find_brush(favs[0])
check(b is not None and b.preview_ensure() is not None, "brush previews are available")

# Floating cards ------------------------------------------------------------
m = floating.Metrics(1.0)
state = {"cards": {"BRUSH": {"open": True, "x": 100, "y": 600},
                   "MASK_HIDE": {"open": True, "x": 400, "y": 600, "collapsed": True},
                   "DEFORM": {"open": False, "x": 0, "y": 0}}}


class RNAProxy:
    def __init__(self, rna_type):
        self.bl_rna = rna_type.bl_rna

    def __getattr__(self, name):
        prop = self.bl_rna.properties[name]
        return prop.default


class Space:
    type = 'VIEW_3D'
    overlay = RNAProxy(bpy.types.View3DOverlay)
    shading = RNAProxy(bpy.types.View3DShading)


class Ctx:
    space_data = Space()

    def __getattr__(self, name):
        return getattr(bpy.context, name)


bpy.ops.mesh.primitive_uv_sphere_add()
bpy.ops.object.mode_set(mode='SCULPT')
ctx = Ctx()
rows = {cid: fn(ctx) for cid, fn in floating.CARDS.items()}
hits, cards = floating.layout_cards(state, rows, 1200, 800, m)
check([c[0] for c in cards] == ["BRUSH", "MASK_HIDE"], "only open cards are laid out")
brush = next(c for c in cards if c[0] == "BRUSH")
check(abs(brush[2] + brush[4] - 600) < 1e-6, "card top sits at its stored y")
mask = next(c for c in cards if c[0] == "MASK_HIDE")
check(abs(mask[4] - m.header) < 1e-6, "collapsed card is just its header")
h = floating.find_hit(hits, 100 + m.width / 2, 600 - m.header / 2)
check(h is not None and h[4] == "drag", "header middle drags the card")
h = floating.find_hit(hits, 100 + m.width - 3, 600 - 3)
check(h is not None and h[4] == "close", "top-right corner closes")
h = floating.find_hit(hits, 100 + 20, 600 - m.header - m.pad - m.row / 2)
check(h is not None and h[4] == "widget" and isinstance(h[6], floating.Slider),
      "first brush row is the radius slider")
check(floating.find_hit(hits, 50, 50) is None, "empty viewport is not captured")
tabs = floating.layout_tabs(state, 1200, 800, m)
check(len(tabs) == 1 + len(floating.CARDS), "tab bar has every panel plus the on/off button")

# Every widget must point at something real.
problems = []
for cid, card_rows in rows.items():
    for row in card_rows:
        for w in row:
            if isinstance(w, floating.Button):
                mod, name = w.op.split(".")
                if not hasattr(getattr(bpy.ops, mod), name):
                    problems.append(f"{cid}: no operator {w.op}")
                    continue
                rna = getattr(getattr(bpy.ops, mod), name).get_rna_type()
                for k, v in w.props.items():
                    p = rna.properties.get(k)
                    if p is None:
                        problems.append(f"{cid}: {w.op} has no '{k}'")
                    elif p.type == 'ENUM' and p.enum_items and v not in p.enum_items.keys():
                        problems.append(f"{cid}: {w.op}.{k} '{v}' not valid")
            elif isinstance(w, (floating.Toggle, floating.Slider, floating.Choice)):
                owner = w.owner(ctx)
                rna = getattr(owner, "bl_rna", None)
                if rna is None or w.prop not in rna.properties:
                    problems.append(f"{cid}: no property {w.prop} on {owner}")
                elif isinstance(w, floating.Choice) and w.value not in \
                        rna.properties[w.prop].enum_items.keys():
                    problems.append(f"{cid}: {w.prop} has no value {w.value}")
for p in problems:
    print("   ", p)
check(not problems, "every card widget targets an existing operator or property")

# Slider sets values from a fraction.
s = rows["BRUSH"][1][0]
s.act(ctx, 0.25)
check(abs(s.value(ctx) - 0.25) < 1e-6, "strength slider sets 0.25 at a quarter")

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)

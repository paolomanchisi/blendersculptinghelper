# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless smoke test. Run with Blender's Python module or Blender itself:

    python tests/test_headless.py            # with `pip install bpy`
    blender -b --python tests/test_headless.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402  (must come first: it sets up Blender's script paths)
import addon_utils  # noqa: E402

failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


mod = addon_utils.enable("sculpt_helper", default_set=True, handle_error=None)
check(mod is not None, "add-on enables")

for idname in ("sculpt_helper.hold_mask", "sculpt_helper.hold_isolate",
               "sculpt_helper.shortcut_list", "sculpt_helper.deform_filter",
               "sculpt_helper.multires_subdivide", "sculpt_helper.multires_level",
               "sculpt_helper.panel_help", "sculpt_helper.color_fill"):
    module, name = idname.split(".")
    check(hasattr(getattr(bpy.ops, module), name), f"operator {idname} registered")

check(all(hasattr(bpy.types, f"SCULPT_HELPER_PT_{p}") for p in ("brush", "mask_hide", "view_mode", "deform", "face_sets", "vertex_color", "material", "multires", "extract", "remesh")), "sidebar panels registered")
check("sculpt_helper" in bpy.context.preferences.addons, "preferences registered")

kc = bpy.context.window_manager.keyconfigs.addon
if kc is not None:
    km = kc.keymaps.get("Sculpt")
    ids = {k.idname for k in km.keymap_items} if km else set()
    check({"sculpt_helper.hold_mask", "sculpt_helper.hold_isolate",
           "sculpt_helper.shortcut_list", "wm.call_menu_pie", "wm.call_panel"} <= ids,
          "keymap items added")
    from sculpt_helper import keymap as shk
    pies = {k.properties.name for k in km.keymap_items if k.idname == "wm.call_menu_pie"}
    check(len(pies) == 3, "three pie menus bound (Q is the brush wheel)")
    check("sculpt_helper.brush_wheel" in ids, "Q brush wheel bound")
    for name in pies | {"SCULPT_HELPER_PT_view_popup", "SCULPT_HELPER_PT_panel_toggles",
                        "SCULPT_HELPER_MT_brush_pie"}:
        check(hasattr(bpy.types, name), f"{name} registered")

# Scene: a sphere in Sculpt Mode.
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("sculpt_helper", default_set=True, handle_error=None)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
obj = bpy.context.active_object
bpy.ops.object.mode_set(mode='SCULPT')
check(bpy.context.mode == 'SCULPT', "entered Sculpt Mode")

from sculpt_helper import utils  # noqa: E402

state = utils.capture_brush_state(bpy.context)
check(utils.activate_essential_brush("Mask"), "Mask brush activates")
ref = bpy.context.tool_settings.sculpt.brush_asset_reference
check(ref.relative_asset_identifier.endswith("/Brush/Mask"), "active brush is Mask")
check(utils.activate_essential_brush("Draw"), "Draw brush activates")
state = utils.capture_brush_state(bpy.context)
utils.activate_essential_brush("Mask")
utils.restore_brush_state(state)
ref = bpy.context.tool_settings.sculpt.brush_asset_reference
check(ref.relative_asset_identifier.endswith("/Brush/Draw"), "previous brush restored")

# Multires helpers.
bpy.ops.sculpt_helper.multires_subdivide(mode='CATMULL_CLARK')
mod = next((m for m in obj.modifiers if m.type == 'MULTIRES'), None)
check(mod is not None and mod.total_levels == 1, "Subdivide adds Multires level 1")
bpy.ops.sculpt_helper.multires_subdivide(mode='CATMULL_CLARK')
bpy.ops.sculpt_helper.multires_level(delta=-1)
check((mod.sculpt_levels, mod.levels, mod.render_levels) == (1, 1, 1), "linked levels step down")
bpy.context.scene.sculpt_helper.multires_link_levels = False
bpy.ops.sculpt_helper.multires_level(delta=1)
check((mod.sculpt_levels, mod.levels) == (2, 1), "unlinked level moves sculpt level only")

prefs = bpy.context.preferences.addons["sculpt_helper"].preferences
check(all(hasattr(prefs, "show_" + pid.lower()) for pid, _ in __import__(
    "sculpt_helper.panels", fromlist=["PANELS"]).PANELS), "panel toggles in preferences")

# The mask / visibility operators the hold keys call need a real 3D viewport
# (they crash or fail their poll in a windowless background session), so they
# are exercised by the manual checklist in README.md instead.

addon_utils.disable("sculpt_helper", default_set=True)
check(not hasattr(bpy.types, "SCULPT_HELPER_PT_mask_hide"), "add-on unregisters cleanly")

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)

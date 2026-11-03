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
               "sculpt_helper.shortcut_list"):
    module, name = idname.split(".")
    check(hasattr(getattr(bpy.ops, module), name), f"operator {idname} registered")

check(hasattr(bpy.types, "SCULPT_HELPER_PT_mask_hide"), "sidebar panel registered")
check("sculpt_helper" in bpy.context.preferences.addons, "preferences registered")

kc = bpy.context.window_manager.keyconfigs.addon
if kc is not None:
    km = kc.keymaps.get("Sculpt")
    ids = {k.idname for k in km.keymap_items} if km else set()
    check({"sculpt_helper.hold_mask", "sculpt_helper.hold_isolate",
           "sculpt_helper.shortcut_list"} <= ids, "keymap items added")

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

# The mask / visibility operators the hold keys call need a real 3D viewport
# (they crash or fail their poll in a windowless background session), so they
# are exercised by the manual checklist in README.md instead.

addon_utils.disable("sculpt_helper", default_set=True)
check(not hasattr(bpy.types, "SCULPT_HELPER_PT_mask_hide"), "add-on unregisters cleanly")

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)

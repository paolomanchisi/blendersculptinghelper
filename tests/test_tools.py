# SPDX-License-Identifier: GPL-3.0-or-later
"""Data-level tests for the step 3 tools (named masks, Morph, Depth Limit,
Copy Stamp, material by mask, sculpt together). These edit mesh data in
Object Mode, so they run without a viewport.

    python tests/test_tools.py            # with `pip install bpy`
    blender -b --python tests/test_tools.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import addon_utils  # noqa: E402
import numpy as np  # noqa: E402

failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("sculpt_helper", default_set=True, handle_error=None)
from sculpt_helper import meshdata as md  # noqa: E402
from sculpt_helper import ops_masks, ops_shape, ops_stamp  # noqa: E402

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0)
obj = bpy.context.active_object
mesh = obj.data
n = len(mesh.vertices)
z = md.get_positions(mesh)[:, 2]
top = (z > 0).astype(np.float32)
md.set_mask(mesh, top)
bpy.ops.object.mode_set(mode='SCULPT')

# Named masks ---------------------------------------------------------------
bpy.ops.sculpt_helper.mask_save(name="Top")
check(md.SAVED_MASK_PREFIX + "Top" in mesh.attributes, "mask saved as attribute")
check(bpy.context.mode == 'SCULPT', "back in Sculpt Mode after saving")
with md.object_mode(bpy.context) as m:
    x = md.get_positions(m)[:, 0]
    md.set_mask(m, (x > 0).astype(np.float32))
bpy.ops.sculpt_helper.mask_save(name="Right")
for mode, expect in (('REPLACE', top),
                     ('INTERSECT', top * (x > 0)),
                     ('ADD', np.maximum(top, x > 0)),
                     ('SUBTRACT', np.clip(top - (x > 0), 0, 1))):
    bpy.ops.sculpt_helper.mask_load(name="Top", mode='REPLACE')
    if mode != 'REPLACE':
        bpy.ops.sculpt_helper.mask_load(name="Right", mode=mode)
    with md.object_mode(bpy.context) as m:
        got = md.get_mask(m)
    check(np.allclose(got, expect), f"mask {mode.lower()} combines correctly")
check(md.saved_mask_names(mesh) == ["Right", "Top"], "saved masks listed")
bpy.ops.sculpt_helper.mask_delete(name="Right")
check(md.saved_mask_names(mesh) == ["Top"], "saved mask deleted")

# Morph ---------------------------------------------------------------------
bpy.ops.sculpt_helper.shape_record()
check(ops_shape.reference_valid(mesh), "shape recorded")
with md.object_mode(bpy.context) as m:
    original = md.get_positions(m).copy()
    md.set_positions(m, original * 1.2)
    md.set_mask(m, top)
bpy.ops.sculpt_helper.morph(strength=1.0)
with md.object_mode(bpy.context) as m:
    pos = md.get_positions(m)
check(np.allclose(pos[top > 0], original[top > 0], atol=1e-5), "morph restores masked area")
check(np.allclose(pos[top == 0], original[top == 0] * 1.2, atol=1e-5), "morph leaves unmasked area")

# Depth Limit ---------------------------------------------------------------
with md.object_mode(bpy.context) as m:
    md.set_positions(m, original * 1.5)  # pushed 0.5 out along the normal
settings = bpy.context.scene.sculpt_helper
settings.depth_limit_height = 0.1
bpy.ops.sculpt_helper.depth_limit_apply()
with md.object_mode(bpy.context) as m:
    r = np.linalg.norm(md.get_positions(m), axis=1)
check(np.allclose(r, 1.1, atol=2e-2), "depth limit clamps build-up to max height")

settings.depth_limit_auto = True
check(bpy.app.timers.is_registered(ops_shape._watcher), "auto depth limit watcher starts")
settings.depth_limit_auto = False

# Copy Stamp (functions) ----------------------------------------------------
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mesh.primitive_grid_add(x_subdivisions=80, y_subdivisions=80, size=4)
grid = bpy.context.active_object.data
p = md.get_positions(grid)
bump = np.exp(-((p[:, 0] + 1) ** 2 + p[:, 1] ** 2) / 0.02) * 0.2  # bump at (-1, 0)
p[:, 2] = bump
md.set_positions(grid, p)
sampled = ops_stamp.sample(grid, np.array([-1, 0, 0], np.float32), (0, 0, 1), (0, 1, 0), 0.5, 20)
check(sampled is not None, "stamp sample taken")
count = ops_stamp.stamp(grid, np.array([1, 0, 0], np.float32), (0, 0, 1), (0, 1, 0), 0.5,
                        sampled, 1.0, True, 20)
pos = md.get_positions(grid)
near_target = np.linalg.norm(pos[:, :2] - [1, 0], axis=1) < 0.05
check(count > 0 and pos[near_target, 2].max() > 0.08, "stamp raises a bump at the target")
far = np.linalg.norm(pos[:, :2] - [1, 0], axis=1) > 0.6
check(np.allclose(pos[far & (np.abs(pos[:, 0] + 1) > 0.6), 2], 0, atol=1e-4),
      "stamp leaves the rest of the surface")

# Material by mask ----------------------------------------------------------
bpy.context.view_layer.objects.active = obj
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
for name in ("Base", "Accent"):
    obj.data.materials.append(bpy.data.materials.new(name))
bpy.ops.object.mode_set(mode='SCULPT')
with md.object_mode(bpy.context) as m:
    md.set_mask(m, top)
obj.active_material_index = 1
bpy.ops.sculpt_helper.material_assign_masked()
idx = np.empty(len(mesh.polygons), np.int32)
mesh.polygons.foreach_get("material_index", idx)
centres = np.array([f.center.z for f in mesh.polygons])
check((idx[centres > 0.05] == 1).all() and (idx[centres < -0.05] == 0).all(),
      "masked faces get the active material")
with md.object_mode(bpy.context) as m:
    md.set_mask(m, np.zeros(len(m.vertices)))
bpy.ops.sculpt_helper.material_mask()
check(np.allclose(md.get_mask(mesh) > 0, z >= -1e-6) or
      (md.get_mask(mesh)[z > 0.1] == 1).all(), "mask by material covers that material")

# Sculpt together -----------------------------------------------------------
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("sculpt_helper", default_set=True, handle_error=None)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
a = bpy.context.active_object
a.name = "A"
a.modifiers.new("Bevel", 'BEVEL')
bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0), rotation=(0.3, 0, 0), scale=(2, 2, 2))
b = bpy.context.active_object
b.name = "B"
mat = bpy.data.materials.new("Skin")
b.data.materials.append(mat)
a.select_set(True)
b.select_set(True)
bpy.context.view_layer.objects.active = a
counts = (len(a.data.vertices), len(b.data.vertices))
b_world = [b.matrix_world @ v.co for v in b.data.vertices[:5]]
bpy.ops.sculpt_helper.multi_combine()
comb = bpy.context.active_object
check(comb.name.startswith("Combined") and bpy.context.mode == 'SCULPT', "combined into one object")
check(len(comb.data.vertices) == sum(counts), "combined object has all vertices")
check(a.hide_get() and b.hide_get(), "originals hidden while combined")
bpy.ops.sculpt_helper.multi_split()
check("Combined Sculpt" not in bpy.data.objects, "combined object removed")
check((len(a.data.vertices), len(b.data.vertices)) == counts, "vertex counts restored")
check(not a.hide_get() and not b.hide_get(), "originals visible again")
check(len(a.modifiers) == 1 and b.data.materials[0] == mat, "modifiers and materials kept")
b_after = [b.matrix_world @ v.co for v in b.data.vertices[:5]]
check(all((p - q).length < 1e-4 for p, q in zip(b_world, b_after)), "world positions preserved")

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)

# SPDX-License-Identifier: GPL-3.0-or-later
"""History timeline and Morph Target brush, data level (no viewport).

    python tests/test_history.py            # with `pip install bpy`
    blender -b --python tests/test_history.py
"""

import os
import sys
import tempfile

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
from sculpt_helper import history as hs  # noqa: E402
from sculpt_helper import history_ui  # noqa: E402
from sculpt_helper import meshdata as md  # noqa: E402

check(hasattr(bpy.types, "SCULPT_HELPER_PT_history"), "History panel registered")
for name in ("history_snapshot", "history_select", "history_jump", "history_paint_back",
             "history_delete", "history_clear", "morph_brush", "history_timeline"):
    check(hasattr(bpy.ops.sculpt_helper, name), f"operator {name} registered")

# Tree layout (pure Python) ----------------------------------------------------
h = hs.History()
a = h.add(None, None)
b = h.add(None, None)
c = h.add(None, None)
h.head = a.id            # jump back to A, then sculpt: a branch
d = h.add(None, None)
e = h.add(None, None)
check(d.parent == a.id and h.children(a.id) == [b.id, d.id], "going back starts a branch")
lanes = h.lanes()
check(lanes[b.id][1] == lanes[c.id][1] == lanes[a.id][1], "first child stays in its lane")
check(lanes[d.id][1] == lanes[e.id][1] != lanes[a.id][1], "branch gets its own lane")
check([lanes[s][0] for s in sorted(lanes)] == [0, 1, 2, 3, 4], "columns follow creation order")
h.remove(b.id)
check(c.parent == a.id, "deleting a snapshot moves its children up")
h.trim(2)
check(set(h.snaps) == {e.id, d.id} or e.id in h.snaps, "trim keeps the head")
check(len(h.snaps) <= 2, "trim respects the limit")
nodes = history_ui.strip_layout(h, 1200, 1.0)
check(len(nodes) == len(h.snaps) and any(n[3] for n in nodes), "strip layout places nodes")

# Snapshots on a real mesh -----------------------------------------------------
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0)
obj = bpy.context.active_object
bpy.ops.object.mode_set(mode='SCULPT')
ctx = bpy.context
settings = ctx.scene.sculpt_helper
settings.history_auto = False

s1 = hs.take_snapshot(ctx, obj, "start")
original = s1.positions.copy()
with md.object_mode(ctx) as mesh:
    md.set_positions(mesh, md.get_positions(mesh) * 1.5)
s2 = hs.take_snapshot(ctx, obj, "bigger")
hist = hs.history_for(obj)
check(s2.parent == s1.id and hist.head == s2.id, "snapshots chain")
check(ctx.mode == 'SCULPT', "still in Sculpt Mode after a snapshot")

# Blend halfway back to the first snapshot.
hist.selected = s1.id
hs.blend(ctx, obj, s1.id, 0.5)
hs.blend(ctx, obj, s1.id, 0.5)  # repeated calls use the same base
with md.object_mode(ctx) as mesh:
    check(np.allclose(md.get_positions(mesh), original * 1.25, atol=1e-5), "blend 0.5")
hs.blend(ctx, obj, s1.id, 0.0)
with md.object_mode(ctx) as mesh:
    check(np.allclose(md.get_positions(mesh), original * 1.5, atol=1e-5), "blend back to 0")
hs.end_blend(obj)

# Paint back only where masked.
with md.object_mode(ctx) as mesh:
    top = (md.get_positions(mesh)[:, 2] > 0).astype(np.float32)
    md.set_mask(mesh, top)
check(hs.paint_back(ctx, obj, s1.id), "paint back runs")
with md.object_mode(ctx) as mesh:
    pos = md.get_positions(mesh)
    t = top > 0
    check(np.allclose(pos[t], original[t], atol=1e-5), "masked part restored")
    check(np.allclose(pos[~t], original[~t] * 1.5, atol=1e-5), "unmasked part kept")
    md.set_mask(mesh, np.zeros(len(pos), np.float32))

# Morph Target brush dab.
with md.object_mode(ctx) as mesh:
    target = history_ui.morph_target(ctx, mesh)
    check(target is not None and np.allclose(target, original), "morph target = selected snapshot")
    pos = md.get_positions(mesh).astype(np.float64)
    centre = pos[np.argmin(pos[:, 2])].copy()  # bottom: still scaled
    before = np.linalg.norm(pos - target, axis=1)
    pos, count = history_ui.morph_dab(pos, target.astype(np.float64), centre, 0.5, 1.0,
                                      md.editable_weight(mesh))
    after = np.linalg.norm(pos - target, axis=1)
    near = np.linalg.norm(md.get_positions(mesh) - centre, axis=1) < 0.4
    check(count > 0 and after[near].mean() < before[near].mean() * 0.8, "dab pulls toward target")
    far = np.linalg.norm(md.get_positions(mesh) - centre, axis=1) > 0.6
    check(np.allclose(after[far], before[far]), "dab leaves the rest alone")
settings.morph_target = 'RECORDED'
with md.object_mode(ctx) as mesh:
    check(history_ui.morph_target(ctx, mesh) is None, "no recorded shape, no target")
settings.morph_target = 'SNAPSHOT'

# Jump after a topology change restores the whole mesh.
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.modifier_add(type='SUBSURF')
bpy.ops.object.modifier_apply(modifier=obj.modifiers[-1].name)
bpy.ops.object.mode_set(mode='SCULPT')
check(not hs.compatible(obj.data, s1), "topology change detected")
check(not hs.paint_back(ctx, obj, s1.id), "paint back refuses other topology")
hs.jump_to(ctx, obj, s1.id)
with md.object_mode(ctx) as mesh:
    check(len(mesh.vertices) == len(original)
          and np.allclose(md.get_positions(mesh), original, atol=1e-5), "jump restores mesh")
s3 = hs.take_snapshot(ctx, obj, "branch")
check(s3.parent == s1.id and set(hist.children(s1.id)) == {s2.id, s3.id}, "branch after jump")

# Operators (data level).
bpy.ops.sculpt_helper.history_select(sid=s2.id)
check(hist.selected == s2.id, "select operator")
bpy.ops.sculpt_helper.history_snapshot(label="by hand")
check(hist.snaps[hist.head].label == "by hand" and not hist.snaps[hist.head].auto,
      "snapshot operator")

# Max snapshots.
settings.history_max = 3
hs.take_snapshot(ctx, obj)
check(len(hist.snaps) == 3 and hist.head in hist.snaps, "history_max trims old snapshots")

# Keep in file: save, reload, snapshots come back --------------------------------
settings.history_keep_in_file = True
ids = sorted(hist.snaps)
parents = {sid: hist.snaps[sid].parent for sid in ids}
head = hist.head
path = os.path.join(tempfile.mkdtemp(), "history.blend")
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.save_as_mainfile(filepath=path)
check(not any(m.name.startswith(hs.FILE_PREFIX) for m in bpy.data.meshes),
      "stored copies removed after saving")
bpy.ops.wm.open_mainfile(filepath=path)
obj = bpy.data.objects["Sphere"]
hist = hs.history_for(obj, create=False)
check(hist is not None and sorted(hist.snaps) == ids, "snapshots reloaded")
check(hist is not None and {s: hist.snaps[s].parent for s in ids} == parents, "tree reloaded")
check(hist is not None and hist.head == head, "current snapshot reloaded")
check(not any(m.name.startswith(hs.FILE_PREFIX) for m in bpy.data.meshes),
      "stored copies cleaned up after loading")

bpy.context.scene.sculpt_helper.history_keep_in_file = False
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
check(hs.history_for(bpy.data.objects["Sphere"], create=False) is None,
      "without Keep in File nothing is stored")

addon_utils.disable("sculpt_helper", default_set=True)
check(not hasattr(bpy.types, "SCULPT_HELPER_PT_history"), "unregisters cleanly")

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)

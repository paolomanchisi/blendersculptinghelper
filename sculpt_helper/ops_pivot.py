# SPDX-License-Identifier: GPL-3.0-or-later
"""Pivot bend (Y): place pivots on joints and bend or twist the part beyond.

No face sets are needed. A pivot sits in the middle of the limb (halfway
between where the view ray enters and leaves the mesh). When you drag from a
pivot, the limb axis is estimated from the nearby vertices, the smaller
connected part on one side of the joint is chosen as the part that moves,
and it is rotated around the pivot with a smooth blend on the root side.

Keys while the tool is active:
  click mesh      add a pivot              drag a pivot   bend toward the drag
  T               bend <-> twist           X / Alt+click  delete the hovered pivot
  hold W + move   blend width (root side)  hold R + move  bend length (curl)
  M               only move unmasked       K              smooth the joint
  I               show influence           Y / Esc        finish
"""

import math

import bpy
import gpu
import numpy as np
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from . import meshdata as md
from . import utils

PIVOTS_PROP = "sculpt_helper_pivots"
HOVER_PX = 14


# ---------------------------------------------------------------------------
# Geometry (pure numpy; tested in tests/test_tools.py)


def principal_axis(points):
    centred = points - points.mean(axis=0)
    _vals, vecs = np.linalg.eigh(centred.T @ centred)
    return vecs[:, -1]


def grow_region(edge_array, allowed, seeds):
    """Vertices reachable from ``seeds`` through ``allowed`` vertices."""
    region = np.zeros(len(allowed), dtype=bool)
    region[seeds & allowed] = True
    a, b = edge_array[:, 0], edge_array[:, 1]
    while True:
        step = (region[a] & ~region[b] & allowed[b])
        back = (region[b] & ~region[a] & allowed[a])
        if not step.any() and not back.any():
            return region
        region[b[step]] = True
        region[a[back]] = True


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def smooth_weights(weights, edge_array, iterations):
    if iterations <= 0:
        return weights
    n = len(weights)
    a, b = edge_array[:, 0], edge_array[:, 1]
    degree = np.maximum(np.bincount(a, minlength=n) + np.bincount(b, minlength=n), 1)
    w = weights.copy()
    for _ in range(iterations):
        acc = np.zeros(n, dtype=np.float64)
        np.add.at(acc, a, w[b])
        np.add.at(acc, b, w[a])
        w = 0.5 * w + 0.5 * acc / degree
        w[weights == 0.0] = 0.0  # never leak outside the region
    return w


def setup_bend(positions, edge_array, pivot, thickness, blend_width, bend_length,
               mask=None, use_mask=False, smooth_iterations=3):
    """Work out which vertices move and how much.

    Returns dict(axis, weights) where ``axis`` points from the pivot toward
    the moving part, or None when nothing sensible can be found."""
    pivot = np.asarray(pivot, dtype=np.float64)
    d = positions - pivot
    dist = np.linalg.norm(d, axis=1)
    reach = max(thickness, 1e-6) * 1.5
    near = dist < reach
    if near.sum() < 4:
        return None
    axis = principal_axis(positions[near])
    s = d @ axis
    seeds_pos = near & (s > 0)
    seeds_neg = near & (s < 0)
    side_pos = grow_region(edge_array, s > -blend_width, seeds_pos)
    side_neg = grow_region(edge_array, s < blend_width, seeds_neg)
    # The part beyond the joint is the smaller one (hand, not body).
    if side_neg.sum() < side_pos.sum():
        axis, s, region = -axis, -s, side_neg
    else:
        region = side_pos
    if not region.any():
        return None
    span = blend_width + max(bend_length, 0.0)
    weights = np.where(region, smoothstep((s + blend_width) / max(span, 1e-6)), 0.0)
    if use_mask and mask is not None:
        weights *= 1.0 - mask
    weights = smooth_weights(weights, edge_array, smooth_iterations)
    return {"axis": axis, "weights": weights}


def rotate(positions, pivot, axis, angle, weights):
    """Rotate each vertex about ``axis`` through ``pivot`` by angle*weight."""
    k = np.asarray(axis, dtype=np.float64)
    k = k / max(np.linalg.norm(k), 1e-12)
    theta = (angle * weights)[:, None]
    v = positions - pivot
    cos, sin = np.cos(theta), np.sin(theta)
    kv = np.cross(k, v)
    kdot = (v @ k)[:, None] * k
    return pivot + v * cos + kv * sin + kdot * (1.0 - cos)


MIRROR = np.diag([-1.0, 1.0, 1.0])


# ---------------------------------------------------------------------------
# Pivot storage


def get_pivots(obj):
    """List of (location, thickness) in object space."""
    out = []
    for p in obj.get(PIVOTS_PROP, []):
        p = list(p)
        out.append((Vector(p[:3]), p[3] if len(p) > 3 else 0.0))
    return out


def set_pivots(obj, pivots):
    obj[PIVOTS_PROP] = [[*loc, float(t)] for loc, t in pivots]


def joint_centre(context, coord):
    """Midpoint between where the view ray enters and leaves the mesh."""
    region, rv3d = context.region, context.region_data
    obj = context.active_object
    obj_eval = obj.evaluated_get(context.evaluated_depsgraph_get())
    inv = obj_eval.matrix_world.inverted()
    origin = inv @ view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = (inv.to_3x3() @ view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)).normalized()
    hit, front, _n, _i = obj_eval.ray_cast(origin, direction)
    if not hit:
        return None, 0.0
    hit2, back, _n2, _i2 = obj_eval.ray_cast(front + direction * 1e-4, direction)
    if not hit2:
        return front, 0.0
    return (front + back) * 0.5, (back - front).length


# ---------------------------------------------------------------------------
# Modal tool


class SCULPT_HELPER_OT_pivot_bend(bpy.types.Operator):
    bl_idname = "sculpt_helper.pivot_bend"
    bl_label = "Pivot Bend"
    bl_description = ("Place pivots on joints and drag them to bend (T: twist) the part "
                      "beyond. No face sets needed")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not utils.in_sculpt_mode(context):
            return False
        reason = md.unsupported_reason(context.active_object)
        if reason:
            cls.poll_message_set(reason)
            return False
        return True

    # -- lifecycle --------------------------------------------------------

    def invoke(self, context, event):
        self._key = event.type
        self._hover = None
        self._drag = None
        self._adjust = None
        self._influence = None
        self._show_influence = False
        self._twist = False
        self._handles = (
            bpy.types.SpaceView3D.draw_handler_add(self._draw_px, (context,), 'WINDOW', 'POST_PIXEL'),
            bpy.types.SpaceView3D.draw_handler_add(self._draw_3d, (context,), 'WINDOW', 'POST_VIEW'),
        )
        context.window_manager.modal_handler_add(self)
        self._status(context)
        return {'RUNNING_MODAL'}

    def _settings(self, context):
        return context.scene.sculpt_helper

    def _status(self, context):
        s = self._settings(context)
        mode = "Twist" if self._twist else "Bend"
        context.workspace.status_text_set(
            f"Pivot {mode} · click mesh: add pivot · drag pivot: {mode.lower()} · T bend/twist · "
            f"W width {s.pivot_blend:.2f} · R length {s.pivot_length:.2f} · "
            f"M mask {'on' if s.pivot_use_mask else 'off'} · "
            f"K smooth {'on' if s.pivot_smooth else 'off'} · I influence · X delete · Y/Esc done")

    def _finish(self, context):
        for h in self._handles:
            bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
        context.workspace.status_text_set(None)
        context.area.tag_redraw()
        return {'FINISHED'}

    # -- helpers ----------------------------------------------------------

    def _pivot_screen(self, context, p):
        obj = context.active_object
        return view3d_utils.location_3d_to_region_2d(
            context.region, context.region_data, obj.matrix_world @ p)

    def _hovered(self, context, coord):
        best, best_d = None, HOVER_PX
        for i, (p, _t) in enumerate(get_pivots(context.active_object)):
            sp = self._pivot_screen(context, p)
            if sp is None:
                continue
            d = math.hypot(sp[0] - coord[0], sp[1] - coord[1])
            if d < best_d:
                best, best_d = i, d
        return best

    def _setup(self, context, mesh, pivot_index):
        s = self._settings(context)
        obj = context.active_object
        loc, thickness = get_pivots(obj)[pivot_index]
        pivot = np.array(loc, dtype=np.float64)
        pos = md.get_positions(mesh).astype(np.float64)
        edge_array = md.edges(mesh)
        mask = md.get_mask(mesh)
        if not thickness:
            # Fall back to the distance to the nearest surface, doubled.
            thickness = 2.0 * float(np.min(np.linalg.norm(pos - pivot, axis=1)))
        kw = dict(thickness=thickness, blend_width=s.pivot_blend * thickness,
                  bend_length=s.pivot_length * thickness, mask=mask,
                  use_mask=s.pivot_use_mask, smooth_iterations=8 if s.pivot_smooth else 2)
        parts = []
        main = setup_bend(pos, edge_array, pivot, **kw)
        if main is None:
            return None
        parts.append((pivot, main["axis"], main["weights"], False))
        if mesh.use_mirror_x and abs(pivot[0]) > thickness * 0.5:
            mpivot = MIRROR @ pivot
            mirrored = setup_bend(pos, edge_array, mpivot, **kw)
            if mirrored is not None:
                parts.append((mpivot, mirrored["axis"], mirrored["weights"], True))
        return {"base": pos, "parts": parts}

    def _apply(self, context, mesh, angle_vec):
        """angle_vec: (axis in object space or None for twist, angle)."""
        base = self._drag["setup"]["base"]
        out = base.copy()
        for pivot, limb_axis, weights, mirrored in self._drag["setup"]["parts"]:
            if self._twist:
                rot_axis = limb_axis
                angle = angle_vec[1] * (-1.0 if mirrored else 1.0)
            else:
                rot_axis = np.cross(limb_axis, angle_vec[0]) if not mirrored else \
                    -(MIRROR @ np.cross(MIRROR @ limb_axis, angle_vec[0]))
                if np.linalg.norm(rot_axis) < 1e-9:
                    continue
                angle = angle_vec[1]
            moved = rotate(out, pivot, rot_axis, angle, weights)
            sel = weights > 0
            out[sel] = moved[sel]
        md.set_positions(mesh, out)

    # -- modal ------------------------------------------------------------

    def modal(self, context, event):
        context.area.tag_redraw()
        coord = (event.mouse_region_x, event.mouse_region_y)
        s = self._settings(context)

        if self._drag is not None:
            return self._modal_drag(context, event, coord)

        if self._adjust is not None:
            name, key, x0, v0 = self._adjust
            if event.type == key and event.value == 'RELEASE':
                self._adjust = None
                self._influence = None
            elif event.type == 'MOUSEMOVE':
                setattr(s, name, max(0.0, v0 + (coord[0] - x0) / 200.0))
                self._influence = None
                self._status(context)
            return {'RUNNING_MODAL'}

        if event.type in {'ESC', self._key} and event.value == 'PRESS':
            return self._finish(context)

        if event.type == 'MOUSEMOVE':
            hover = self._hovered(context, coord)
            if hover != self._hover:
                self._hover = hover
                self._influence = None
            return {'PASS_THROUGH'}

        if event.value == 'PRESS':
            if event.type == 'T':
                self._twist = not self._twist
            elif event.type == 'M':
                s.pivot_use_mask = not s.pivot_use_mask
                self._influence = None
            elif event.type == 'K':
                s.pivot_smooth = not s.pivot_smooth
                self._influence = None
            elif event.type == 'I':
                self._show_influence = not self._show_influence
                self._influence = None
            elif event.type in {'W', 'R'}:
                name = "pivot_blend" if event.type == 'W' else "pivot_length"
                self._adjust = (name, event.type, coord[0], getattr(s, name))
            elif event.type in {'X', 'DEL'} and self._hover is not None:
                self._delete(context, self._hover)
            elif event.type == 'LEFTMOUSE':
                return self._press(context, event, coord)
            else:
                return {'PASS_THROUGH'}
            self._status(context)
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}

    def _delete(self, context, index):
        obj = context.active_object
        pivots = get_pivots(obj)
        del pivots[index]
        set_pivots(obj, pivots)
        self._hover = None
        self._influence = None

    def _press(self, context, event, coord):
        obj = context.active_object
        if self._hover is not None and event.alt:
            self._delete(context, self._hover)
            return {'RUNNING_MODAL'}
        if self._hover is not None:
            bpy.ops.object.mode_set(mode='OBJECT')
            setup = self._setup(context, obj.data, self._hover)
            if setup is None:
                bpy.ops.object.mode_set(mode='SCULPT')
                self.report({'WARNING'}, "Couldn't find a limb around this pivot")
                return {'RUNNING_MODAL'}
            self._drag = {"start": coord, "setup": setup}
            return {'RUNNING_MODAL'}
        centre, thickness = joint_centre(context, coord)
        if centre is None:
            return {'PASS_THROUGH'}
        pivots = get_pivots(obj)
        pivots.append((centre, thickness))
        set_pivots(obj, pivots)
        self._hover = len(pivots) - 1
        return {'RUNNING_MODAL'}

    def _modal_drag(self, context, event, coord):
        mesh = context.active_object.data
        if event.type == 'T' and event.value == 'PRESS':
            self._twist = not self._twist
            self._status(context)
        if event.type in {'MOUSEMOVE', 'T'}:
            dx = coord[0] - self._drag["start"][0]
            dy = coord[1] - self._drag["start"][1]
            if self._twist:
                self._apply(context, mesh, (None, math.radians(dx * 0.5)))
            else:
                obj = context.active_object
                view = context.region_data.view_rotation
                world_dir = view @ Vector((dx, dy, 0.0))
                local = np.array(obj.matrix_world.inverted().to_3x3() @ world_dir)
                length = math.hypot(dx, dy)
                if length > 1:
                    self._apply(context, mesh, (local / np.linalg.norm(local),
                                                math.radians(min(length * 0.4, 180.0))))
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._drag = None
            self._influence = None
            bpy.ops.object.mode_set(mode='SCULPT')
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            md.set_positions(mesh, self._drag["setup"]["base"])
            self._drag = None
            bpy.ops.object.mode_set(mode='SCULPT')
            return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}

    # -- drawing ----------------------------------------------------------

    def _draw_px(self, context):
        obj = context.active_object
        if obj is None:
            return
        pts, hover_pts = [], []
        for i, (p, _t) in enumerate(get_pivots(obj)):
            sp = self._pivot_screen(context, p)
            if sp is None:
                continue
            (hover_pts if i == self._hover else pts).append((sp[0], sp[1], 0.0))
        shader = gpu.shader.from_builtin('POINT_UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        for points, colour, size in ((pts, (1, 1, 1, 0.9), 8.0),
                                     (hover_pts, (1.0, 0.55, 0.1, 1.0), 12.0)):
            if points:
                gpu.state.point_size_set(size)
                shader.uniform_float("color", colour)
                batch_for_shader(shader, 'POINTS', {"pos": points}).draw(shader)
        gpu.state.blend_set('NONE')

    def _draw_3d(self, context):
        if not self._show_influence or self._hover is None or self._drag is not None:
            return
        obj = context.active_object
        if self._influence is None:
            try:
                setup = self._setup(context, obj.data, self._hover)
            except Exception:  # noqa: BLE001 - drawing must never raise
                setup = None
            if setup is None:
                self._influence = ([], [])
            else:
                w = np.zeros(len(setup["base"]))
                for _p, _a, weights, _m in setup["parts"]:
                    w = np.maximum(w, weights)
                sel = np.nonzero(w > 0.02)[0]
                if len(sel) > 30000:
                    sel = sel[:: len(sel) // 30000 + 1]
                mw = np.array(obj.matrix_world)
                pts = setup["base"][sel] @ mw[:3, :3].T + mw[:3, 3]
                cols = np.zeros((len(sel), 4), dtype=np.float32)
                cols[:] = (0.1, 0.85, 0.85, 1.0)
                cols[:, 3] = 0.25 + 0.6 * w[sel]
                self._influence = (pts.astype(np.float32).tolist(), cols.tolist())
        pts, cols = self._influence
        if not pts:
            return
        shader = gpu.shader.from_builtin('POINT_FLAT_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.point_size_set(3.0)
        batch_for_shader(shader, 'POINTS', {"pos": pts, "color": cols}).draw(shader)
        gpu.state.blend_set('NONE')


class SCULPT_HELPER_OT_pivot_clear(bpy.types.Operator):
    bl_idname = "sculpt_helper.pivot_clear"
    bl_label = "Clear Pivots"
    bl_description = "Remove every pivot from the active object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and PIVOTS_PROP in obj

    def execute(self, context):
        del context.active_object[PIVOTS_PROP]
        return {'FINISHED'}


def draw_pivot(layout, context):
    s = context.scene.sculpt_helper
    obj = context.active_object
    col = layout.column(align=True)
    col.operator("sculpt_helper.pivot_bend", text="Pivot Bend (Y)", icon='CON_KINEMATIC')
    col.prop(s, "pivot_blend")
    col.prop(s, "pivot_length")
    row = col.row(align=True)
    row.prop(s, "pivot_use_mask", toggle=True)
    row.prop(s, "pivot_smooth", toggle=True)
    count = len(obj.get(PIVOTS_PROP, [])) if obj else 0
    row = col.row(align=True)
    row.label(text=f"{count} pivot(s)")
    row.operator("sculpt_helper.pivot_clear", text="", icon='TRASH')


classes = (SCULPT_HELPER_OT_pivot_bend, SCULPT_HELPER_OT_pivot_clear)

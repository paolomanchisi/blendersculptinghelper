# SPDX-License-Identifier: GPL-3.0-or-later
"""Copy Stamp: sample the surface detail under the cursor and stamp it
elsewhere.

"Detail" is the difference between the surface and a smoothed copy of it,
measured in a frame built from the surface normal and the view's up
direction. Stamping adds (or replaces) that detail at the new spot, fading
out toward the edge of the brush radius. Masked and hidden areas are kept.
"""

import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

from . import meshdata as md
from . import utils


def frame(normal, view_up):
    n = Vector(normal).normalized()
    t = Vector(view_up) - n * Vector(view_up).dot(n)
    if t.length < 1e-6:
        t = n.orthogonal()
    t.normalize()
    b = n.cross(t)
    return np.array([t, b, n], dtype=np.float32)  # rows: tangent, bitangent, normal


def local_detail(mesh, centre, radius, smooth_iterations):
    """Return (indices, positions, smoothed) for vertices within 1.6 radius."""
    pos = md.get_positions(mesh)
    dist = np.linalg.norm(pos - centre, axis=1)
    near = np.nonzero(dist < radius * 1.6)[0]
    if len(near) == 0:
        return near, pos, pos
    remap = np.full(len(pos), -1, dtype=np.int64)
    remap[near] = np.arange(len(near))
    e = md.edges(mesh)
    keep = (remap[e[:, 0]] >= 0) & (remap[e[:, 1]] >= 0)
    sub_edges = remap[e[keep]]
    sub = pos[near]
    smoothed = md.smooth(sub, sub_edges, iterations=smooth_iterations)
    return near, pos, smoothed


def sample(mesh, centre, normal, view_up, radius, smooth_iterations):
    near, pos, smoothed = local_detail(mesh, centre, radius, smooth_iterations)
    if len(near) == 0:
        return None
    f = frame(normal, view_up)
    rel = (pos[near] - centre) @ f.T          # (u, v, h) per vertex
    detail = (pos[near] - smoothed) @ f.T      # detail in frame coordinates
    inside = np.linalg.norm(rel[:, :2], axis=1) <= radius
    uv = rel[inside, :2] / radius
    detail = detail[inside]
    if len(uv) < 3:
        return None
    tree = KDTree(len(uv))
    for i, (u, v) in enumerate(uv):
        tree.insert((u, v, 0.0), i)
    tree.balance()
    return {"tree": tree, "detail": detail}


def stamp(mesh, centre, normal, view_up, radius, sampled, strength, replace,
          smooth_iterations):
    near, pos, smoothed = local_detail(mesh, centre, radius, smooth_iterations)
    if len(near) == 0:
        return 0
    f = frame(normal, view_up)
    rel = (pos[near] - centre) @ f.T
    uv = rel[:, :2] / radius
    r = np.linalg.norm(uv, axis=1)
    inside = r <= 1.0
    if not inside.any():
        return 0
    idx = near[inside]
    picks = np.array([sampled["tree"].find((u, v, 0.0))[1] for u, v in uv[inside]])
    src = sampled["detail"][picks] @ f          # back to object space
    t = np.clip(1.0 - r[inside], 0.0, 1.0)
    falloff = t * t * (3.0 - 2.0 * t)            # smoothstep
    weight = (falloff * strength * md.editable_weight(mesh)[idx])[:, None]
    if replace:
        own = pos[idx] - smoothed[inside]
        new = pos[idx] + (src - own) * weight
    else:
        new = pos[idx] + src * weight
    pos[idx] = new
    md.set_positions(mesh, pos)
    return len(idx)


class SCULPT_HELPER_OT_copy_stamp(md.MeshDataOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.copy_stamp"
    bl_label = "Copy Stamp"
    bl_description = ("Click to sample the surface detail, then click elsewhere to stamp it. "
                      "Shift+click resamples, Esc or right-click finishes")
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        if not utils.in_sculpt_mode(context):
            return {'CANCELLED'}
        self._sample = None
        context.window_manager.modal_handler_add(self)
        self._status(context)
        return {'RUNNING_MODAL'}

    def _status(self, context):
        context.workspace.status_text_set(
            ("Click to stamp · Shift+click to resample" if self._sample
             else "Click the detail to copy") + " · F radius · Esc / right-click to finish")

    def _brush_pixels(self, context):
        ups = context.tool_settings.sculpt.unified_paint_settings
        brush = context.tool_settings.sculpt.brush
        return ups.size if (ups.use_unified_size or brush is None) else brush.size

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            context.workspace.status_text_set(None)
            return {'FINISHED'}
        if event.type != 'LEFTMOUSE' or event.value != 'PRESS':
            return {'PASS_THROUGH'}
        coord = (event.mouse_region_x, event.mouse_region_y)
        hit = utils.raycast_active(context, coord)
        if hit is None:
            return {'RUNNING_MODAL'}
        loc, normal, _face = hit
        radius = utils.pixel_radius_to_object(context, coord, loc, self._brush_pixels(context))
        if radius <= 0.0:
            return {'RUNNING_MODAL'}
        obj = context.active_object
        view_up = obj.matrix_world.inverted().to_3x3() @ (
            context.region_data.view_rotation @ Vector((0.0, 1.0, 0.0)))
        settings = context.scene.sculpt_helper
        centre = np.array(loc, dtype=np.float32)
        with md.object_mode(context) as mesh:
            if self._sample is None or event.shift:
                self._sample = sample(mesh, centre, normal, view_up, radius,
                                      settings.stamp_smooth)
                if self._sample is None:
                    self.report({'WARNING'}, "Not enough vertices under the brush to sample")
            else:
                stamp(mesh, centre, normal, view_up, radius, self._sample,
                      settings.stamp_strength, settings.stamp_replace, settings.stamp_smooth)
        self._status(context)
        return {'RUNNING_MODAL'}


def draw_stamp(layout, context):
    settings = context.scene.sculpt_helper
    col = layout.column(align=True)
    col.prop(settings, "stamp_strength", slider=True)
    col.prop(settings, "stamp_smooth")
    col.prop(settings, "stamp_replace")
    col.operator("sculpt_helper.copy_stamp", icon='CLONE')


classes = (SCULPT_HELPER_OT_copy_stamp,)

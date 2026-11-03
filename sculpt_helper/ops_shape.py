# SPDX-License-Identifier: GPL-3.0-or-later
"""Reference shape tools: record a shape, Morph back to it, Depth Limit.

* Record Shape stores the current vertex positions and normals on the mesh.
* Morph moves the masked area back toward the recorded shape (paint the
  mask where you want the old shape back, then press Morph).
* Depth Limit keeps every vertex within a height above and a depth below the
  recorded surface, so strokes can't over-build or over-cut. With Auto on it
  is applied after every stroke.
"""

import bpy
import numpy as np

from . import meshdata as md


def has_reference(obj):
    return obj is not None and obj.type == 'MESH' and md.REF_ATTR in obj.data.attributes


def reference_valid(mesh):
    attr = mesh.attributes.get(md.REF_ATTR)
    return attr is not None and len(attr.data) == len(mesh.vertices)


class SCULPT_HELPER_OT_shape_record(md.MeshDataOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.shape_record"
    bl_label = "Record Shape"
    bl_description = "Remember the current shape for Morph and Depth Limit"

    def execute(self, context):
        with md.object_mode(context) as mesh:
            md.set_vectors(mesh, md.REF_ATTR, md.get_positions(mesh))
            md.set_vectors(mesh, md.REF_NORMAL_ATTR, md.get_normals(mesh))
        self.report({'INFO'}, "Shape recorded")
        return {'FINISHED'}


class SCULPT_HELPER_OT_shape_clear(md.MeshDataOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.shape_clear"
    bl_label = "Forget Shape"
    bl_description = "Delete the recorded shape"

    def execute(self, context):
        with md.object_mode(context) as mesh:
            for name in (md.REF_ATTR, md.REF_NORMAL_ATTR):
                attr = mesh.attributes.get(name)
                if attr is not None:
                    mesh.attributes.remove(attr)
        return {'FINISHED'}


def morph(positions, reference, weight, strength):
    w = np.clip(weight * strength, 0.0, 1.0)[:, None]
    return positions + (reference - positions) * w


def depth_clamp(positions, reference, normals, height, depth):
    offset = positions - reference
    along = np.einsum("ij,ij->i", offset, normals)
    clamped = np.clip(along, -depth, height)
    return positions + normals * (clamped - along)[:, None], int(np.count_nonzero(clamped != along))


class SCULPT_HELPER_OT_morph(md.MeshDataOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.morph"
    bl_label = "Morph to Recorded Shape"
    bl_description = "Move the masked area back toward the recorded shape"

    strength: bpy.props.FloatProperty(name="Strength", default=1.0, min=0.0, max=1.0)
    invert: bpy.props.BoolProperty(
        name="Unmasked Area", description="Morph the unmasked area instead", default=False)

    def execute(self, context):
        with md.object_mode(context) as mesh:
            if not reference_valid(mesh):
                self.report({'WARNING'}, "Record a shape first (topology must not change)")
                return {'CANCELLED'}
            mask = md.get_mask(mesh)
            weight = (1.0 - mask if self.invert else mask) * ~md.get_hidden(mesh)
            pos = morph(md.get_positions(mesh), md.get_vectors(mesh, md.REF_ATTR),
                        weight, self.strength)
            md.set_positions(mesh, pos)
        return {'FINISHED'}


def apply_depth_limit(context, report=None):
    settings = context.scene.sculpt_helper
    with md.object_mode(context) as mesh:
        if not reference_valid(mesh):
            if report:
                report({'WARNING'}, "Record a shape first (topology must not change)")
            return 0
        pos, count = depth_clamp(
            md.get_positions(mesh), md.get_vectors(mesh, md.REF_ATTR),
            md.get_vectors(mesh, md.REF_NORMAL_ATTR),
            settings.depth_limit_height, settings.depth_limit_depth)
        if count:
            md.set_positions(mesh, pos)
    return count


class SCULPT_HELPER_OT_depth_limit_apply(md.MeshDataOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.depth_limit_apply"
    bl_label = "Apply Depth Limit"
    bl_description = "Pull back everything that rose or sank past the limits"

    def execute(self, context):
        count = apply_depth_limit(context, self.report)
        self.report({'INFO'}, f"Depth Limit: {count} vertices clamped")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Auto Depth Limit: watch for the end of each brush stroke.

_watch = {"stroking": False}


def _find_view3d(win):
    for area in win.screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'WINDOW':
                    return area, region
    return None, None


def _watcher():
    scene = bpy.context.scene
    if scene is None or not scene.sculpt_helper.depth_limit_auto:
        _watch["stroking"] = False
        return None  # stop the timer
    wm = bpy.context.window_manager
    for win in wm.windows:
        running = any(op.bl_idname == "SCULPT_OT_brush_stroke" for op in win.modal_operators)
        if running:
            _watch["stroking"] = True
            return 0.05
        if _watch["stroking"]:
            _watch["stroking"] = False
            area, region = _find_view3d(win)
            obj = bpy.context.view_layer.objects.active
            if area and obj is not None and md.unsupported_reason(obj) is None:
                with bpy.context.temp_override(window=win, area=area, region=region):
                    if bpy.context.mode == 'SCULPT' and has_reference(obj):
                        apply_depth_limit(bpy.context)
    return 0.1


def depth_auto_update(self, context):
    if self.depth_limit_auto and not bpy.app.timers.is_registered(_watcher):
        bpy.app.timers.register(_watcher, first_interval=0.1)


def unregister():
    if bpy.app.timers.is_registered(_watcher):
        bpy.app.timers.unregister(_watcher)


def draw_depth_limit(layout, context):
    obj = context.active_object
    settings = context.scene.sculpt_helper
    col = layout.column(align=True)
    reason = md.unsupported_reason(obj)
    if reason:
        col.label(text=reason, icon='INFO')
        return
    row = col.row(align=True)
    row.operator("sculpt_helper.shape_record",
                 text="Re-record Shape" if has_reference(obj) else "Record Shape",
                 icon='REC')
    if has_reference(obj):
        row.operator("sculpt_helper.shape_clear", text="", icon='TRASH')
    sub = col.column(align=True)
    sub.active = has_reference(obj)
    sub.prop(settings, "depth_limit_height")
    sub.prop(settings, "depth_limit_depth")
    row = sub.row(align=True)
    row.prop(settings, "depth_limit_auto", toggle=True)
    row.operator("sculpt_helper.depth_limit_apply", text="Apply Now")


def draw_morph(layout, context):
    obj = context.active_object
    col = layout.column(align=True)
    reason = md.unsupported_reason(obj)
    if reason:
        col.label(text=reason, icon='INFO')
        return
    col.operator("sculpt_helper.shape_record",
                 text="Re-record Shape" if has_reference(obj) else "Record Shape", icon='REC')
    row = col.row(align=True)
    row.enabled = has_reference(obj)
    row.operator("sculpt_helper.morph", text="Morph Masked").invert = False
    row.operator("sculpt_helper.morph", text="Morph Unmasked").invert = True


classes = (
    SCULPT_HELPER_OT_shape_record,
    SCULPT_HELPER_OT_shape_clear,
    SCULPT_HELPER_OT_morph,
    SCULPT_HELPER_OT_depth_limit_apply,
)

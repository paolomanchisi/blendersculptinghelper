# SPDX-License-Identifier: GPL-3.0-or-later
"""Named masks stored on the mesh, combinable by add / subtract / intersect."""

import bpy
import numpy as np

from . import meshdata as md


class SCULPT_HELPER_OT_mask_save(md.MeshDataOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.mask_save"
    bl_label = "Save Mask"
    bl_description = "Save the current mask under a name"

    name: bpy.props.StringProperty(name="Name", default="Mask")

    def invoke(self, context, event):
        existing = md.saved_mask_names(context.active_object.data)
        i = len(existing) + 1
        while f"Mask {i}" in existing:
            i += 1
        self.name = f"Mask {i}"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = self.name.strip()
        if not name:
            self.report({'WARNING'}, "Give the mask a name")
            return {'CANCELLED'}
        with md.object_mode(context) as mesh:
            md.set_float(mesh, md.SAVED_MASK_PREFIX + name, md.get_mask(mesh))
        self.report({'INFO'}, f"Saved mask '{name}'")
        return {'FINISHED'}


def combine(current, saved, mode):
    if mode == 'REPLACE':
        return saved
    if mode == 'ADD':
        return np.maximum(current, saved)
    if mode == 'SUBTRACT':
        return np.clip(current - saved, 0.0, 1.0)
    if mode == 'INTERSECT':
        return np.minimum(current, saved)
    raise ValueError(mode)


class SCULPT_HELPER_OT_mask_load(md.MeshDataOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.mask_load"
    bl_label = "Load Mask"
    bl_description = "Load a saved mask, or combine it with the current one"

    name: bpy.props.StringProperty()
    mode: bpy.props.EnumProperty(items=(
        ('REPLACE', "Load", "Replace the current mask"),
        ('ADD', "Add", "Add to the current mask"),
        ('SUBTRACT', "Subtract", "Remove from the current mask"),
        ('INTERSECT', "Intersect", "Keep only what both masks cover"),
    ))

    def execute(self, context):
        with md.object_mode(context) as mesh:
            attr_name = md.SAVED_MASK_PREFIX + self.name
            if attr_name not in mesh.attributes:
                self.report({'WARNING'}, f"No saved mask '{self.name}'")
                return {'CANCELLED'}
            saved = md.get_float(mesh, attr_name)
            md.set_mask(mesh, combine(md.get_mask(mesh), saved, self.mode))
        return {'FINISHED'}


class SCULPT_HELPER_OT_mask_delete(md.MeshDataOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.mask_delete"
    bl_label = "Delete Saved Mask"
    bl_description = "Delete this saved mask"

    name: bpy.props.StringProperty()

    def execute(self, context):
        with md.object_mode(context) as mesh:
            attr = mesh.attributes.get(md.SAVED_MASK_PREFIX + self.name)
            if attr is not None:
                mesh.attributes.remove(attr)
        return {'FINISHED'}


def draw_saved_masks(layout, context):
    obj = context.active_object
    col = layout.column(align=True)
    row = col.row(align=True)
    row.label(text="Saved Masks")
    row.operator("sculpt_helper.mask_save", text="Save", icon='ADD')
    reason = md.unsupported_reason(obj)
    if reason:
        col.label(text=reason, icon='INFO')
        return
    names = md.saved_mask_names(obj.data)
    if not names:
        col.label(text="None yet")
    for name in names:
        row = col.row(align=True)
        row.label(text=name)
        for mode, icon in (('REPLACE', 'IMPORT'), ('ADD', 'ADD'),
                           ('SUBTRACT', 'REMOVE'), ('INTERSECT', 'SELECT_INTERSECT')):
            op = row.operator("sculpt_helper.mask_load", text="", icon=icon)
            op.name, op.mode = name, mode
        row.operator("sculpt_helper.mask_delete", text="", icon='TRASH').name = name


classes = (
    SCULPT_HELPER_OT_mask_save,
    SCULPT_HELPER_OT_mask_load,
    SCULPT_HELPER_OT_mask_delete,
)

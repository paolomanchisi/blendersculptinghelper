# SPDX-License-Identifier: GPL-3.0-or-later
"""Assign materials to the masked area, and mask by material."""

import bpy
import numpy as np

from . import meshdata as md


def face_mask(mesh):
    """Average vertex mask per face."""
    loop_vert = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_vert)
    starts = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("loop_start", starts)
    counts = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("loop_total", counts)
    mask = md.get_mask(mesh)[loop_vert]
    return np.add.reduceat(mask, starts) / counts, loop_vert, starts, counts


class SCULPT_HELPER_OT_material_assign_masked(md.MeshDataOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.material_assign_masked"
    bl_label = "Assign to Masked"
    bl_description = "Give the masked faces the active material slot"

    threshold: bpy.props.FloatProperty(name="Threshold", default=0.5, min=0.0, max=1.0)

    @classmethod
    def poll(cls, context):
        return super().poll(context) and len(context.active_object.material_slots) > 0

    def execute(self, context):
        index = context.active_object.active_material_index
        with md.object_mode(context) as mesh:
            fmask, *_ = face_mask(mesh)
            mat = np.empty(len(mesh.polygons), dtype=np.int32)
            mesh.polygons.foreach_get("material_index", mat)
            chosen = fmask >= self.threshold
            mat[chosen] = index
            mesh.polygons.foreach_set("material_index", mat)
            mesh.update()
        self.report({'INFO'}, f"{int(chosen.sum())} faces assigned")
        return {'FINISHED'}


class SCULPT_HELPER_OT_material_mask(md.MeshDataOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.material_mask"
    bl_label = "Mask by Material"
    bl_description = "Mask the faces that use the active material slot"

    def execute(self, context):
        index = context.active_object.active_material_index
        with md.object_mode(context) as mesh:
            _fm, loop_vert, starts, counts = face_mask(mesh)
            mat = np.empty(len(mesh.polygons), dtype=np.int32)
            mesh.polygons.foreach_get("material_index", mat)
            loop_face_mat = np.repeat(mat, counts)
            mask = np.zeros(len(mesh.vertices), dtype=np.float32)
            mask[loop_vert[loop_face_mat == index]] = 1.0
            md.set_mask(mesh, mask)
        return {'FINISHED'}


def draw_material_slots(layout, context):
    obj = context.active_object
    row = layout.row()
    row.template_list("MATERIAL_UL_matslots", "", obj, "material_slots", obj,
                      "active_material_index", rows=3)
    col = row.column(align=True)
    col.operator("object.material_slot_add", icon='ADD', text="")
    col.operator("object.material_slot_remove", icon='REMOVE', text="")
    if obj.active_material_index < len(obj.material_slots):
        layout.template_ID(obj, "active_material", new="material.new")
    row = layout.row(align=True)
    row.operator("sculpt_helper.material_assign_masked", text="Assign to Masked")
    row.operator("sculpt_helper.material_mask", text="Mask by Material")


classes = (SCULPT_HELPER_OT_material_assign_masked, SCULPT_HELPER_OT_material_mask)

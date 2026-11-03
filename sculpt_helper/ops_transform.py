# SPDX-License-Identifier: GPL-3.0-or-later
"""Move, rotate and scale the unmasked part with a gizmo.

Mask what should stay put, press Gizmo (G in the Deform panel), and drag the
combined translate / rotate / scale gizmo. The pivot starts at the centre of
the unmasked part; Mask Border puts it on the joint between the two, and
Under Cursor on the surface you point at (with Alt+click while the gizmo is
active, like Blender's own transform tools).
"""

import bpy

from . import utils


class SCULPT_HELPER_OT_gizmo_transform(bpy.types.Operator):
    bl_idname = "sculpt_helper.gizmo_transform"
    bl_label = "Gizmo: Move Unmasked"
    bl_description = ("Move, rotate and scale the unmasked part with a gizmo; "
                      "masked areas stay where they are")
    bl_options = {'REGISTER', 'UNDO'}

    pivot: bpy.props.EnumProperty(name="Pivot", items=(
        ('UNMASKED', "Centre", "Centre of the unmasked part"),
        ('BORDER', "Mask Border", "Centre of the mask border (good for joints)"),
        ('ORIGIN', "Origin", "Object origin"),
    ))

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context)

    def execute(self, context):
        context.tool_settings.sculpt.transform_mode = 'ALL_VERTICES'
        bpy.ops.sculpt.set_pivot_position(mode=self.pivot)
        bpy.ops.wm.tool_set_by_id(name="builtin.transform", space_type='VIEW_3D')
        context.space_data.show_gizmo = True
        return {'FINISHED'}


class SCULPT_HELPER_OT_gizmo_done(bpy.types.Operator):
    bl_idname = "sculpt_helper.gizmo_done"
    bl_label = "Back to Brush"
    bl_description = "Leave the gizmo and return to the brush"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context)

    def execute(self, context):
        bpy.ops.wm.tool_set_by_id(name="builtin.brush", space_type='VIEW_3D')
        return {'FINISHED'}


def draw_gizmo(layout, context):
    col = layout.column(align=True)
    col.operator("sculpt_helper.gizmo_transform", text="Gizmo: Move Unmasked",
                 icon='OBJECT_ORIGIN').pivot = 'UNMASKED'
    row = col.row(align=True)
    row.operator("sculpt_helper.gizmo_transform", text="Pivot on Mask Border").pivot = 'BORDER'
    row.operator("sculpt_helper.gizmo_transform", text="Pivot on Origin").pivot = 'ORIGIN'
    col.operator("sculpt_helper.gizmo_done", icon='BRUSH_DATA')


classes = (SCULPT_HELPER_OT_gizmo_transform, SCULPT_HELPER_OT_gizmo_done)

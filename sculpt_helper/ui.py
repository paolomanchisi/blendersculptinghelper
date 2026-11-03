# SPDX-License-Identifier: GPL-3.0-or-later
"""Shortcut list popup and the sidebar Mask / Hide panel."""

import bpy

from . import keymap, utils


class SCULPT_HELPER_OT_shortcut_list(bpy.types.Operator):
    bl_idname = "sculpt_helper.shortcut_list"
    bl_label = "Sculpt Helper Shortcuts"
    bl_description = "List the Sculpt Helper shortcuts"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=360)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Sculpt Helper shortcuts", icon='KEYINGSET')
        col = layout.column(align=True)
        for label, _km, kmi in keymap.find_user_items():
            row = col.row()
            row.active = kmi.active
            row.label(text=label)
            row.label(text=kmi.to_string() or "(unbound)")
        layout.separator()
        layout.label(text="Change them in Preferences > Add-ons > Sculpt Helper.")
        layout.operator("preferences.addon_show", text="Open Preferences",
                        icon='PREFERENCES').module = __package__


class SCULPT_HELPER_PT_mask_hide(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sculpt Helper"
    bl_label = "Mask / Hide"

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context)

    def draw_header_preset(self, context):
        self.layout.operator("sculpt_helper.shortcut_list", text="", icon='QUESTION',
                             emboss=False)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Mask")
        row = col.row(align=True)
        row.operator("paint.mask_flood_fill", text="Invert").mode = 'INVERT'
        op = row.operator("paint.mask_flood_fill", text="Clear")
        op.mode, op.value = 'VALUE', 0.0
        row = col.row(align=True)
        op = row.operator("sculpt.mask_filter", text="Blur")
        op.filter_type, op.auto_iteration_count = 'SMOOTH', True
        op = row.operator("sculpt.mask_filter", text="Sharpen")
        op.filter_type, op.auto_iteration_count = 'SHARPEN', True
        row = col.row(align=True)
        op = row.operator("sculpt.mask_filter", text="Grow")
        op.filter_type, op.auto_iteration_count = 'GROW', True
        op = row.operator("sculpt.mask_filter", text="Shrink")
        op.filter_type, op.auto_iteration_count = 'SHRINK', True

        col = layout.column(align=True)
        col.label(text="Hide / Show")
        row = col.row(align=True)
        row.operator("paint.hide_show_all", text="Show All").action = 'SHOW'
        row.operator("paint.visibility_invert", text="Invert")
        row = col.row(align=True)
        row.operator("paint.hide_show_masked", text="Hide Masked").action = 'HIDE'
        row.operator("paint.hide_show_masked", text="Show Masked").action = 'SHOW'
        row = col.row(align=True)
        op = row.operator("paint.visibility_filter", text="Grow")
        op.action, op.auto_iteration_count = 'GROW', True
        op = row.operator("paint.visibility_filter", text="Shrink")
        op.action, op.auto_iteration_count = 'SHRINK', True

        prefs = utils.addon_prefs(context)
        if prefs:
            col = layout.column(align=True)
            col.label(text="Hold Isolate")
            col.prop(prefs, "isolate_method", text="")
            col.prop(prefs, "front_faces_only")


classes = (SCULPT_HELPER_OT_shortcut_list, SCULPT_HELPER_PT_mask_hide)

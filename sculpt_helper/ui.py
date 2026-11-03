# SPDX-License-Identifier: GPL-3.0-or-later
"""Shortcut list popup (F1)."""

import bpy

from . import keymap


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


classes = (SCULPT_HELPER_OT_shortcut_list,)

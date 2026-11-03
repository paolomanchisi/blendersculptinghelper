# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import rna_keymap_ui
from bpy.props import BoolProperty, EnumProperty

from . import keymap


class SCULPT_HELPER_AP_preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    isolate_method: EnumProperty(
        name="Isolate Shape",
        description="Default shape used by the hold-isolate key (Tab cycles while held)",
        items=(
            ('BOX', "Box", "Drag a rectangle"),
            ('LASSO', "Lasso", "Draw a free shape"),
            ('LINE', "Line", "Hide everything on one side of a line"),
        ),
        default='BOX',
    )
    front_faces_only: BoolProperty(
        name="Front Faces Only",
        description="Isolate gestures affect only faces pointing toward the view",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "isolate_method")
        col.prop(self, "front_faces_only")

        layout.separator()
        layout.label(text="Shortcuts (Sculpt Mode)")
        clashes = keymap.conflicts()
        box = layout.box()
        found = False
        for label, km, kmi in keymap.find_user_items():
            found = True
            box.label(text=label)
            rna_keymap_ui.draw_kmi([], context.window_manager.keyconfigs.user,
                                   km, kmi, box, 0)
            if kmi.idname in clashes:
                row = box.row()
                row.alert = True
                row.label(text="Takes priority over: " + ", ".join(clashes[kmi.idname]),
                          icon='ERROR')
        if not found:
            box.label(text="Keymap not loaded yet; reopen Preferences.", icon='INFO')


classes = (SCULPT_HELPER_AP_preferences,)

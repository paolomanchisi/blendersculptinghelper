# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import rna_keymap_ui
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import keymap, panels

DEFAULT_BRUSHES = ("Draw, Clay Strips, Grab, Pinch/Magnify, Smooth, Snake Hook, "
                   "Inflate/Deflate, Crease Polish, Flatten/Contrast, Layer")


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

    brush_favorites: StringProperty(
        name="Pie Brushes",
        description=("Essentials brush names for the Q pie, separated by commas. "
                     "The first seven get their own slot, the rest are listed at the bottom"),
        default=DEFAULT_BRUSHES,
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "isolate_method")
        col.prop(self, "front_faces_only")
        col.prop(self, "brush_favorites")

        layout.separator()
        layout.label(text="Sidebar panels")
        grid = layout.grid_flow(columns=3, align=True, even_columns=True)
        for pid, label in panels.PANELS:
            grid.prop(self, "show_" + pid.lower(), text=label, toggle=True)

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
            kid = keymap.key_id(kmi)
            if kid in clashes:
                row = box.row()
                row.alert = True
                row.label(text="Takes priority over: " + ", ".join(clashes[kid]),
                          icon='ERROR')
        if not found:
            box.label(text="Keymap not loaded yet; reopen Preferences.", icon='INFO')


for _pid, _label in panels.PANELS:
    SCULPT_HELPER_AP_preferences.__annotations__["show_" + _pid.lower()] = BoolProperty(
        name=_label, description=f"Show the {_label} panel in the sidebar", default=True)


classes = (SCULPT_HELPER_AP_preferences,)

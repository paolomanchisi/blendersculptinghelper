# SPDX-License-Identifier: GPL-3.0-or-later
"""Pie menus (Q, A, Shift+W, Alt+W) and popups (Z, S)."""

import bpy

from . import panels, utils

# Pie slot order: left, right, bottom, top, top-left, top-right, bottom-left, bottom-right.
PIE_SLOTS = 8


def _brush_button(layout, name):
    op = layout.operator("brush.asset_activate", text=name.split("/")[0])
    op.asset_library_type = 'ESSENTIALS'
    op.relative_asset_identifier = utils.ESSENTIALS_SCULPT + name


def brush_favorites(context):
    prefs = utils.addon_prefs(context)
    text = prefs.brush_favorites if prefs else ""
    return [n.strip() for n in text.split(",") if n.strip()]


class SCULPT_HELPER_MT_brush_pie(bpy.types.Menu):
    bl_idname = "SCULPT_HELPER_MT_brush_pie"
    bl_label = "Brushes"

    def draw(self, context):
        pie = self.layout.menu_pie()
        names = brush_favorites(context)
        # Seven slots hold favourites; the bottom slot lists the rest and the
        # full brush browser, so any number of brushes fits.
        direct, extra = names[:PIE_SLOTS - 1], names[PIE_SLOTS - 1:]
        slots = [None] * PIE_SLOTS
        free = [i for i in range(PIE_SLOTS) if i != 2]
        for i, name in zip(free, direct):
            slots[i] = name
        for i in range(PIE_SLOTS):
            if i == 2:
                col = pie.column(align=True)
                col.operator("wm.call_asset_shelf_popover", text="All Brushes…",
                             icon='BRUSHES_ALL').name = "VIEW3D_AST_brush_sculpt"
                for name in extra:
                    _brush_button(col, name)
            elif slots[i]:
                _brush_button(pie, slots[i])
            else:
                pie.separator()


class SCULPT_HELPER_MT_mask_pie(bpy.types.Menu):
    bl_idname = "SCULPT_HELPER_MT_mask_pie"
    bl_label = "Mask"

    def draw(self, context):
        pie = self.layout.menu_pie()
        pie.operator("paint.mask_flood_fill", text="Invert", icon='SELECT_SUBTRACT').mode = 'INVERT'
        op = pie.operator("paint.mask_flood_fill", text="Clear", icon='X')
        op.mode, op.value = 'VALUE', 0.0
        for ftype, text in (('SHARPEN', "Sharpen"), ('SMOOTH', "Blur"),
                            ('GROW', "Grow"), ('SHRINK', "Shrink"),
                            ('CONTRAST_INCREASE', "More Contrast")):
            op = pie.operator("sculpt.mask_filter", text=text)
            op.filter_type, op.auto_iteration_count = ftype, True
        col = pie.column(align=True)
        op = col.operator("paint.mask_flood_fill", text="Fill")
        op.mode, op.value = 'VALUE', 1.0
        col.operator("sculpt.mask_from_cavity", text="From Cavity")
        col.operator("sculpt.mask_init", text="Random per Face Set").mode = 'RANDOM_PER_FACE_SET'
        col.operator("wm.tool_set_by_id", text="Lasso Mask Tool").name = "builtin.lasso_mask"
        col.operator("sculpt_helper.gizmo_transform", text="Gizmo: Move Unmasked",
                     icon='OBJECT_ORIGIN').pivot = 'UNMASKED'


class SCULPT_HELPER_MT_hide_pie(bpy.types.Menu):
    bl_idname = "SCULPT_HELPER_MT_hide_pie"
    bl_label = "Hide / Show"

    def draw(self, context):
        pie = self.layout.menu_pie()
        pie.operator("paint.hide_show_masked", text="Hide Masked").action = 'HIDE'
        pie.operator("paint.hide_show_masked", text="Show Masked").action = 'SHOW'
        pie.operator("paint.hide_show_all", text="Show All", icon='HIDE_OFF').action = 'SHOW'
        pie.operator("paint.visibility_invert", text="Invert Visible", icon='ARROW_LEFTRIGHT')
        op = pie.operator("paint.visibility_filter", text="Shrink Visible")
        op.action, op.auto_iteration_count = 'SHRINK', True
        op = pie.operator("paint.visibility_filter", text="Grow Visible")
        op.action, op.auto_iteration_count = 'GROW', True
        pie.operator("wm.tool_set_by_id", text="Box Hide Tool").name = "builtin.box_hide"
        pie.operator("wm.tool_set_by_id", text="Lasso Hide Tool").name = "builtin.lasso_hide"


class SCULPT_HELPER_MT_face_sets_pie(bpy.types.Menu):
    bl_idname = "SCULPT_HELPER_MT_face_sets_pie"
    bl_label = "Face Sets"

    def draw(self, context):
        pie = self.layout.menu_pie()
        pie.operator("sculpt.face_sets_create", text="From Mask").mode = 'MASKED'
        pie.operator("sculpt.face_sets_create", text="From Visible").mode = 'VISIBLE'
        pie.operator("paint.hide_show_all", text="Show All", icon='HIDE_OFF').action = 'SHOW'
        pie.operator("sculpt.face_sets_randomize_colors", text="New Colors", icon='COLOR')
        pie.operator("sculpt.face_sets_init", text="By Loose Parts").mode = 'LOOSE_PARTS'
        pie.operator("sculpt.face_sets_init", text="By Normals").mode = 'NORMALS'
        op = pie.operator("brush.asset_activate", text="Draw Face Sets", icon='BRUSH_DATA')
        op.asset_library_type = 'ESSENTIALS'
        op.relative_asset_identifier = utils.ESSENTIALS_SCULPT + "Face Set Paint"
        pie.menu("VIEW3D_MT_face_sets_init", text="More Auto Create…")


class SCULPT_HELPER_PT_view_popup(bpy.types.Panel):
    """Z popup: mirror, display, Dyntopo and Multires in one place."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_label = "View / Mode"
    bl_ui_units_x = 13

    def draw(self, context):
        layout = self.layout
        if not utils.in_sculpt_mode(context):
            layout.label(text="Sculpt Mode only")
            return
        panels.draw_view_mode(layout, context)
        layout.separator()
        layout.label(text="Multires")
        panels.draw_multires(layout, context)


class SCULPT_HELPER_PT_panel_toggles(bpy.types.Panel):
    """S popup: choose which sidebar panels are shown."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_label = "Sculpt Helper Panels"
    bl_ui_units_x = 9

    def draw(self, context):
        layout = self.layout
        prefs = utils.addon_prefs(context)
        layout.label(text="Show panels (N sidebar)")
        if prefs is None:
            return
        col = layout.column(align=True)
        for pid, label in panels.PANELS:
            col.prop(prefs, "show_" + pid.lower(), text=label, toggle=True)
        row = layout.row(align=True)
        row.operator("sculpt_helper.panels_all", text="All").show = True
        row.operator("sculpt_helper.panels_all", text="None").show = False
        layout.operator("wm.context_toggle", text="Toggle Sidebar",
                        icon='MENU_PANEL').data_path = "space_data.show_region_ui"


class SCULPT_HELPER_OT_panels_all(bpy.types.Operator):
    bl_idname = "sculpt_helper.panels_all"
    bl_label = "Show / Hide All Panels"
    bl_description = "Show or hide every Sculpt Helper panel"

    show: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        prefs = utils.addon_prefs(context)
        for pid, _label in panels.PANELS:
            setattr(prefs, "show_" + pid.lower(), self.show)
        if self.show:
            context.space_data.show_region_ui = True
        return {'FINISHED'}


classes = (
    SCULPT_HELPER_MT_brush_pie,
    SCULPT_HELPER_MT_mask_pie,
    SCULPT_HELPER_MT_hide_pie,
    SCULPT_HELPER_MT_face_sets_pie,
    SCULPT_HELPER_PT_view_popup,
    SCULPT_HELPER_PT_panel_toggles,
    SCULPT_HELPER_OT_panels_all,
)

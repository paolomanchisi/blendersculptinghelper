# SPDX-License-Identifier: GPL-3.0-or-later
"""Sidebar panels (N > Sculpt Helper). Each can be hidden with the S popup."""

import bpy
from bl_ui.properties_paint_common import BrushAssetShelf, UnifiedPaintPanel

from . import (ops_boolean, ops_gravity, ops_layers, ops_masks, ops_material, ops_multi,
               ops_pivot, ops_shape, ops_stamp, ops_transfer, ops_transform, utils)
from .help_text import HELP

CATEGORY = "Sculpt Helper"

# (id, label). The id names the preference toggle ("show_<id>") and help text.
PANELS = (
    ("BRUSH", "Brush"),
    ("MASK_HIDE", "Mask / Hide"),
    ("VIEW_MODE", "View / Mode"),
    ("DEFORM", "Deform"),
    ("FACE_SETS", "Face Sets"),
    ("VERTEX_COLOR", "Vertex Color"),
    ("MATERIAL", "Material"),
    ("MULTIRES", "Multires"),
    ("LAYERS", "Layers"),
    ("EXTRACT", "Extract"),
    ("REMESH", "Remesh"),
    ("BOOLEAN", "Boolean"),
)


def panel_visible(context, panel_id):
    prefs = utils.addon_prefs(context)
    return prefs is None or getattr(prefs, "show_" + panel_id.lower(), True)


# ---------------------------------------------------------------------------
# Operators used by the panels


class SCULPT_HELPER_OT_panel_help(bpy.types.Operator):
    bl_idname = "sculpt_helper.panel_help"
    bl_label = "How to Use"
    bl_description = "Explain how to use this panel"

    panel: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=380)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        label = dict(PANELS).get(self.panel, self.panel)
        col = self.layout.column(align=True)
        col.label(text=label, icon='QUESTION')
        col.separator()
        for line in HELP.get(self.panel, ()):
            col.label(text=line)


class SCULPT_HELPER_OT_thickness_protect(bpy.types.Operator):
    bl_idname = "sculpt_helper.thickness_protect"
    bl_label = "Thickness Protect"
    bl_description = ("Keep strokes from reaching through thin parts to the far side "
                      "(front faces only plus occlusion auto-masking)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        am = context.tool_settings.sculpt.mesh_automasking_settings
        on = not am.use_automasking_view_occlusion
        am.use_automasking_view_occlusion = on
        am.use_automasking_view_normal = on
        return {'FINISHED'}


class SCULPT_HELPER_OT_deform_filter(bpy.types.Operator):
    bl_idname = "sculpt_helper.deform_filter"
    bl_label = "Deform Filter"
    bl_description = "Apply a mesh filter to the visible, unmasked part"
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.StringProperty(default='SMOOTH')
    sign: bpy.props.FloatProperty(default=1.0)

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context)

    def execute(self, context):
        settings = context.scene.sculpt_helper
        bpy.ops.sculpt.mesh_filter(
            type=self.type,
            strength=self.sign * settings.deform_strength,
            iteration_count=settings.deform_iterations)
        return {'FINISHED'}


class SCULPT_HELPER_OT_color_fill(bpy.types.Operator):
    bl_idname = "sculpt_helper.color_fill"
    bl_label = "Fill Color"
    bl_description = "Fill the visible, unmasked part with the current colour"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context)

    def execute(self, context):
        paint = context.tool_settings.sculpt
        ups = paint.unified_paint_settings
        brush = paint.brush
        color = ups.color if (ups.use_unified_color or brush is None) else brush.color
        bpy.ops.sculpt.color_filter(type='FILL', fill_color=color[:3], strength=1.0)
        return {'FINISHED'}


def _multires(obj):
    return next((m for m in obj.modifiers if m.type == 'MULTIRES'), None)


class SCULPT_HELPER_OT_multires_subdivide(bpy.types.Operator):
    bl_idname = "sculpt_helper.multires_subdivide"
    bl_label = "Subdivide"
    bl_description = "Add a Multires level, adding the modifier first if needed"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(items=(
        ('CATMULL_CLARK', "Subdivide", "Smooth subdivision"),
        ('SIMPLE', "Simple", "Subdivide without smoothing"),
        ('LINEAR', "Linear", "Linear subdivision"),
    ))

    @classmethod
    def poll(cls, context):
        return utils.sculpting_mesh(context)

    def execute(self, context):
        obj = context.active_object
        mod = _multires(obj)
        if mod is None:
            if obj.use_dynamic_topology_sculpting:
                self.report({'WARNING'}, "Turn Dyntopo off before adding Multires")
                return {'CANCELLED'}
            mod = obj.modifiers.new("Multires", 'MULTIRES')
        bpy.ops.object.multires_subdivide(modifier=mod.name, mode=self.mode)
        return {'FINISHED'}


class SCULPT_HELPER_OT_multires_level(bpy.types.Operator):
    bl_idname = "sculpt_helper.multires_level"
    bl_label = "Change Level"
    bl_description = "Step the Multires sculpt level down or up"
    bl_options = {'REGISTER', 'UNDO'}

    delta: bpy.props.IntProperty(default=1)

    @classmethod
    def poll(cls, context):
        return utils.sculpting_mesh(context) and _multires(context.active_object) is not None

    def execute(self, context):
        mod = _multires(context.active_object)
        level = max(0, min(mod.total_levels, mod.sculpt_levels + self.delta))
        mod.sculpt_levels = level
        if context.scene.sculpt_helper.multires_link_levels:
            mod.levels = level
            mod.render_levels = level
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Shared draw functions (also used by the Z popup)


def draw_brush(layout, context):
    paint = context.tool_settings.sculpt
    brush = paint.brush
    row = layout.row(align=True)
    BrushAssetShelf.draw_popup_selector(row, context, brush)
    if brush is None:
        return
    col = layout.column(align=True)
    UnifiedPaintPanel.prop_unified(col, context, brush, "size", unified_name="use_unified_size",
                                   pressure_name="use_pressure_size", text="Radius", slider=True)
    UnifiedPaintPanel.prop_unified(col, context, brush, "strength",
                                   unified_name="use_unified_strength",
                                   pressure_name="use_pressure_strength", text="Strength",
                                   slider=True)
    row = layout.row(align=True)
    row.popover(panel="VIEW3D_PT_tools_brush_texture", text="Texture")
    row.popover(panel="VIEW3D_PT_tools_brush_stroke", text="Stroke")
    row.popover(panel="VIEW3D_PT_tools_brush_falloff", text="Falloff")

    am = paint.mesh_automasking_settings
    col = layout.column(align=True)
    col.label(text="Auto-Masking")
    grid = col.grid_flow(columns=3, align=True, even_columns=True)
    grid.prop(am, "use_automasking_view_normal", text="Front", toggle=True)
    grid.prop(am, "use_automasking_topology", text="Topology", toggle=True)
    grid.prop(am, "use_automasking_boundary_edges", text="Boundary", toggle=True)
    grid.prop(am, "use_automasking_face_sets", text="Face Set", toggle=True)
    grid.prop(am, "use_automasking_boundary_face_sets", text="FS Border", toggle=True)
    grid.prop(am, "use_automasking_cavity", text="Cavity", toggle=True)
    row = col.row(align=True)
    row.operator("sculpt_helper.thickness_protect", text="Thickness Protect",
                 depress=am.use_automasking_view_occlusion, icon='MOD_SOLIDIFY')

    _sub_panel(layout, context, "show_depth_limit", "Depth Limit", ops_shape.draw_depth_limit)
    _sub_panel(layout, context, "show_gravity", "Gravity", ops_gravity.draw_gravity)


def _sub_panel(layout, context, flag, label, draw):
    """Collapsible section (layout.panel) inside a sidebar panel."""
    header, body = layout.panel("sculpt_helper_" + flag, default_closed=True)
    header.label(text=label)
    if body:
        draw(body, context)


def draw_mask_hide(layout, context):
    col = layout.column(align=True)
    col.label(text="Mask")
    row = col.row(align=True)
    row.operator("paint.mask_flood_fill", text="Invert").mode = 'INVERT'
    op = row.operator("paint.mask_flood_fill", text="Clear")
    op.mode, op.value = 'VALUE', 0.0
    for a, b in (("SMOOTH", "SHARPEN"), ("GROW", "SHRINK")):
        row = col.row(align=True)
        for ftype in (a, b):
            op = row.operator("sculpt.mask_filter", text="Blur" if ftype == 'SMOOTH' else ftype.title())
            op.filter_type, op.auto_iteration_count = ftype, True

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

    _sub_panel(layout, context, "show_saved_masks", "Save / Load", ops_masks.draw_saved_masks)

    prefs = utils.addon_prefs(context)
    if prefs:
        col = layout.column(align=True)
        col.label(text="Hold Isolate (Shift+C)")
        col.row().prop(prefs, "isolate_method", expand=True)
        col.prop(prefs, "front_faces_only")


def draw_view_mode(layout, context):
    obj = context.active_object
    mesh = obj.data
    paint = context.tool_settings.sculpt

    col = layout.column(align=True)
    col.label(text="Mirror")
    row = col.row(align=True)
    row.prop(mesh, "use_mirror_x", text="X", toggle=True)
    row.prop(mesh, "use_mirror_y", text="Y", toggle=True)
    row.prop(mesh, "use_mirror_z", text="Z", toggle=True)
    row.popover(panel="VIEW3D_PT_sculpt_symmetry", text="", icon='DOWNARROW_HLT')
    row = col.row(align=True)
    row.prop(paint, "symmetrize_direction", text="")
    row.operator("sculpt.symmetrize", text="Symmetrize")

    overlay = context.space_data.overlay
    col = layout.column(align=True)
    col.label(text="Display")
    row = col.row(align=True)
    row.prop(overlay, "show_sculpt_mask", text="", icon='MOD_MASK')
    row.prop(overlay, "sculpt_mode_mask_opacity", text="Mask")
    row = col.row(align=True)
    row.prop(overlay, "show_sculpt_face_sets", text="", icon='FACE_MAPS')
    row.prop(overlay, "sculpt_mode_face_sets_opacity", text="Face Sets")
    col.prop(overlay, "show_wireframes", text="Wireframe", toggle=True)

    col = layout.column(align=True)
    col.label(text="Dyntopo")
    dyntopo = obj.use_dynamic_topology_sculpting
    has_multires = _multires(obj) is not None
    row = col.row(align=True)
    row.enabled = not has_multires
    row.operator("sculpt.dynamic_topology_toggle",
                 text="Dyntopo On" if dyntopo else "Dyntopo Off", depress=dyntopo)
    sub = col.column(align=True)
    sub.active = dyntopo
    sub.prop(paint, "detail_type_method", text="")
    if paint.detail_type_method in {'CONSTANT', 'MANUAL'}:
        sub.prop(paint, "constant_detail_resolution")
    elif paint.detail_type_method == 'BRUSH':
        sub.prop(paint, "detail_percent")
    else:
        sub.prop(paint, "detail_size")
    sub.prop(paint, "detail_refine_method", text="")
    sub.operator("sculpt.detail_flood_fill")
    if has_multires:
        col.label(text="Dyntopo is unavailable with Multires", icon='INFO')

    _sub_panel(layout, context, "show_multi", "Sculpt Together", ops_multi.draw_multi)


def draw_deform(layout, context):
    settings = context.scene.sculpt_helper
    col = layout.column(align=True)
    col.prop(settings, "deform_strength", slider=True)
    col.prop(settings, "deform_iterations")

    def pair(a, b):
        row = layout.row(align=True)
        for text, ftype, sign in (a, b):
            op = row.operator("sculpt_helper.deform_filter", text=text)
            op.type, op.sign = ftype, sign

    pair(("Smooth", 'SMOOTH', 1.0), ("Surface Smooth", 'SURFACE_SMOOTH', 1.0))
    pair(("Inflate", 'INFLATE', 1.0), ("Deflate", 'INFLATE', -1.0))
    pair(("Expand", 'SCALE', 1.0), ("Shrink", 'SCALE', -1.0))
    pair(("Sphere", 'SPHERE', 1.0), ("Random", 'RANDOM', 1.0))
    pair(("Sharpen", 'SHARPEN', 1.0), ("Enhance", 'ENHANCE_DETAILS', 1.0))
    pair(("Relax", 'RELAX', 1.0), ("Relax FS", 'RELAX_FACE_SETS', 1.0))

    _sub_panel(layout, context, "show_pivot", "Pivot Bend", ops_pivot.draw_pivot)
    _sub_panel(layout, context, "show_gizmo", "Gizmo", ops_transform.draw_gizmo)
    _sub_panel(layout, context, "show_morph", "Morph", ops_shape.draw_morph)
    _sub_panel(layout, context, "show_stamp", "Copy Stamp", ops_stamp.draw_stamp)


def draw_face_sets(layout, context):
    col = layout.column(align=True)
    col.label(text="Create")
    row = col.row(align=True)
    row.operator("sculpt.face_sets_create", text="From Mask").mode = 'MASKED'
    row.operator("sculpt.face_sets_create", text="From Visible").mode = 'VISIBLE'
    col.menu("VIEW3D_MT_face_sets_init", text="Auto Create")
    col = layout.column(align=True)
    row = col.row(align=True)
    row.operator("sculpt.face_sets_randomize_colors", text="New Colors")
    row.operator("paint.hide_show_all", text="Show All").action = 'SHOW'
    overlay = context.space_data.overlay
    row = col.row(align=True)
    row.prop(overlay, "show_sculpt_face_sets", text="", icon='HIDE_OFF')
    row.prop(overlay, "sculpt_mode_face_sets_opacity", text="Opacity")
    layout.operator("wm.tool_set_by_id", text="Edit Face Set Tool").name = "builtin.face_set_edit"


def draw_vertex_color(layout, context):
    paint = context.tool_settings.sculpt
    brush = paint.brush
    if brush is not None:
        UnifiedPaintPanel.prop_unified_color_picker(layout, context, brush, "color")
        row = layout.row(align=True)
        UnifiedPaintPanel.prop_unified_color(row, context, brush, "color", text="")
        UnifiedPaintPanel.prop_unified_color(row, context, brush, "secondary_color", text="")
    layout.template_ID(paint, "palette", new="palette.new")
    if paint.palette:
        layout.template_palette(paint, "palette")
    row = layout.row(align=True)
    op = row.operator("brush.asset_activate", text="Paint", icon='BRUSH_DATA')
    op.asset_library_type = 'ESSENTIALS'
    op.relative_asset_identifier = utils.ESSENTIALS_SCULPT + "Paint Hard"
    row.operator("sculpt_helper.color_fill", text="Fill", icon='SNAP_FACE')


def draw_material(layout, context):
    ops_material.draw_material_slots(layout, context)
    layout.separator()
    shading = context.space_data.shading
    row = layout.row(align=True)
    row.prop(shading, "light", expand=True)
    if shading.light in {'STUDIO', 'MATCAP'}:
        row = layout.row()
        row.template_icon_view(shading, "studio_light", scale_popup=3.0)
        if shading.light == 'MATCAP':
            row.operator("view3d.toggle_matcap_flip", text="", icon='ARROW_LEFTRIGHT')
    col = layout.column(align=True)
    col.prop(shading, "color_type", text="Color")
    if shading.color_type == 'SINGLE':
        col.prop(shading, "single_color", text="")
    layout.prop(shading, "show_cavity")


def draw_multires(layout, context):
    obj = context.active_object
    mod = _multires(obj)
    settings = context.scene.sculpt_helper
    row = layout.row(align=True)
    for mode, text in (('CATMULL_CLARK', "Subdivide"), ('SIMPLE', "Simple"), ('LINEAR', "Linear")):
        row.operator("sculpt_helper.multires_subdivide", text=text).mode = mode
    if mod is None:
        layout.label(text="No Multires yet: Subdivide adds one", icon='INFO')
        return
    row = layout.row(align=True)
    row.operator("sculpt_helper.multires_level", text="", icon='REMOVE').delta = -1
    row.label(text=f"Level {mod.sculpt_levels} / {mod.total_levels}")
    row.operator("sculpt_helper.multires_level", text="", icon='ADD').delta = 1
    layout.prop(settings, "multires_link_levels")
    col = layout.column(align=True)
    col.prop(mod, "levels", text="Viewport")
    col.prop(mod, "sculpt_levels", text="Sculpt")
    col.prop(mod, "render_levels", text="Render")
    row = layout.row(align=True)
    row.operator("object.multires_higher_levels_delete", text="Delete Higher").modifier = mod.name
    row.operator("object.multires_base_apply", text="Apply Base").modifier = mod.name


def draw_extract(layout, context):
    settings = context.scene.sculpt_helper
    col = layout.column(align=True)
    col.prop(settings, "extract_threshold", slider=True)
    col.prop(settings, "extract_smooth")
    col.prop(settings, "extract_thickness")
    op = layout.operator("sculpt.paint_mask_extract", text="Extract Mask")
    op.mask_threshold = settings.extract_threshold
    op.smooth_iterations = settings.extract_smooth
    op.add_solidify = settings.extract_thickness
    layout.prop(settings, "slice_new_object")
    op = layout.operator("sculpt.paint_mask_slice", text="Slice Mask")
    op.mask_threshold = settings.extract_threshold
    op.new_object = settings.slice_new_object
    op = layout.operator("sculpt.face_set_extract", text="Extract Face Set (click)")
    op.smooth_iterations = settings.extract_smooth
    op.add_solidify = settings.extract_thickness


def draw_remesh(layout, context):
    mesh = context.active_object.data
    col = layout.column(align=True)
    col.prop(mesh, "remesh_voxel_size")
    col.prop(mesh, "remesh_voxel_adaptivity")
    col = layout.column(align=True)
    col.prop(mesh, "use_remesh_fix_poles")
    col.prop(mesh, "use_remesh_preserve_volume", text="Preserve Volume")
    col.prop(mesh, "use_remesh_preserve_attributes", text="Preserve Attributes")
    row = layout.row(align=True)
    row.operator("object.voxel_size_edit", text="", icon='MOD_REMESH')
    row.operator("object.voxel_remesh", text="Voxel Remesh")
    layout.operator("object.quadriflow_remesh", text="QuadriFlow Remesh")
    _sub_panel(layout, context, "show_transfer", "Shape Transfer", ops_transfer.draw_transfer)


DRAW = {
    "BRUSH": draw_brush,
    "MASK_HIDE": draw_mask_hide,
    "VIEW_MODE": draw_view_mode,
    "DEFORM": draw_deform,
    "FACE_SETS": draw_face_sets,
    "VERTEX_COLOR": draw_vertex_color,
    "MATERIAL": draw_material,
    "MULTIRES": draw_multires,
    "LAYERS": ops_layers.draw_layers,
    "EXTRACT": draw_extract,
    "REMESH": draw_remesh,
    "BOOLEAN": ops_boolean.draw_boolean,
}


# ---------------------------------------------------------------------------
# Panel classes, generated from PANELS


class _SidebarPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    panel_id = ""

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context) and panel_visible(context, cls.panel_id)

    def draw_header_preset(self, context):
        self.layout.operator("sculpt_helper.panel_help", text="", icon='QUESTION',
                             emboss=False).panel = self.panel_id

    def draw(self, context):
        DRAW[self.panel_id](self.layout, context)


def _make_panel(panel_id, label):
    return type(
        f"SCULPT_HELPER_PT_{panel_id.lower()}",
        (_SidebarPanel, bpy.types.Panel),
        {"bl_label": label, "panel_id": panel_id},
    )


panel_classes = tuple(_make_panel(pid, label) for pid, label in PANELS)

classes = (
    SCULPT_HELPER_OT_panel_help,
    SCULPT_HELPER_OT_thickness_protect,
    SCULPT_HELPER_OT_deform_filter,
    SCULPT_HELPER_OT_color_fill,
    SCULPT_HELPER_OT_multires_subdivide,
    SCULPT_HELPER_OT_multires_level,
    *panel_classes,
)

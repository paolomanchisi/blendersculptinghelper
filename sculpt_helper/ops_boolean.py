# SPDX-License-Identifier: GPL-3.0-or-later
"""Boolean layers: stack cutters on the sculpt and keep them editable until
you confirm.

Each cutter is a separate wireframe object driving a Boolean modifier on the
sculpt, so you can change its operation, hide it, or move / scale it (Edit)
as often as you like. Confirm applies them all and removes the cutters;
Cancel removes them and leaves the sculpt as it was.
"""

import bmesh
import bpy

from . import utils

COLLECTION = "Sculpt Helper Cutters"
TARGET_PROP = "sculpt_helper_cutter_target"
MOD_PREFIX = "SH Boolean "


def cutter_mods(obj):
    return [m for m in obj.modifiers if m.type == 'BOOLEAN' and m.name.startswith(MOD_PREFIX)]


def _collection(context):
    coll = bpy.data.collections.get(COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION)
    if coll.name not in context.scene.collection.children:
        context.scene.collection.children.link(coll)
    return coll


def _cutter_mesh(shape):
    bm = bmesh.new()
    if shape == 'SPHERE':
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    elif shape == 'CYLINDER':
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=1.0, radius2=1.0, depth=2.0)
    else:
        bmesh.ops.create_cube(bm, size=2.0)
    mesh = bpy.data.meshes.new("Cutter")
    bm.to_mesh(mesh)
    bm.free()
    return mesh


class SCULPT_HELPER_OT_boolean_add(bpy.types.Operator):
    bl_idname = "sculpt_helper.boolean_add"
    bl_label = "Add Cutter"
    bl_description = "Add a cutter at the 3D cursor as a Boolean layer"
    bl_options = {'REGISTER', 'UNDO'}

    shape: bpy.props.EnumProperty(items=(
        ('SPHERE', "Sphere", ""), ('CUBE', "Cube", ""), ('CYLINDER', "Cylinder", "")))
    operation: bpy.props.EnumProperty(items=(
        ('DIFFERENCE', "Subtract", "Cut the cutter's shape away"),
        ('UNION', "Add", "Add the cutter's shape"),
        ('INTERSECT', "Intersect", "Keep only the overlap"),
    ))

    @classmethod
    def poll(cls, context):
        return utils.sculpting_mesh(context)

    def execute(self, context):
        target = context.active_object
        cutter = bpy.data.objects.new(f"Cutter {self.shape.title()}", _cutter_mesh(self.shape))
        _collection(context).objects.link(cutter)
        cutter.display_type = 'WIRE'
        cutter.hide_render = True
        cutter.location = context.scene.cursor.location
        size = max(target.dimensions) * 0.15 or 0.2
        cutter.scale = (size, size, size)
        cutter[TARGET_PROP] = target.name
        mod = target.modifiers.new(MOD_PREFIX + cutter.name, 'BOOLEAN')
        mod.object = cutter
        mod.operation = self.operation
        if 'MANIFOLD' in {i.identifier for i in mod.bl_rna.properties['solver'].enum_items}:
            mod.solver = 'MANIFOLD'
        return {'FINISHED'}


class SCULPT_HELPER_OT_boolean_edit(bpy.types.Operator):
    bl_idname = "sculpt_helper.boolean_edit"
    bl_label = "Edit Cutter"
    bl_description = "Select this cutter in Object Mode to move, rotate or scale it"
    bl_options = {'REGISTER', 'UNDO'}

    modifier: bpy.props.StringProperty()

    def execute(self, context):
        target = context.active_object
        mod = target.modifiers.get(self.modifier)
        if mod is None or mod.object is None:
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        mod.object.hide_set(False)
        mod.object.select_set(True)
        context.view_layer.objects.active = mod.object
        bpy.ops.wm.tool_set_by_id(name="builtin.transform", space_type='VIEW_3D')
        return {'FINISHED'}


class SCULPT_HELPER_OT_boolean_back(bpy.types.Operator):
    bl_idname = "sculpt_helper.boolean_back"
    bl_label = "Back to Sculpting"
    bl_description = "Return to Sculpt Mode on the object this cutter belongs to"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and TARGET_PROP in obj and obj[TARGET_PROP] in bpy.data.objects

    def execute(self, context):
        target = bpy.data.objects[context.active_object[TARGET_PROP]]
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        context.view_layer.objects.active = target
        bpy.ops.object.mode_set(mode='SCULPT')
        return {'FINISHED'}


def _finish(context, target, apply):
    was_sculpt = context.mode == 'SCULPT'
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    count = 0
    for mod in cutter_mods(target):
        cutter = mod.object
        if apply and mod.show_viewport:
            with context.temp_override(object=target, active_object=target):
                bpy.ops.object.modifier_apply(modifier=mod.name)
            count += 1
        else:
            target.modifiers.remove(mod)
        if cutter is not None:
            mesh = cutter.data
            bpy.data.objects.remove(cutter)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
    coll = bpy.data.collections.get(COLLECTION)
    if coll is not None and not coll.objects:
        bpy.data.collections.remove(coll)
    context.view_layer.objects.active = target
    target.select_set(True)
    if was_sculpt:
        bpy.ops.object.mode_set(mode='SCULPT')
    return count


class SCULPT_HELPER_OT_boolean_confirm(bpy.types.Operator):
    bl_idname = "sculpt_helper.boolean_confirm"
    bl_label = "Confirm Booleans"
    bl_description = "Apply every visible cutter to the mesh and remove the cutters"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and bool(cutter_mods(obj))

    def execute(self, context):
        count = _finish(context, context.active_object, apply=True)
        self.report({'INFO'}, f"Applied {count} cutter(s)")
        return {'FINISHED'}


class SCULPT_HELPER_OT_boolean_cancel(bpy.types.Operator):
    bl_idname = "sculpt_helper.boolean_cancel"
    bl_label = "Cancel Booleans"
    bl_description = "Remove every cutter without changing the mesh"
    bl_options = {'REGISTER', 'UNDO'}

    poll = SCULPT_HELPER_OT_boolean_confirm.poll

    def execute(self, context):
        _finish(context, context.active_object, apply=False)
        return {'FINISHED'}


class SCULPT_HELPER_OT_boolean_remove(bpy.types.Operator):
    bl_idname = "sculpt_helper.boolean_remove"
    bl_label = "Remove Cutter"
    bl_description = "Remove this cutter"
    bl_options = {'REGISTER', 'UNDO'}

    modifier: bpy.props.StringProperty()

    def execute(self, context):
        target = context.active_object
        mod = target.modifiers.get(self.modifier)
        if mod is None:
            return {'CANCELLED'}
        cutter = mod.object
        target.modifiers.remove(mod)
        if cutter is not None:
            bpy.data.objects.remove(cutter)
        return {'FINISHED'}


def draw_boolean(layout, context):
    obj = context.active_object
    col = layout.column(align=True)
    row = col.row(align=True)
    for shape, icon in (('SPHERE', 'MESH_UVSPHERE'), ('CUBE', 'MESH_CUBE'),
                        ('CYLINDER', 'MESH_CYLINDER')):
        op = row.operator("sculpt_helper.boolean_add", text="", icon=icon)
        op.shape, op.operation = shape, 'DIFFERENCE'
    row.label(text="Add cutter at 3D cursor")
    mods = cutter_mods(obj)
    if not mods:
        col.label(text="No cutters yet")
        return
    box = layout.box()
    for mod in mods:
        row = box.row(align=True)
        row.prop(mod, "show_viewport", text="", emboss=False)
        row.label(text=mod.object.name if mod.object else "(missing)")
        row.prop(mod, "operation", text="")
        row.operator("sculpt_helper.boolean_edit", text="", icon='OBJECT_ORIGIN').modifier = mod.name
        row.operator("sculpt_helper.boolean_remove", text="", icon='X').modifier = mod.name
    row = layout.row(align=True)
    row.operator("sculpt_helper.boolean_confirm", text="Confirm", icon='CHECKMARK')
    row.operator("sculpt_helper.boolean_cancel", text="Cancel", icon='CANCEL')


class SCULPT_HELPER_PT_cutter(bpy.types.Panel):
    """Shown in Object Mode while a cutter is selected for editing."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sculpt Helper"
    bl_label = "Boolean Cutter"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return context.mode == 'OBJECT' and obj is not None and TARGET_PROP in obj

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Move, rotate or scale the cutter,")
        col.label(text="then go back to sculpting.")
        col.operator("sculpt_helper.boolean_back", icon='SCULPTMODE_HLT')


classes = (
    SCULPT_HELPER_OT_boolean_add,
    SCULPT_HELPER_OT_boolean_edit,
    SCULPT_HELPER_OT_boolean_back,
    SCULPT_HELPER_OT_boolean_confirm,
    SCULPT_HELPER_OT_boolean_cancel,
    SCULPT_HELPER_OT_boolean_remove,
    SCULPT_HELPER_PT_cutter,
)

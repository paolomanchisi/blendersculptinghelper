# SPDX-License-Identifier: GPL-3.0-or-later
"""Sculpt several objects together.

Blender sculpts one object at a time. "Combine" joins copies of the selected
meshes into one temporary object (one face set per source object) and hides
the originals. "Split Back" writes each part back into its original object,
keeping its name, transform, modifiers and materials, and removes the
temporary object.
"""

import bmesh
import bpy
import numpy as np

from . import meshdata as md

SOURCE_ATTR = "sh_source_object"
SOURCES_PROP = "sculpt_helper_sources"


def combined_object(context):
    obj = context.active_object
    return obj if obj is not None and SOURCES_PROP in obj else None


class SCULPT_HELPER_OT_multi_combine(bpy.types.Operator):
    bl_idname = "sculpt_helper.multi_combine"
    bl_label = "Combine for Sculpting"
    bl_description = ("Sculpt the selected meshes together: join copies into one object "
                      "and hide the originals until you split back")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if len(meshes) < 2:
            cls.poll_message_set("Select two or more mesh objects")
            return False
        if any(o.data.shape_keys for o in meshes):
            cls.poll_message_set("Objects with shape keys can't be combined")
            return False
        return context.active_object is not None and combined_object(context) is None

    def execute(self, context):
        start_mode = context.mode
        if start_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        sources = [o for o in context.selected_objects if o.type == 'MESH']
        active = context.active_object if context.active_object in sources else sources[0]
        sources.remove(active)
        sources.insert(0, active)

        copies = []
        for i, src in enumerate(sources):
            dup = src.copy()
            dup.data = src.data.copy()
            dup.modifiers.clear()
            dup.parent = None
            dup.matrix_world = src.matrix_world.copy()
            context.scene.collection.objects.link(dup)
            mesh = dup.data
            attr = mesh.attributes.new(SOURCE_ATTR, 'INT', 'FACE')
            attr.data.foreach_set("value", np.full(len(mesh.polygons), i, dtype=np.int32))
            fs = mesh.attributes.get(md.FACE_SET_ATTR) or mesh.attributes.new(
                md.FACE_SET_ATTR, 'INT', 'FACE')
            fs.data.foreach_set("value", np.full(len(mesh.polygons), i + 1, dtype=np.int32))
            copies.append(dup)

        bpy.ops.object.select_all(action='DESELECT')
        with context.temp_override(active_object=copies[0], selected_editable_objects=copies,
                                   selected_objects=copies):
            bpy.ops.object.join()
        combined = copies[0]
        combined.name = "Combined Sculpt"
        combined[SOURCES_PROP] = [s.name for s in sources]
        for src in sources:
            src.hide_set(True)
        context.view_layer.objects.active = combined
        combined.select_set(True)
        bpy.ops.object.mode_set(mode='SCULPT')
        self.report({'INFO'}, f"Combined {len(sources)} objects; use Split Back when done")
        return {'FINISHED'}


class SCULPT_HELPER_OT_multi_split(bpy.types.Operator):
    bl_idname = "sculpt_helper.multi_split"
    bl_label = "Split Back"
    bl_description = "Write the combined sculpt back into the original objects"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return combined_object(context) is not None

    def execute(self, context):
        combined = combined_object(context)
        was_sculpt = context.mode == 'SCULPT'
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        names = list(combined[SOURCES_PROP])
        mesh = combined.data
        if SOURCE_ATTR not in mesh.attributes:
            self.report({'ERROR'}, "The combined object lost its source data (remeshed?)")
            return {'CANCELLED'}

        restored = []
        for i, name in enumerate(names):
            target = bpy.data.objects.get(name)
            if target is None:
                continue
            bm = bmesh.new()
            bm.from_mesh(mesh)
            layer = bm.faces.layers.int.get(SOURCE_ATTR)
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer] != i], context='FACES')
            loose = [v for v in bm.verts if not v.link_faces]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context='VERTS')
            to_local = target.matrix_world.inverted() @ combined.matrix_world
            bm.transform(to_local)
            bm.faces.layers.int.remove(layer)
            new_mesh = bpy.data.meshes.new(target.data.name)
            bm.to_mesh(new_mesh)
            bm.free()
            remap_materials(new_mesh, mesh.materials, target.data.materials)
            old = target.data
            target.data = new_mesh
            if old.users == 0:
                bpy.data.meshes.remove(old)
            target.hide_set(False)
            restored.append(target)

        bpy.data.objects.remove(combined)
        if old_mesh_unused(mesh):
            bpy.data.meshes.remove(mesh)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in restored:
            obj.select_set(True)
        if restored:
            context.view_layer.objects.active = restored[0]
            if was_sculpt:
                bpy.ops.object.mode_set(mode='SCULPT')
        self.report({'INFO'}, f"Split back into {len(restored)} objects")
        return {'FINISHED'}


def old_mesh_unused(mesh):
    try:
        return mesh.users == 0
    except ReferenceError:
        return False


def remap_materials(new_mesh, combined_materials, original_materials):
    """Keep the original object's material order: map each combined slot to
    the original's slot holding the same material, appending if missing."""
    order = list(original_materials)
    mapping = {}
    for ci, mat in enumerate(combined_materials):
        if mat in order:
            mapping[ci] = order.index(mat)
        else:
            order.append(mat)
            mapping[ci] = len(order) - 1
    new_mesh.materials.clear()
    for mat in order:
        new_mesh.materials.append(mat)
    if not mapping or len(new_mesh.polygons) == 0:
        return
    idx = np.empty(len(new_mesh.polygons), dtype=np.int32)
    new_mesh.polygons.foreach_get("material_index", idx)
    lut = np.array([mapping.get(i, 0) for i in range(max(mapping) + 1)], dtype=np.int32)
    new_mesh.polygons.foreach_set("material_index", lut[np.clip(idx, 0, len(lut) - 1)])


def draw_multi(layout, context):
    col = layout.column(align=True)
    if combined_object(context):
        col.label(text="Sculpting " + ", ".join(context.active_object[SOURCES_PROP]))
        col.operator("sculpt_helper.multi_split", icon='MOD_EXPLODE')
    else:
        col.operator("sculpt_helper.multi_combine", icon='OBJECT_DATA')
        col.label(text="Select 2+ meshes first")


class SCULPT_HELPER_PT_sculpt_together(bpy.types.Panel):
    """Object Mode entry point, where selecting several objects is easiest."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sculpt Helper"
    bl_label = "Sculpt Together"

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def draw(self, context):
        draw_multi(self.layout, context)


classes = (SCULPT_HELPER_OT_multi_combine, SCULPT_HELPER_OT_multi_split,
           SCULPT_HELPER_PT_sculpt_together)

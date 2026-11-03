# SPDX-License-Identifier: GPL-3.0-or-later
"""Shape transfer: put back detail that a remesh smoothed away.

"Remesh (Keep Detail)" remembers the surface, runs Voxel Remesh, then pulls
every new vertex onto the closest point of the old surface. "Transfer Shape
From" does the same projection onto another object, so you can also restore
detail from a backup copy.
"""

import bmesh
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

from . import meshdata as md
from . import utils


def project(positions, tree, strength, weight, to_source=None, from_source=None):
    """Move positions toward the closest point on ``tree`` (all in one space,
    or converted with the optional 4x4 matrices)."""
    out = positions.copy()
    for i, p in enumerate(positions):
        if weight[i] <= 0.0:
            continue
        q = p if to_source is None else to_source @ np.append(p, 1.0)
        hit = tree.find_nearest(tuple(q[:3]))
        if hit[0] is None:
            continue
        target = np.array(hit[0])
        if from_source is not None:
            target = (from_source @ np.append(target, 1.0))[:3]
        out[i] = p + (target - p) * (strength * weight[i])
    return out


def tree_from_mesh(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


class SCULPT_HELPER_OT_remesh_keep_detail(bpy.types.Operator):
    bl_idname = "sculpt_helper.remesh_keep_detail"
    bl_label = "Remesh (Keep Detail)"
    bl_description = "Voxel remesh, then project the new mesh back onto the old surface"
    bl_options = {'REGISTER', 'UNDO'}

    strength: bpy.props.FloatProperty(name="Strength", default=1.0, min=0.0, max=1.0)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return utils.sculpting_mesh(context) and md.unsupported_reason(obj) is None

    def execute(self, context):
        with md.object_mode(context) as mesh:
            tree = tree_from_mesh(mesh)
        bpy.ops.object.voxel_remesh()
        with md.object_mode(context) as mesh:
            pos = md.get_positions(mesh)
            out = project(pos, tree, self.strength, np.ones(len(pos), dtype=np.float32))
            md.set_positions(mesh, out)
        return {'FINISHED'}


class SCULPT_HELPER_OT_transfer_shape(bpy.types.Operator):
    bl_idname = "sculpt_helper.transfer_shape"
    bl_label = "Transfer Shape From"
    bl_description = "Pull the visible, unmasked surface onto the chosen object's surface"
    bl_options = {'REGISTER', 'UNDO'}

    strength: bpy.props.FloatProperty(name="Strength", default=1.0, min=0.0, max=1.0)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        src = context.scene.sculpt_helper.transfer_source
        return (utils.sculpting_mesh(context) and md.unsupported_reason(obj) is None
                and src is not None and src != obj and src.type == 'MESH')

    def execute(self, context):
        obj = context.active_object
        src = context.scene.sculpt_helper.transfer_source
        depsgraph = context.evaluated_depsgraph_get()
        src_eval = src.evaluated_get(depsgraph)
        tree = BVHTree.FromObject(src_eval, depsgraph)
        to_src = np.array(src.matrix_world.inverted() @ obj.matrix_world)
        from_src = np.array(obj.matrix_world.inverted() @ src.matrix_world)
        with md.object_mode(context) as mesh:
            pos = md.get_positions(mesh)
            out = project(pos, tree, self.strength, md.editable_weight(mesh), to_src, from_src)
            md.set_positions(mesh, out)
        return {'FINISHED'}


def draw_transfer(layout, context):
    settings = context.scene.sculpt_helper
    col = layout.column(align=True)
    col.operator("sculpt_helper.remesh_keep_detail", icon='MOD_REMESH')
    col.separator()
    col.prop(settings, "transfer_source", text="From")
    col.operator("sculpt_helper.transfer_shape", text="Transfer Shape", icon='MOD_SHRINKWRAP')


classes = (SCULPT_HELPER_OT_remesh_keep_detail, SCULPT_HELPER_OT_transfer_shape)

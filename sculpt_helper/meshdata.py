# SPDX-License-Identifier: GPL-3.0-or-later
"""Reading and writing sculpt data with numpy.

Sculpt Mode keeps its own copy of the mesh while active, so tools that edit
vertex data step out to Object Mode, edit the mesh, and step back in. That
round trip also records an undo step, so Ctrl+Z works as usual.
"""

import contextlib

import bpy
import numpy as np

MASK_ATTR = ".sculpt_mask"
FACE_SET_ATTR = ".sculpt_face_set"
HIDE_VERT_ATTR = ".hide_vert"
REF_ATTR = "sh_reference_shape"
REF_NORMAL_ATTR = "sh_reference_normal"
SAVED_MASK_PREFIX = "sh_mask_"


def unsupported_reason(obj):
    """Why vertex-editing tools can't run on this object, or None."""
    if obj is None or obj.type != 'MESH':
        return "Needs an active mesh object"
    if obj.use_dynamic_topology_sculpting:
        return "Turn Dyntopo off first"
    if any(m.type == 'MULTIRES' for m in obj.modifiers):
        return "Not available with a Multires modifier"
    if obj.data.shape_keys:
        return "Not available with shape keys"
    return None


class MeshDataOp:
    """Mixin: poll for tools that edit vertex data of the sculpted mesh."""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if context.mode != 'SCULPT' or obj is None or obj.type != 'MESH':
            return False
        reason = unsupported_reason(obj)
        if reason:
            cls.poll_message_set(reason)
            return False
        return True


@contextlib.contextmanager
def object_mode(context):
    """Temporarily leave Sculpt Mode so the mesh can be edited directly."""
    was_sculpt = context.mode == 'SCULPT'
    if was_sculpt:
        bpy.ops.object.mode_set(mode='OBJECT')
    try:
        yield context.active_object.data
    finally:
        if was_sculpt:
            bpy.ops.object.mode_set(mode='SCULPT')


# ---------------------------------------------------------------------------
# Generic attribute access


def get_float(mesh, name, default=0.0):
    attr = mesh.attributes.get(name)
    n = len(mesh.vertices)
    if attr is None:
        return np.full(n, default, dtype=np.float32)
    out = np.empty(n, dtype=np.float32)
    attr.data.foreach_get("value", out)
    return out


def set_float(mesh, name, values):
    attr = mesh.attributes.get(name)
    if attr is None:
        attr = mesh.attributes.new(name, 'FLOAT', 'POINT')
    attr.data.foreach_set("value", np.ascontiguousarray(values, dtype=np.float32))


def get_vectors(mesh, name):
    attr = mesh.attributes.get(name)
    if attr is None:
        return None
    out = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    attr.data.foreach_get("vector", out)
    return out.reshape(-1, 3)


def set_vectors(mesh, name, values):
    attr = mesh.attributes.get(name)
    if attr is None:
        attr = mesh.attributes.new(name, 'FLOAT_VECTOR', 'POINT')
    attr.data.foreach_set("vector", np.ascontiguousarray(values, dtype=np.float32).ravel())


def get_positions(mesh):
    out = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", out)
    return out.reshape(-1, 3)


def set_positions(mesh, positions):
    mesh.vertices.foreach_set("co", np.ascontiguousarray(positions, dtype=np.float32).ravel())
    mesh.update()


def get_normals(mesh):
    out = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("normal", out)
    return out.reshape(-1, 3)


def get_mask(mesh):
    return get_float(mesh, MASK_ATTR, 0.0)


def set_mask(mesh, values):
    set_float(mesh, MASK_ATTR, np.clip(values, 0.0, 1.0))


def get_hidden(mesh):
    attr = mesh.attributes.get(HIDE_VERT_ATTR)
    n = len(mesh.vertices)
    if attr is None:
        return np.zeros(n, dtype=bool)
    out = np.empty(n, dtype=bool)
    attr.data.foreach_get("value", out)
    return out


def editable_weight(mesh):
    """1 where a vertex may move (visible, unmasked), 0 where it may not."""
    return (1.0 - get_mask(mesh)) * (~get_hidden(mesh))


def edges(mesh):
    out = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get("vertices", out)
    return out.reshape(-1, 2)


def smooth(positions, edge_array, iterations=3, factor=0.5):
    """Laplacian smoothing using the edge graph (vectorised)."""
    n = len(positions)
    a, b = edge_array[:, 0], edge_array[:, 1]
    degree = np.bincount(a, minlength=n) + np.bincount(b, minlength=n)
    degree = np.maximum(degree, 1)[:, None]
    p = positions.copy()
    for _ in range(iterations):
        acc = np.zeros_like(p)
        np.add.at(acc, a, p[b])
        np.add.at(acc, b, p[a])
        p += factor * (acc / degree - p)
    return p


def saved_mask_names(mesh):
    return sorted(a.name[len(SAVED_MASK_PREFIX):] for a in mesh.attributes
                  if a.name.startswith(SAVED_MASK_PREFIX) and a.domain == 'POINT'
                  and a.data_type == 'FLOAT')

# SPDX-License-Identifier: GPL-3.0-or-later
"""Sculpt layers: record changes per layer and change their strength later.

The mesh keeps a base shape plus one offset per layer, so the visible shape
is   base + sum(strength_i * offset_i).   Whatever you sculpt goes into the
active layer: when you change a strength, switch layers or add / remove one,
the difference between the mesh and the last composed shape is first stored
in the layer that was recording, then the shape is recomposed.
"""

import bpy
import numpy as np
from bpy.props import BoolProperty, CollectionProperty, FloatProperty, IntProperty, StringProperty

from . import meshdata as md

BASE_ATTR = "sh_layers_base"
LAYER_PREFIX = "sh_layer_"


def _schedule(self, context):
    obj = context.active_object
    if obj is None:
        return
    _pending.add(obj.name)
    if not bpy.app.timers.is_registered(_flush):
        bpy.app.timers.register(_flush, first_interval=0.15)


class SculptHelperLayer(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Layer")
    uid: StringProperty()
    strength: FloatProperty(name="Strength", default=1.0, soft_min=0.0, soft_max=1.0,
                            min=-2.0, max=2.0, update=_schedule)
    mute: BoolProperty(name="Mute", default=False, update=_schedule)
    applied: FloatProperty(default=1.0)  # strength used when the shape was last composed


def effective(layer):
    return 0.0 if layer.mute else layer.strength


def compose(base, offsets, strengths):
    out = base.copy()
    for d, s in zip(offsets, strengths):
        out += s * d
    return out


def capture(current, base, offsets, applied, recording):
    """Store sculpted changes (current minus composed) into the recording layer.
    Returns new (base, offsets)."""
    diff = current - compose(base, offsets, applied)
    offsets = [d.copy() for d in offsets]
    if recording is not None and 0 <= recording < len(offsets) and abs(applied[recording]) > 1e-6:
        offsets[recording] += diff / applied[recording]
    else:
        base = base + diff
    return base, offsets


def _read(obj, mesh):
    layers = obj.sculpt_helper_layers
    base = md.get_vectors(mesh, BASE_ATTR)
    if base is None or len(base) != len(mesh.vertices):
        return None
    offsets = []
    for layer in layers:
        d = md.get_vectors(mesh, LAYER_PREFIX + layer.uid)
        if d is None or len(d) != len(mesh.vertices):
            return None
        offsets.append(d)
    return base, offsets


def sync(context, obj, report=None):
    """Capture into the recording layer, then recompose with current strengths."""
    layers = obj.sculpt_helper_layers
    with md.object_mode(context) as mesh:
        data = _read(obj, mesh)
        if data is None:
            if report:
                report({'WARNING'}, "Layers no longer match the mesh (topology changed)")
            return False
        base, offsets = data
        applied = [layer.applied for layer in layers]
        base, offsets = capture(md.get_positions(mesh), base, offsets, applied,
                                obj.sculpt_helper_layer_recording)
        strengths = [effective(layer) for layer in layers]
        md.set_vectors(mesh, BASE_ATTR, base)
        for layer, d in zip(layers, offsets):
            md.set_vectors(mesh, LAYER_PREFIX + layer.uid, d)
        md.set_positions(mesh, compose(base, offsets, strengths))
        for layer, s in zip(layers, strengths):
            layer.applied = s
        obj.sculpt_helper_layer_recording = obj.sculpt_helper_layer_index
    return True


_pending = set()


def _flush():
    names = list(_pending)
    _pending.clear()
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            with bpy.context.temp_override(window=win, area=area, region=region):
                obj = bpy.context.active_object
                if (obj is not None and obj.name in names and bpy.context.mode == 'SCULPT'
                        and md.unsupported_reason(obj) is None):
                    sync(bpy.context, obj)
            return None
    return None


class _LayerOp(md.MeshDataOp):
    pass


class SCULPT_HELPER_OT_layer_add(_LayerOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.layer_add"
    bl_label = "Add Layer"
    bl_description = "Start a new layer; what you sculpt next goes into it"

    def execute(self, context):
        obj = context.active_object
        layers = obj.sculpt_helper_layers
        if len(layers):
            if not sync(context, obj, self.report):
                return {'CANCELLED'}
        uid = str(max([int(l.uid) for l in layers if l.uid.isdigit()] + [0]) + 1)
        with md.object_mode(context) as mesh:
            if not len(layers):
                md.set_vectors(mesh, BASE_ATTR, md.get_positions(mesh))
            md.set_vectors(mesh, LAYER_PREFIX + uid, np.zeros((len(mesh.vertices), 3)))
            layer = layers.add()
            layer.name = f"Layer {uid}"
            layer.uid = uid
            layer.applied = 1.0
            obj.sculpt_helper_layer_index = len(layers) - 1
            obj.sculpt_helper_layer_recording = len(layers) - 1
        return {'FINISHED'}


class SCULPT_HELPER_OT_layer_remove(_LayerOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.layer_remove"
    bl_label = "Delete Layer"
    bl_description = "Delete the active layer and remove its changes from the mesh"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return super().poll(context) and len(obj.sculpt_helper_layers) > 0

    def execute(self, context):
        obj = context.active_object
        if not sync(context, obj, self.report):
            return {'CANCELLED'}
        layers = obj.sculpt_helper_layers
        index = obj.sculpt_helper_layer_index
        with md.object_mode(context) as mesh:
            attr = mesh.attributes.get(LAYER_PREFIX + layers[index].uid)
            if attr is not None:
                mesh.attributes.remove(attr)
            layers.remove(index)
            data = _read(obj, mesh)
            base, offsets = data
            md.set_positions(mesh, compose(base, offsets, [effective(l) for l in layers]))
            obj.sculpt_helper_layer_index = max(0, index - 1)
            obj.sculpt_helper_layer_recording = obj.sculpt_helper_layer_index if len(layers) else -1
            if not len(layers):
                base_attr = mesh.attributes.get(BASE_ATTR)
                if base_attr is not None:
                    mesh.attributes.remove(base_attr)
        return {'FINISHED'}


class SCULPT_HELPER_OT_layer_apply_all(_LayerOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.layer_apply_all"
    bl_label = "Apply All Layers"
    bl_description = "Keep the current shape and remove the layers"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return super().poll(context) and len(obj.sculpt_helper_layers) > 0

    def execute(self, context):
        obj = context.active_object
        sync(context, obj)
        with md.object_mode(context) as mesh:
            for name in [BASE_ATTR] + [LAYER_PREFIX + l.uid for l in obj.sculpt_helper_layers]:
                attr = mesh.attributes.get(name)
                if attr is not None:
                    mesh.attributes.remove(attr)
            obj.sculpt_helper_layers.clear()
            obj.sculpt_helper_layer_index = 0
            obj.sculpt_helper_layer_recording = -1
        return {'FINISHED'}


class SCULPT_HELPER_OT_layer_sync(_LayerOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.layer_sync"
    bl_label = "Update Layers"
    bl_description = "Store recent sculpting in the active layer and apply strengths now"

    def execute(self, context):
        return {'FINISHED'} if sync(context, context.active_object, self.report) else {'CANCELLED'}


class SCULPT_HELPER_UL_layers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        rec = index == data.sculpt_helper_layer_recording
        row.prop(item, "name", text="", emboss=False, icon='REC' if rec else 'BLANK1')
        row.prop(item, "strength", text="", slider=True)
        row.prop(item, "mute", text="", icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


def draw_layers(layout, context):
    obj = context.active_object
    reason = md.unsupported_reason(obj)
    if reason:
        layout.label(text=reason, icon='INFO')
        return
    row = layout.row()
    row.template_list("SCULPT_HELPER_UL_layers", "", obj, "sculpt_helper_layers",
                      obj, "sculpt_helper_layer_index", rows=3)
    col = row.column(align=True)
    col.operator("sculpt_helper.layer_add", icon='ADD', text="")
    col.operator("sculpt_helper.layer_remove", icon='REMOVE', text="")
    row = layout.row(align=True)
    row.operator("sculpt_helper.layer_sync", icon='FILE_REFRESH')
    row.operator("sculpt_helper.layer_apply_all", text="Apply All")
    if len(obj.sculpt_helper_layers):
        layout.label(text="Sculpting goes into the ● layer", icon='INFO')


classes = (
    SculptHelperLayer,
    SCULPT_HELPER_OT_layer_add,
    SCULPT_HELPER_OT_layer_remove,
    SCULPT_HELPER_OT_layer_apply_all,
    SCULPT_HELPER_OT_layer_sync,
    SCULPT_HELPER_UL_layers,
)


def register():
    bpy.types.Object.sculpt_helper_layers = CollectionProperty(type=SculptHelperLayer)
    bpy.types.Object.sculpt_helper_layer_index = IntProperty(default=0, update=_schedule)
    bpy.types.Object.sculpt_helper_layer_recording = IntProperty(default=-1)


def unregister():
    if bpy.app.timers.is_registered(_flush):
        bpy.app.timers.unregister(_flush)
    del bpy.types.Object.sculpt_helper_layer_recording
    del bpy.types.Object.sculpt_helper_layer_index
    del bpy.types.Object.sculpt_helper_layers

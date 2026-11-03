# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-scene settings used by the panels."""

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty


class SculptHelperSceneSettings(bpy.types.PropertyGroup):
    deform_strength: FloatProperty(
        name="Strength", description="Strength of each deform filter press",
        default=0.5, min=0.0, soft_max=2.0, max=10.0)
    deform_iterations: IntProperty(
        name="Iterations", description="How many times each filter press is applied",
        default=1, min=1, max=50)
    multires_link_levels: BoolProperty(
        name="Link Levels",
        description="Keep the viewport, sculpt and render levels together",
        default=True)
    extract_thickness: BoolProperty(
        name="Solidify", description="Give extracted parts thickness", default=True)
    extract_smooth: IntProperty(
        name="Smooth", description="Smoothing passes on the extracted border",
        default=4, min=0, max=100)
    extract_threshold: FloatProperty(
        name="Threshold", description="Mask value above which faces are extracted",
        default=0.5, min=0.0, max=1.0)
    depth_limit_height: FloatProperty(
        name="Max Height", description="How far strokes may build up above the recorded shape",
        default=0.05, min=0.0, soft_max=1.0, unit='LENGTH', precision=4)
    depth_limit_depth: FloatProperty(
        name="Max Depth", description="How far strokes may cut below the recorded shape",
        default=0.05, min=0.0, soft_max=1.0, unit='LENGTH', precision=4)
    depth_limit_auto: BoolProperty(
        name="Auto", description="Apply the Depth Limit after every stroke",
        default=False, update=lambda self, ctx: _depth_auto_update(self, ctx))
    stamp_strength: FloatProperty(
        name="Strength", description="How strongly Copy Stamp applies the sampled detail",
        default=1.0, min=0.0, soft_max=1.0, max=4.0)
    stamp_smooth: IntProperty(
        name="Detail Size", description=("Smoothing passes used to separate detail from form; "
                                         "higher keeps larger features"),
        default=10, min=1, max=60)
    stamp_replace: BoolProperty(
        name="Replace Detail",
        description="Replace the detail already at the target instead of adding to it",
        default=True)
    pivot_blend: FloatProperty(
        name="Blend Width", description=("How far the bend fades into the root side, "
                                         "relative to the limb thickness (W)"),
        default=0.6, min=0.0, soft_max=3.0)
    pivot_length: FloatProperty(
        name="Bend Length", description=("Spread the bend along the part, relative to the limb "
                                         "thickness, for necks and tails (R). 0 bends at the joint"),
        default=0.0, min=0.0, soft_max=10.0)
    pivot_use_mask: BoolProperty(
        name="Use Mask", description="Masked areas don't move (M)", default=False)
    pivot_smooth: BoolProperty(
        name="Smooth Joint", description="Smooth the bend around the joint (K)", default=True)
    transfer_source: PointerProperty(
        name="Source", type=bpy.types.Object,
        description="Object whose surface the shape is transferred from",
        poll=lambda self, obj: obj.type == 'MESH')
    slice_new_object: BoolProperty(
        name="Slice to New Object",
        description="Keep the sliced part as a new object instead of deleting it",
        default=True)
    history_auto: BoolProperty(
        name="Auto Snapshot", description="Take a history snapshot every few strokes",
        default=True, update=lambda self, ctx: _history_auto_update(self, ctx))
    history_every: IntProperty(
        name="Every N Strokes", description="Strokes between automatic snapshots",
        default=5, min=1, soft_max=50)
    history_max: IntProperty(
        name="Max Snapshots", description=("Oldest snapshots are dropped past this number "
                                           "(the current one and the selected one are kept)"),
        default=30, min=2, soft_max=200)
    history_keep_in_file: BoolProperty(
        name="Keep in File",
        description="Save the snapshots inside the .blend file (makes the file bigger)",
        default=False)
    history_blend: FloatProperty(
        name="Blend", description="Blend the current shape toward the selected snapshot",
        default=0.0, min=0.0, max=1.0, update=lambda self, ctx: _history_blend_update(self, ctx))
    morph_target: EnumProperty(
        name="Target", description="Shape the Morph Target brush pulls toward",
        items=(('RECORDED', "Recorded Shape", "The shape saved with Record Shape (Deform panel)"),
               ('SNAPSHOT', "Snapshot", "The snapshot selected in the History panel")),
        default='SNAPSHOT')
    morph_brush_strength: FloatProperty(
        name="Strength", description="How far each dab pulls toward the target",
        default=0.5, min=0.0, max=1.0)


def _history_auto_update(self, context):
    from . import history
    history.auto_update(self, context)


def _history_blend_update(self, context):
    from . import history_ui
    history_ui.blend_update(self, context)


def _depth_auto_update(self, context):
    from . import ops_shape
    ops_shape.depth_auto_update(self, context)


classes = (SculptHelperSceneSettings,)


def register():
    bpy.types.Scene.sculpt_helper = PointerProperty(type=SculptHelperSceneSettings)


def unregister():
    del bpy.types.Scene.sculpt_helper

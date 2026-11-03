# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-scene settings used by the panels."""

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, PointerProperty


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
    slice_new_object: BoolProperty(
        name="Slice to New Object",
        description="Keep the sliced part as a new object instead of deleting it",
        default=True)


def _depth_auto_update(self, context):
    from . import ops_shape
    ops_shape.depth_auto_update(self, context)


classes = (SculptHelperSceneSettings,)


def register():
    bpy.types.Scene.sculpt_helper = PointerProperty(type=SculptHelperSceneSettings)


def unregister():
    del bpy.types.Scene.sculpt_helper

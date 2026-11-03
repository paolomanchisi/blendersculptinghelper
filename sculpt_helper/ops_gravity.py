# SPDX-License-Identifier: GPL-3.0-or-later
"""Gravity direction for sculpt strokes.

Blender's own Gravity option pulls strokes along the Z axis of an
"orientation" object. These tools keep a hidden empty for that and aim it:
toward the bottom of the screen, straight into the screen, or along a
direction you drag in the viewport.
"""

import bpy
from mathutils import Vector

from . import utils

EMPTY_NAME = "SculptHelper Gravity"


def gravity_empty(context):
    obj = bpy.data.objects.get(EMPTY_NAME)
    if obj is None:
        obj = bpy.data.objects.new(EMPTY_NAME, None)
        obj.empty_display_type = 'SINGLE_ARROW'
        obj.hide_select = True
        obj.hide_render = True
    if obj.name not in context.scene.collection.objects:
        context.scene.collection.objects.link(obj)
    obj.hide_viewport = True
    return obj


def aim(context, direction):
    """Point gravity along the world-space ``direction``."""
    direction = Vector(direction).normalized()
    obj = gravity_empty(context)
    # Blender pulls toward the orientation object's -Z, so align -Z with
    # the direction. Matrix only, so the object needs no location.
    rot = (-direction).to_track_quat('Z', 'Y').to_matrix().to_4x4()
    obj.matrix_world = rot
    sculpt = context.tool_settings.sculpt
    sculpt.gravity_object = obj
    if sculpt.gravity == 0.0:
        sculpt.gravity = 0.3


class SCULPT_HELPER_OT_gravity_set(bpy.types.Operator):
    bl_idname = "sculpt_helper.gravity_set"
    bl_label = "Set Gravity Direction"
    bl_description = "Aim the stroke gravity"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(items=(
        ('SCREEN_DOWN', "Screen Down", "Toward the bottom of the screen"),
        ('INTO_SCREEN', "Into Screen", "Away from you, into the screen"),
        ('WORLD_DOWN', "World Down", "Along world -Z (Blender's default)"),
    ))

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context)

    def execute(self, context):
        sculpt = context.tool_settings.sculpt
        if self.direction == 'WORLD_DOWN':
            sculpt.gravity_object = None
            if sculpt.gravity == 0.0:
                sculpt.gravity = 0.3
            return {'FINISHED'}
        view = context.region_data.view_rotation
        if self.direction == 'SCREEN_DOWN':
            aim(context, view @ Vector((0.0, -1.0, 0.0)))
        else:
            aim(context, view @ Vector((0.0, 0.0, -1.0)))
        return {'FINISHED'}


class SCULPT_HELPER_OT_gravity_drag(bpy.types.Operator):
    bl_idname = "sculpt_helper.gravity_drag"
    bl_label = "Drag Gravity Direction"
    bl_description = "Drag in the viewport to set which way gravity pulls"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context)

    def invoke(self, context, event):
        self._start = None
        self._end = None
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set("Drag the direction gravity should pull · Esc cancels")
        return {'RUNNING_MODAL'}

    def _draw(self):
        if self._start and self._end:
            utils.draw_polyline([self._start, self._end], (0.4, 0.8, 1.0, 1.0), width=2.5)

    def _finish(self, context, result):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        context.workspace.status_text_set(None)
        context.area.tag_redraw()
        return {result}

    def modal(self, context, event):
        context.area.tag_redraw()
        coord = (event.mouse_region_x, event.mouse_region_y)
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._start = self._end = coord
        elif event.type == 'MOUSEMOVE' and self._start:
            self._end = coord
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self._start:
            dx, dy = self._end[0] - self._start[0], self._end[1] - self._start[1]
            if abs(dx) + abs(dy) < utils.DRAG_THRESHOLD:
                return self._finish(context, 'CANCELLED')
            view = context.region_data.view_rotation
            aim(context, view @ Vector((dx, dy, 0.0)))
            return self._finish(context, 'FINISHED')
        elif event.type in {'ESC', 'RIGHTMOUSE'}:
            return self._finish(context, 'CANCELLED')
        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


def draw_gravity(layout, context):
    sculpt = context.tool_settings.sculpt
    col = layout.column(align=True)
    col.prop(sculpt, "gravity", slider=True, text="Gravity")
    row = col.row(align=True)
    for direction, text in (('SCREEN_DOWN', "Screen ↓"), ('INTO_SCREEN', "Into Screen"),
                            ('WORLD_DOWN', "World ↓")):
        row.operator("sculpt_helper.gravity_set", text=text).direction = direction
    col.operator("sculpt_helper.gravity_drag", text="Drag Direction", icon='ORIENTATION_GIMBAL')
    obj = sculpt.gravity_object
    col.label(text="Direction: " + ("custom" if obj and obj.name == EMPTY_NAME
                                     else obj.name if obj else "world down"))


classes = (SCULPT_HELPER_OT_gravity_set, SCULPT_HELPER_OT_gravity_drag)

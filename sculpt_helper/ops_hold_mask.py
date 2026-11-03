# SPDX-License-Identifier: GPL-3.0-or-later
"""Hold-to-mask: while the key is held the Mask brush is active.

* Drag on the mesh          -> paint mask (Ctrl: remove mask)
* Click on the mesh         -> blur mask edges (Ctrl: sharpen)
* Click on the background   -> invert mask
* Drag on the background    -> clear mask
* Release the key           -> previous tool and brush come back
"""

import bpy

from . import utils


class SCULPT_HELPER_OT_hold_mask(bpy.types.Operator):
    bl_idname = "sculpt_helper.hold_mask"
    bl_label = "Hold Mask Brush"
    bl_description = ("While held: Mask brush. Click mesh to blur (Ctrl: sharpen), "
                      "click background to invert, drag background to clear")
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context)

    def invoke(self, context, event):
        self._key = event.type
        self._state = utils.capture_brush_state(context)
        if not utils.activate_essential_brush("Mask"):
            self.report({'WARNING'}, "Mask brush not found in Essentials library")
            return {'CANCELLED'}
        self._press = None      # (x, y) of a background press
        self._stroke = None     # ((x, y), ctrl) of a press handed to the brush
        self._released = False
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set(
            "Mask: drag paint · Ctrl drag erase · click mesh blur (Ctrl sharpen) · "
            "click background invert · drag background clear")
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        utils.restore_brush_state(self._state)
        return {'FINISHED'}

    def modal(self, context, event):
        # Key released: restore once any stroke in flight has finished.
        if event.type == self._key and event.value == 'RELEASE':
            self._released = True
        if self._released:
            if utils.stroke_running(context) or self._stroke is not None:
                if event.type == 'TIMER' and self._stroke is not None:
                    pass  # fall through to the click / drag check below
                else:
                    return {'PASS_THROUGH'}
            else:
                return self._finish(context)

        if event.type == self._key:
            return {'RUNNING_MODAL'}  # key repeat

        coord = (event.mouse_region_x, event.mouse_region_y)

        # A press on the mesh was passed to Blender's own brush stroke. Once
        # that stroke has ended, decide whether it was a click or a drag.
        if self._stroke is not None and event.type == 'TIMER':
            if not utils.stroke_running(context):
                start, ctrl = self._stroke
                self._stroke = None
                if not utils.dragged(start, coord):
                    # A click: drop the single dab it painted, then filter.
                    bpy.ops.ed.undo()
                    bpy.ops.sculpt.mask_filter(
                        filter_type='SHARPEN' if ctrl else 'SMOOTH',
                        auto_iteration_count=True)
            return {'PASS_THROUGH'}

        if event.type == 'TIMER':
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if not utils.in_region(context, coord):
                return {'PASS_THROUGH'}
            if utils.hit_active_object(context, coord):
                # Let the regular keymap start the stroke (Ctrl = subtract).
                self._stroke = (coord, event.ctrl)
                return {'PASS_THROUGH'}
            self._press = coord
            return {'RUNNING_MODAL'}

        if self._press is not None and event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self._press is not None:
            start = self._press
            self._press = None
            if utils.dragged(start, coord):
                bpy.ops.paint.mask_flood_fill(mode='VALUE', value=0.0)
            else:
                bpy.ops.paint.mask_flood_fill(mode='INVERT')
            return {'RUNNING_MODAL'}

        if event.type in {'ESC'}:
            return self._finish(context)

        return {'PASS_THROUGH'}


classes = (SCULPT_HELPER_OT_hold_mask,)

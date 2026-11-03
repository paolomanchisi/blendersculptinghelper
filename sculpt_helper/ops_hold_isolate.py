# SPDX-License-Identifier: GPL-3.0-or-later
"""Hold-to-isolate: while the key is held, enclose an area to show only it.

* Drag                      -> box / lasso / line; everything outside is hidden
* Click a face set          -> show only that face set (click again: show all)
* Click the background      -> show everything
* Tab or mouse wheel        -> cycle box / lasso / line
* Ctrl while releasing      -> hide the enclosed area instead
"""

import time

import bpy

from . import utils

METHODS = ('BOX', 'LASSO', 'LINE')


class SCULPT_HELPER_OT_hold_isolate(bpy.types.Operator):
    bl_idname = "sculpt_helper.hold_isolate"
    bl_label = "Hold Isolate"
    bl_description = ("While held: drag a box, lasso or line to show only that area, "
                      "click a face set to isolate it, click background to show all")
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context)

    def invoke(self, context, event):
        prefs = utils.addon_prefs(context)
        self._key = event.type
        self._method = prefs.isolate_method if prefs else 'BOX'
        self._front = prefs.front_faces_only if prefs else False
        self._press = None
        self._path = []
        self._released = False
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self._status(context)
        return {'RUNNING_MODAL'}

    def _status(self, context):
        context.workspace.status_text_set(
            f"Isolate ({self._method.title()}, Tab to change): drag to show only the area · "
            "Ctrl hides it instead · click face set to isolate · click background to show all")

    def _draw(self):
        if self._press is None or not self._path:
            return
        color = (1.0, 0.62, 0.15, 0.95)
        if self._method == 'BOX':
            utils.draw_polyline(utils.rect_points(self._press, self._path[-1]), color, closed=True)
        elif self._method == 'LASSO':
            utils.draw_polyline(self._path, color, closed=True)
        else:
            utils.draw_polyline([self._press, self._path[-1]], color)

    def _finish(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        context.workspace.status_text_set(None)
        context.area.tag_redraw()
        return {'FINISHED'}

    def _apply_gesture(self, context, end, ctrl):
        area = 'Inside' if ctrl else 'OUTSIDE'
        start = self._press
        if self._method == 'BOX':
            bpy.ops.paint.hide_show(
                action='HIDE', area=area, use_front_faces_only=self._front,
                xmin=int(min(start[0], end[0])), xmax=int(max(start[0], end[0])),
                ymin=int(min(start[1], end[1])), ymax=int(max(start[1], end[1])))
        elif self._method == 'LASSO':
            now = time.time()
            path = [{"name": "", "loc": p, "time": now} for p in self._path]
            bpy.ops.paint.hide_show_lasso_gesture(
                action='HIDE', area=area, use_front_faces_only=self._front, path=path)
        else:
            bpy.ops.paint.hide_show_line_gesture(
                action='HIDE', area=area, use_front_faces_only=self._front,
                xstart=int(start[0]), ystart=int(start[1]),
                xend=int(end[0]), yend=int(end[1]), flip=ctrl)

    def modal(self, context, event):
        context.area.tag_redraw()
        if event.type == self._key and event.value == 'RELEASE':
            self._released = True
        if self._released and self._press is None:
            return self._finish(context)
        if event.type == self._key:
            return {'RUNNING_MODAL'}

        if event.type in {'TAB', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and event.value == 'PRESS':
            step = -1 if event.type == 'WHEELDOWNMOUSE' else 1
            self._method = METHODS[(METHODS.index(self._method) + step) % len(METHODS)]
            self._status(context)
            return {'RUNNING_MODAL'}

        coord = (event.mouse_region_x, event.mouse_region_y)

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._press = coord
            self._path = [coord]
            return {'RUNNING_MODAL'}

        if self._press is not None and event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self._path.append(coord)
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self._press is not None:
            if utils.dragged(self._press, coord):
                self._path.append(coord)
                self._apply_gesture(context, coord, event.ctrl)
            elif utils.hit_active_object(context, coord):
                bpy.ops.sculpt.face_set_change_visibility('INVOKE_DEFAULT', mode='TOGGLE')
            else:
                bpy.ops.paint.hide_show_all(action='SHOW')
            self._press = None
            self._path = []
            return {'RUNNING_MODAL'}

        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            if self._press is not None:
                self._press = None
                self._path = []
                return {'RUNNING_MODAL'}
            return self._finish(context)

        return {'PASS_THROUGH'}


classes = (SCULPT_HELPER_OT_hold_isolate,)

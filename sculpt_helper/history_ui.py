# SPDX-License-Identifier: GPL-3.0-or-later
"""History panel, timeline strip and Morph Target brush."""

import math
import time

import bpy
import numpy as np

from . import history as hs
from . import meshdata as md
from . import utils


def _hist(context, create=True):
    obj = context.active_object
    if obj is None or obj.type != 'MESH':
        return None
    return hs.history_for(obj, create=create)


class _HistOp:
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return context.mode == 'SCULPT' and obj is not None and obj.type == 'MESH' \
            and not obj.use_dynamic_topology_sculpting


class _SelectedOp(_HistOp):
    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        hist = _hist(context, create=False)
        return hist is not None and hist.selected in hist.snaps


class SCULPT_HELPER_OT_history_snapshot(_HistOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.history_snapshot"
    bl_label = "Snapshot"
    bl_description = "Save the current shape on the history timeline"

    label: bpy.props.StringProperty(name="Name", default="")

    def execute(self, context):
        snap = hs.take_snapshot(context, context.active_object, self.label or None)
        self.report({'INFO'}, f"Snapshot {snap.label}")
        return {'FINISHED'}


class SCULPT_HELPER_OT_history_select(_HistOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.history_select"
    bl_label = "Select Snapshot"
    bl_description = "Choose the snapshot the history actions use"

    sid: bpy.props.IntProperty()

    def execute(self, context):
        hist = _hist(context)
        if self.sid in hist.snaps:
            hist.selected = self.sid
            hs.end_blend(context.active_object)
            context.scene.sculpt_helper["history_blend"] = 0.0
        return {'FINISHED'}


class SCULPT_HELPER_OT_history_jump(_SelectedOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.history_jump"
    bl_label = "Jump to Snapshot"
    bl_description = ("Restore the selected snapshot. Sculpting from here starts a branch; "
                      "later snapshots are kept")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        hist = _hist(context)
        hs.jump_to(context, context.active_object, hist.selected)
        return {'FINISHED'}


class SCULPT_HELPER_OT_history_paint_back(_SelectedOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.history_paint_back"
    bl_label = "Paint Back Masked"
    bl_description = "Bring the selected snapshot's shape back where the mask is"
    bl_options = {'REGISTER', 'UNDO'}

    strength: bpy.props.FloatProperty(name="Strength", default=1.0, min=0.0, max=1.0)

    def execute(self, context):
        hist = _hist(context)
        if not hs.paint_back(context, context.active_object, hist.selected, self.strength):
            self.report({'WARNING'}, "The mesh topology changed since this snapshot; use Jump")
            return {'CANCELLED'}
        return {'FINISHED'}


class SCULPT_HELPER_OT_history_delete(_SelectedOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.history_delete"
    bl_label = "Delete Snapshot"
    bl_description = "Remove the selected snapshot (its children move up to its parent)"

    def execute(self, context):
        hist = _hist(context)
        hist.remove(hist.selected)
        return {'FINISHED'}


class SCULPT_HELPER_OT_history_clear(_HistOp, bpy.types.Operator):
    bl_idname = "sculpt_helper.history_clear"
    bl_label = "Clear History"
    bl_description = "Remove every snapshot of this object"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        _hist(context).clear()
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Blend slider (panel): deferred, like the layer strengths


def blend_update(self, context):
    if not bpy.app.timers.is_registered(_apply_blend):
        bpy.app.timers.register(_apply_blend, first_interval=0.12)


def _apply_blend():
    context = bpy.context
    for win in context.window_manager.windows:
        area, region = hs._view3d(win)
        if area is None:
            continue
        with context.temp_override(window=win, area=area, region=region):
            obj = context.active_object
            hist = _hist(context, create=False)
            if (context.mode == 'SCULPT' and hist is not None and hist.selected in hist.snaps
                    and md.unsupported_reason(obj) is None):
                hs.blend(context, obj, hist.selected, context.scene.sculpt_helper.history_blend)
        return None
    return None


# ---------------------------------------------------------------------------
# Morph Target brush


def morph_target(context, mesh):
    """Target positions for the Morph Target brush, or None."""
    settings = context.scene.sculpt_helper
    if settings.morph_target == 'RECORDED':
        ref = md.get_vectors(mesh, md.REF_ATTR)
        return ref if ref is not None and len(ref) == len(mesh.vertices) else None
    hist = _hist(context, create=False)
    if hist is None or hist.selected not in hist.snaps:
        return None
    snap = hist.snaps[hist.selected]
    return snap.positions if hs.compatible(mesh, snap) else None


def morph_dab(positions, target, centre, radius, strength, editable):
    d = np.linalg.norm(positions - centre, axis=1)
    sel = np.nonzero(d < radius)[0]
    if len(sel) == 0:
        return positions, 0
    t = 1.0 - d[sel] / radius
    w = (t * t * (3 - 2 * t)) * strength * editable[sel]
    positions[sel] += (target[sel] - positions[sel]) * w[:, None]
    return positions, len(sel)


class SCULPT_HELPER_OT_morph_brush(bpy.types.Operator):
    bl_idname = "sculpt_helper.morph_brush"
    bl_label = "Morph Target Brush"
    bl_description = ("Paint the surface back toward the recorded shape or the selected "
                      "snapshot. F radius as usual; Esc or right-click to finish")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context) and md.unsupported_reason(context.active_object) is None

    def invoke(self, context, event):
        with md.object_mode(context) as mesh:
            if morph_target(context, mesh) is None:
                self.report({'WARNING'}, "Pick a target first: Record Shape, or select a "
                                         "snapshot with the same topology")
                return {'CANCELLED'}
        self._stroke = None
        self._mouse = (event.mouse_region_x, event.mouse_region_y)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (context,),
                                                              'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set(
            "Morph Target: drag to paint toward the target · Esc / right-click to finish")
        return {'RUNNING_MODAL'}

    def _pixels(self, context):
        paint = context.tool_settings.sculpt
        ups = paint.unified_paint_settings
        return ups.size if ups.use_unified_size or paint.brush is None else paint.brush.size

    def _finish(self, context):
        if self._stroke is not None:
            bpy.ops.object.mode_set(mode='SCULPT')
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        context.workspace.status_text_set(None)
        context.area.tag_redraw()
        return {'FINISHED'}

    def _dab(self, context, coord):
        hit = utils.raycast_active(context, coord)
        if hit is None:
            return
        loc = hit[0]
        radius = utils.pixel_radius_to_object(context, coord, loc, self._pixels(context))
        st = self._stroke
        st["pos"], _n = morph_dab(st["pos"], st["target"], np.array(loc), radius,
                                  context.scene.sculpt_helper.morph_brush_strength, st["editable"])
        md.set_positions(context.active_object.data, st["pos"])

    def modal(self, context, event):
        context.area.tag_redraw()
        coord = (event.mouse_region_x, event.mouse_region_y)
        self._mouse = coord
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            return self._finish(context)
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if utils.raycast_active(context, coord) is None:
                return {'PASS_THROUGH'}
            bpy.ops.object.mode_set(mode='OBJECT')
            mesh = context.active_object.data
            self._stroke = {"pos": md.get_positions(mesh).astype(np.float64),
                            "target": morph_target(context, mesh).astype(np.float64),
                            "editable": md.editable_weight(mesh)}
            self._dab(context, coord)
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE' and self._stroke is not None:
            self._dab(context, coord)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self._stroke is not None:
            self._stroke = None
            bpy.ops.object.mode_set(mode='SCULPT')
            return {'RUNNING_MODAL'}
        if self._stroke is not None:
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}

    def _draw(self, context):
        r = self._pixels(context)
        x, y = self._mouse
        pts = [(x + r * math.cos(a), y + r * math.sin(a))
               for a in (2 * math.pi * i / 48 for i in range(48))]
        utils.draw_polyline(pts, (0.3, 0.9, 0.7, 0.9), closed=True)


# ---------------------------------------------------------------------------
# Timeline strip (bottom of the viewport)


def strip_layout(hist, region_w, scale, scroll=0):
    """Node positions for the strip: list of (sid, x, y_offset, is_head, is_selected).
    Newest snapshots are kept in view; ``scroll`` shifts back in time."""
    lanes = hist.lanes()
    if not lanes:
        return []
    step = 58 * scale
    left = 300 * scale
    usable = max(region_w - left - 20 * scale, step)
    visible = int(usable // step)
    columns = sorted(set(c for c, _l in lanes.values()))
    last = max(columns)
    first = max(0, last - visible + 1 - scroll)
    out = []
    for sid, (col, lane) in lanes.items():
        if col < first or col > first + visible - 1:
            continue
        out.append((sid, left + (col - first) * step + step / 2, lane * 30 * scale,
                    sid == hist.head, sid == hist.selected))
    return out


_strip = {"on": False}


def capture_thumbnail(context, snap):
    """Render the current view into a small offscreen texture (draw time only)."""
    import gpu
    region, space = context.region, context.space_data
    w, h = 96, 72
    try:
        offscreen = gpu.types.GPUOffScreen(w, h)
        offscreen.draw_view3d(context.scene, context.view_layer, space, region,
                              space.region_3d.view_matrix, space.region_3d.window_matrix,
                              do_color_management=True)
        snap.thumb = offscreen
    except Exception:  # noqa: BLE001 - thumbnails are a nicety
        snap.thumb = False


class SCULPT_HELPER_OT_history_timeline(bpy.types.Operator):
    bl_idname = "sculpt_helper.history_timeline"
    bl_label = "History Timeline"
    bl_description = "Show the history timeline along the bottom of this viewport (run again to hide)"

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        if _strip["on"]:
            _strip["on"] = False
            return {'FINISHED'}
        from . import gpu_draw
        _strip["on"] = True
        self._area = context.area
        self._region = next(r for r in context.area.regions if r.type == 'WINDOW')
        self._scale = gpu_draw.ui_scale()
        self._scroll = 0
        self._hits = []
        self._hover = None
        self._blend = None  # live blend drag: (x, w)
        self._last_click = (None, 0.0)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _stop(self):
        _strip["on"] = False
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        try:
            self._area.tag_redraw()
        except ReferenceError:
            pass
        return {'FINISHED'}

    def _height(self):
        return 84 * self._scale

    def _buttons(self):
        s = self._scale
        y = 12 * s
        h = 22 * s
        x = 10 * s
        out = []
        for kind, label, w in (("snap", "+ Snapshot", 84), ("jump", "Jump", 46),
                               ("paint", "Paint Back", 74), ("brush", "Brush", 50)):
            out.append((x, y + h + 6 * s, w * s, h, kind, label))
            x += (w + 4) * s
        out.append((10 * s, y, 230 * s, h, "blend", "Blend"))
        out.append((244 * s, y, 22 * s, h, "close", "×"))
        return out

    def modal(self, context, event):
        if not _strip["on"]:
            return self._stop()
        try:
            self._area.tag_redraw()
        except ReferenceError:
            return self._stop()
        if context.mode != 'SCULPT':
            return {'PASS_THROUGH'}
        px = event.mouse_x - self._region.x
        py = event.mouse_y - self._region.y
        obj = context.active_object

        if self._blend is not None:
            if event.type == 'MOUSEMOVE':
                x, w = self._blend
                f = max(0.0, min(1.0, (px - x) / w))
                hist = _hist(context)
                snap = hist.snaps.get(hist.selected)
                mesh = obj.data
                if snap is not None and hs.compatible(mesh, snap):
                    base = hs._blend_base.setdefault(obj.name, md.get_positions(mesh).copy())
                    md.set_positions(mesh, base + (snap.positions - base) * f)
                    context.scene.sculpt_helper["history_blend"] = f
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self._blend = None
                bpy.ops.object.mode_set(mode='SCULPT')
            return {'RUNNING_MODAL'}

        if not (0 <= px <= self._region.width and 0 <= py <= self._height()):
            return {'PASS_THROUGH'}
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            self._scroll = max(0, self._scroll + (1 if event.type == 'WHEELUPMOUSE' else -1))
            return {'RUNNING_MODAL'}
        if event.type != 'LEFTMOUSE' or event.value != 'PRESS':
            return {'RUNNING_MODAL'} if event.type in {'RIGHTMOUSE'} else {'PASS_THROUGH'}

        for x, y, w, h, kind, _label in self._buttons():
            if x <= px <= x + w and y <= py <= y + h:
                return self._button(context, kind, x, w, px)
        hist = _hist(context)
        for sid, nx, ny, _head, _sel in strip_layout(hist, self._region.width, self._scale,
                                                    self._scroll):
            cy = self._height() - 24 * self._scale - ny
            if abs(px - nx) < 22 * self._scale and abs(py - cy) < 18 * self._scale:
                last_sid, last_t = self._last_click
                if last_sid == sid and time.time() - last_t < 0.4:
                    hist.selected = sid
                    bpy.ops.sculpt_helper.history_jump()
                else:
                    bpy.ops.sculpt_helper.history_select(sid=sid)
                self._last_click = (sid, time.time())
                return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}

    def _button(self, context, kind, x, w, px):
        try:
            if kind == "snap":
                bpy.ops.sculpt_helper.history_snapshot()
            elif kind == "jump":
                bpy.ops.sculpt_helper.history_jump()
            elif kind == "paint":
                bpy.ops.sculpt_helper.history_paint_back()
            elif kind == "brush":
                bpy.ops.sculpt_helper.morph_brush('INVOKE_DEFAULT')
            elif kind == "close":
                _strip["on"] = False
            elif kind == "blend":
                hist = _hist(context)
                if hist.selected in hist.snaps and md.unsupported_reason(context.active_object) is None:
                    bpy.ops.object.mode_set(mode='OBJECT')
                    self._blend = (x, w)
        except RuntimeError as exc:
            print("Sculpt Helper:", exc)
        return {'RUNNING_MODAL'}

    def _draw(self):
        context = bpy.context
        if context.area != self._area or context.mode not in {'SCULPT', 'OBJECT'}:
            return
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            return
        from . import gpu_draw as g
        s = self._scale
        hist = _hist(context)
        if hist.pending_thumb in hist.snaps and context.mode == 'SCULPT':
            capture_thumbnail(context, hist.snaps[hist.pending_thumb])
            hist.pending_thumb = None
        H = self._height()
        g.rect(0, 0, self._region.width, H, (0.08, 0.09, 0.10, 0.88))
        for x, y, w, h, kind, label in self._buttons():
            g.rect(x, y, w, h, g.BUTTON)
            if kind == "blend":
                f = context.scene.sculpt_helper.history_blend
                g.rect(x, y, w * f, h, (0.30, 0.45, 0.75, 0.9))
                label = f"Blend to selected {f:.2f}"
            g.text(x + w / 2, y + h * 0.3, label, 10, align='CENTER', max_width=w - 4)
        nodes = strip_layout(hist, self._region.width, s, self._scroll)
        pos = {sid: (nx, H - 24 * s - ny) for sid, nx, ny, _h, _sel in nodes}
        for sid, (nx, ny) in pos.items():
            parent = hist.snaps[sid].parent
            if parent in pos:
                px_, py_ = pos[parent]
                utils.draw_polyline([(px_, py_), (nx, ny)], (0.5, 0.55, 0.6, 0.8))
        for sid, nx, ny, head, sel in nodes:
            cy = H - 24 * s - ny
            snap = hist.snaps[sid]
            if sel:
                g.rect(nx - 23 * s, cy - 19 * s, 46 * s, 38 * s, g.ACCENT)
            thumb = snap.thumb
            if thumb:
                g.texture(thumb.texture_color, nx - 21 * s, cy - 16 * s, 42 * s, 32 * s)
            else:
                g.disc(nx, cy, 7 * s, (0.95, 0.65, 0.2, 1.0) if head else (0.7, 0.72, 0.76, 1.0))
            if head:
                g.text(nx, cy + 20 * s, "now", 9, (0.95, 0.65, 0.2, 1.0), align='CENTER')
            g.text(nx, cy - 30 * s if ny == 0 else cy - 28 * s, snap.label, 9,
                   g.TEXT if sel else g.TEXT_DIM, align='CENTER', max_width=54 * s)
        if not nodes:
            g.text(300 * s, H / 2, "No snapshots yet: sculpt a few strokes or press + Snapshot",
                   10, g.TEXT_DIM)


def is_strip_on():
    return _strip["on"]


# ---------------------------------------------------------------------------
# Sidebar panel


def draw_history(layout, context):
    settings = context.scene.sculpt_helper
    obj = context.active_object
    hist = _hist(context, create=False)
    row = layout.row(align=True)
    row.operator("sculpt_helper.history_snapshot", icon='ADD')
    row.operator("sculpt_helper.history_timeline",
                 text="Timeline: " + ("On" if is_strip_on() else "Off"),
                 depress=is_strip_on())
    col = layout.column(align=True)
    if hist is None or not hist.snaps:
        col.label(text="No snapshots yet")
    else:
        lanes = hist.lanes()
        for sid in sorted(hist.snaps, reverse=True)[:25]:
            snap = hist.snaps[sid]
            r = col.row(align=True)
            indent = lanes[sid][1]
            if indent:
                r.label(text="", icon='BLANK1')
            label = ("● " if sid == hist.head else "") + snap.label + (" (auto)" if snap.auto else "")
            op = r.operator("sculpt_helper.history_select", text=label,
                            depress=sid == hist.selected, emboss=sid == hist.selected)
            op.sid = sid
        if len(hist.snaps) > 25:
            col.label(text=f"…and {len(hist.snaps) - 25} older (see the timeline)")
    box = layout.column(align=True)
    box.label(text="Selected snapshot")
    row = box.row(align=True)
    row.operator("sculpt_helper.history_jump", text="Jump", icon='LOOP_BACK')
    row.operator("sculpt_helper.history_paint_back", text="Paint Back")
    row.operator("sculpt_helper.history_delete", text="", icon='TRASH')
    box.prop(settings, "history_blend", slider=True, text="Blend to Selected")
    layout.separator()
    col = layout.column(align=True)
    col.label(text="Morph Target Brush")
    col.row().prop(settings, "morph_target", expand=True)
    col.prop(settings, "morph_brush_strength", slider=True)
    col.operator("sculpt_helper.morph_brush", icon='BRUSH_DATA')
    layout.separator()
    col = layout.column(align=True)
    col.prop(settings, "history_auto")
    sub = col.column(align=True)
    sub.active = settings.history_auto
    sub.prop(settings, "history_every")
    col.prop(settings, "history_max")
    col.prop(settings, "history_keep_in_file")
    if obj is not None and hist is not None and hist.snaps:
        col.operator("sculpt_helper.history_clear", icon='X')


classes = (
    SCULPT_HELPER_OT_history_snapshot,
    SCULPT_HELPER_OT_history_select,
    SCULPT_HELPER_OT_history_jump,
    SCULPT_HELPER_OT_history_paint_back,
    SCULPT_HELPER_OT_history_delete,
    SCULPT_HELPER_OT_history_clear,
    SCULPT_HELPER_OT_morph_brush,
    SCULPT_HELPER_OT_history_timeline,
)

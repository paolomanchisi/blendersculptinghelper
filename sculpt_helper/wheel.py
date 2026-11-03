# SPDX-License-Identifier: GPL-3.0-or-later
"""Custom-drawn brush wheel (Q).

A ring of brush thumbnails around the cursor, the hovered brush named in the
centre. Click a brush, or let go of Q while pointing at one, to pick it.
Right-click or Esc closes. Any number of brushes fits: the ring grows a
second row when there are more than twelve. The native pie stays available
(Preferences > Use Custom Wheel off).
"""

import math
import os

import bpy

from . import utils

ESSENTIALS_FILE = "essentials_brushes-mesh_sculpt.blend"


# ---------------------------------------------------------------------------
# Geometry (pure; tested)


def layout(names, scale=1.0):
    """Slot centres relative to the wheel centre: list of (name, x, y, size)."""
    per_ring = 12
    slots = []
    rings = [names[i:i + per_ring] for i in range(0, len(names), per_ring)]
    for r, ring_names in enumerate(rings):
        radius = (100 + 70 * r) * scale
        size = 46 * scale
        n = len(ring_names)
        for i, name in enumerate(ring_names):
            a = math.pi / 2 - 2 * math.pi * i / max(n, 1)  # start at the top, clockwise
            slots.append((name, radius * math.cos(a), radius * math.sin(a), size))
    return slots


def hit(slots, dx, dy, inner_radius):
    """Index of the slot under (dx, dy) relative to the centre, or None."""
    if math.hypot(dx, dy) < inner_radius:
        return None
    best, best_d = None, None
    for i, (_n, x, y, size) in enumerate(slots):
        d = math.hypot(dx - x, dy - y)
        if d < size * 0.9 and (best_d is None or d < best_d):
            best, best_d = i, d
    if best is not None:
        return best
    # Outside every thumbnail: pick by direction within the closest ring.
    r = math.hypot(dx, dy)
    ring_slots = [i for i, s in enumerate(slots) if abs(math.hypot(s[1], s[2]) - r) < 45 * (s[3] / 46)]
    if not ring_slots:
        return None
    ang = math.atan2(dy, dx)
    return min(ring_slots, key=lambda i: abs(math.remainder(ang - math.atan2(slots[i][2], slots[i][1]),
                                                             2 * math.pi)))


# ---------------------------------------------------------------------------
# Brush thumbnails

_textures = {}


def essentials_path():
    return os.path.join(bpy.utils.system_resource('DATAFILES'), "assets", "brushes", ESSENTIALS_FILE)


def ensure_linked(names):
    path = essentials_path()
    missing = [n for n in names if _find_brush(n) is None]
    if not missing or not os.path.exists(path):
        return
    with bpy.data.libraries.load(path, link=True, assets_only=True) as (src, dst):
        dst.brushes = [n for n in missing if n in src.brushes]


def _find_brush(name):
    for b in bpy.data.brushes:
        if b.name == name and b.library and b.library.filepath.endswith(ESSENTIALS_FILE):
            return b
    return None


def thumbnail(name):
    from . import gpu_draw
    if name in _textures:
        return _textures[name]
    brush = _find_brush(name)
    tex = None
    if brush is not None:
        try:
            tex = gpu_draw.preview_texture(brush.preview_ensure())
        except Exception:  # noqa: BLE001 - a missing preview just shows a label
            tex = None
    _textures[name] = tex
    return tex


def clear_cache():
    _textures.clear()


# ---------------------------------------------------------------------------
# Operator


class SCULPT_HELPER_OT_brush_wheel(bpy.types.Operator):
    bl_idname = "sculpt_helper.brush_wheel"
    bl_label = "Brush Wheel"
    bl_description = "Pick a brush from a wheel of thumbnails around the cursor"

    @classmethod
    def poll(cls, context):
        return utils.in_sculpt_mode(context)

    def invoke(self, context, event):
        prefs = utils.addon_prefs(context)
        from .menus import brush_favorites
        if prefs is not None and not prefs.use_custom_wheel:
            bpy.ops.wm.call_menu_pie(name="SCULPT_HELPER_MT_brush_pie")
            return {'FINISHED'}
        self._names = brush_favorites(context)
        if not self._names:
            return {'CANCELLED'}
        try:
            ensure_linked(self._names)
        except Exception:  # noqa: BLE001
            pass
        from . import gpu_draw
        self._scale = gpu_draw.ui_scale()
        self._key = event.type
        self._centre = (event.mouse_region_x, event.mouse_region_y)
        self._slots = layout(self._names, self._scale)
        self._hover = None
        self._moved = False
        ref = context.tool_settings.sculpt.brush_asset_reference
        self._current = ref.relative_asset_identifier.rsplit("/Brush/", 1)[-1] if ref else ""
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _close(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        context.area.tag_redraw()

    def _pick(self, context):
        if self._hover is None:
            return False
        utils.activate_essential_brush(self._names[self._hover])
        return True

    def modal(self, context, event):
        context.area.tag_redraw()
        dx = event.mouse_region_x - self._centre[0]
        dy = event.mouse_region_y - self._centre[1]
        if event.type == 'MOUSEMOVE':
            self._hover = hit(self._slots, dx, dy, 40 * self._scale)
            if math.hypot(dx, dy) > 30 * self._scale:
                self._moved = True
            return {'RUNNING_MODAL'}
        if event.type == self._key and event.value == 'RELEASE':
            if self._moved and self._hover is not None:
                self._pick(context)
                self._close(context)
                return {'FINISHED'}
            return {'RUNNING_MODAL'}  # tap: keep the wheel open for clicking
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._pick(context)
            self._close(context)
            return {'FINISHED'}
        if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._close(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def _draw(self):
        from . import gpu_draw as g
        s = self._scale
        cx, cy = self._centre
        outer = max(math.hypot(x, y) for _n, x, y, _s in self._slots) + 40 * s
        g.ring(cx, cy, 40 * s, outer, (0.10, 0.11, 0.13, 0.82))
        g.disc(cx, cy, 38 * s, (0.16, 0.17, 0.20, 0.95))
        for i, (name, x, y, size) in enumerate(self._slots):
            px, py = cx + x, cy + y
            current = name == self._current
            hovered = i == self._hover
            if hovered or current:
                g.disc(px, py, size * 0.62, g.ACCENT if hovered else (0.90, 0.62, 0.20, 1.0))
            g.disc(px, py, size * 0.55, (0.22, 0.23, 0.27, 1.0))
            tex = thumbnail(name)
            if tex is not None:
                half = size * 0.45
                g.texture(tex, px - half, py - half, half * 2, half * 2)
            else:
                g.text(px, py - 4 * s, name.split("/")[0][:2], 12, g.TEXT, align='CENTER')
            g.text(px, py - size * 0.55 - 13 * s, name.split("/")[0], 10,
                   g.TEXT if hovered else g.TEXT_DIM, align='CENTER', max_width=size * 1.8)
        label = self._names[self._hover] if self._hover is not None else self._current
        g.text(cx, cy - 4 * s, label.split("/")[0], 12, g.TEXT, align='CENTER', max_width=70 * s)
        g.text(cx, cy - outer - 16 * s, "Right-click to close", 10, g.TEXT_DIM, align='CENTER')


classes = (SCULPT_HELPER_OT_brush_wheel,)

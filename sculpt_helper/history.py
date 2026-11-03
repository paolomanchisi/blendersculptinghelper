# SPDX-License-Identifier: GPL-3.0-or-later
"""History timeline: mesh snapshots with branches.

Snapshots are taken automatically every N strokes and by hand. Each one
remembers its parent, so going back and sculpting starts a branch instead of
throwing later states away. From any snapshot you can:

* Jump back to it (restores the whole mesh, even after a remesh),
* Blend between it and the current shape with a slider,
* Paint it back where you mask, or with the Morph Target brush.

Snapshots live in memory (they survive undo, which Blender's own undo
history doesn't). With "Keep in File" on they are also written into the
.blend when you save and read back when you open it.
"""

import time

import bmesh
import bpy
import numpy as np
from bpy.app.handlers import persistent

from . import meshdata as md

ID_PROP = "sculpt_helper_history_id"
FILE_PREFIX = ".SH History "


class Snapshot:
    __slots__ = ("id", "parent", "label", "time", "auto", "positions", "bm", "thumb")

    def __init__(self, sid, parent, label, positions, bm, auto):
        self.id = sid
        self.parent = parent
        self.label = label
        self.time = time.time()
        self.auto = auto
        self.positions = positions
        self.bm = bm
        self.thumb = None  # GPUTexture, drawn by the timeline when available


class History:
    def __init__(self):
        self.snaps = {}
        self.head = None      # snapshot the current mesh descends from
        self.selected = None  # snapshot the panel / timeline acts on
        self.next_id = 1
        self.strokes = 0
        self.pending_thumb = None

    # -- tree -------------------------------------------------------------

    def add(self, positions, bm, label=None, auto=False):
        sid = self.next_id
        self.next_id += 1
        snap = Snapshot(sid, self.head, label or f"#{sid}", positions, bm, auto)
        self.snaps[sid] = snap
        self.head = sid
        self.selected = sid
        return snap

    def children(self, sid):
        return [s.id for s in self.snaps.values() if s.parent == sid]

    def remove(self, sid):
        snap = self.snaps.pop(sid, None)
        if snap is None:
            return
        for s in self.snaps.values():
            if s.parent == sid:
                s.parent = snap.parent
        if snap.bm is not None:
            snap.bm.free()
        snap.thumb = None
        if self.head == sid:
            self.head = snap.parent
        if self.selected == sid:
            self.selected = self.head

    def ancestors(self, sid):
        out = []
        while sid is not None and sid in self.snaps:
            out.append(sid)
            sid = self.snaps[sid].parent
        return out

    def trim(self, limit):
        """Drop the oldest snapshots that aren't the head or its ancestors'
        newest ones until at most ``limit`` remain."""
        protected = {self.head, self.selected}
        while len(self.snaps) > max(limit, 1):
            candidates = [s for s in sorted(self.snaps) if s not in protected]
            if not candidates:
                return
            self.remove(candidates[0])

    def lanes(self):
        """Lay out the tree for drawing: {id: (column, lane)}. Columns follow
        creation order; a snapshot's first child stays in its lane, later
        children (branches) get new lanes."""
        out, next_lane = {}, [0]
        for sid in sorted(self.snaps):
            snap = self.snaps[sid]
            if snap.parent is None or snap.parent not in out:
                lane = next_lane[0]
                next_lane[0] += 1
            else:
                siblings = sorted(self.children(snap.parent))
                if siblings and siblings[0] == sid:
                    lane = out[snap.parent][1]
                else:
                    lane = next_lane[0]
                    next_lane[0] += 1
            out[sid] = (len(out), lane)
        return out

    def clear(self):
        for s in self.snaps.values():
            if s.bm is not None:
                s.bm.free()
        self.snaps.clear()
        self.head = self.selected = None


_histories = {}


def history_for(obj, create=True):
    key = obj.get(ID_PROP)
    if key is None:
        if not create:
            return None
        key = f"{obj.name}-{int(time.time() * 1000) % 100000000}"
        obj[ID_PROP] = key
    if key not in _histories:
        if not create:
            return None
        _histories[key] = History()
    return _histories[key]


# ---------------------------------------------------------------------------
# Taking and using snapshots


def capture(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    return md.get_positions(mesh).copy(), bm


def take_snapshot(context, obj, label=None, auto=False):
    settings = context.scene.sculpt_helper
    hist = history_for(obj)
    with md.object_mode(context) as mesh:
        positions, bm = capture(mesh)
    snap = hist.add(positions, bm, label, auto)
    hist.trim(settings.history_max)
    hist.pending_thumb = snap.id  # the timeline renders it on its next draw
    hist.strokes = 0
    _blend_base.pop(obj.name, None)
    return snap


def jump_to(context, obj, sid):
    hist = history_for(obj)
    snap = hist.snaps[sid]
    with md.object_mode(context) as mesh:
        snap.bm.to_mesh(mesh)
        mesh.update()
    hist.head = sid
    hist.selected = sid
    _blend_base.pop(obj.name, None)


def compatible(mesh, snap):
    return snap is not None and len(snap.positions) == len(mesh.vertices)


def paint_back(context, obj, sid, strength=1.0):
    """Restore the snapshot's shape where the mask is (like Morph)."""
    snap = history_for(obj).snaps[sid]
    with md.object_mode(context) as mesh:
        if not compatible(mesh, snap):
            return False
        weight = md.get_mask(mesh) * ~md.get_hidden(mesh)
        pos = md.get_positions(mesh)
        w = np.clip(weight * strength, 0, 1)[:, None]
        md.set_positions(mesh, pos + (snap.positions - pos) * w)
    return True


_blend_base = {}  # object name -> positions when blending started


def blend(context, obj, sid, factor):
    """Blend between the shape before blending started and the snapshot."""
    snap = history_for(obj).snaps[sid]
    with md.object_mode(context) as mesh:
        if not compatible(mesh, snap):
            return False
        base = _blend_base.get(obj.name)
        if base is None or len(base) != len(mesh.vertices):
            base = md.get_positions(mesh).copy()
            _blend_base[obj.name] = base
        md.set_positions(mesh, base + (snap.positions - base) * factor)
    return True


def end_blend(obj):
    _blend_base.pop(obj.name, None)


# ---------------------------------------------------------------------------
# Auto snapshots: count strokes, snapshot every N


_watch = {"stroking": False}


def _view3d(win):
    for area in win.screen.areas:
        if area.type == 'VIEW_3D':
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            return area, region
    return None, None


def _watcher():
    context = bpy.context
    scene = context.scene
    if scene is None or not scene.sculpt_helper.history_auto:
        _watch["stroking"] = False
        return None
    for win in context.window_manager.windows:
        running = any(op.bl_idname == "SCULPT_OT_brush_stroke" for op in win.modal_operators)
        if running:
            _watch["stroking"] = True
            return 0.05
        if _watch["stroking"]:
            _watch["stroking"] = False
            obj = context.view_layer.objects.active
            if obj is None or obj.type != 'MESH':
                return 0.2
            end_blend(obj)
            hist = history_for(obj)
            hist.strokes += 1
            if not hist.snaps or hist.strokes >= scene.sculpt_helper.history_every:
                area, region = _view3d(win)
                if area is not None:
                    with context.temp_override(window=win, area=area, region=region):
                        if context.mode == 'SCULPT':
                            take_snapshot(context, obj, auto=True)
    return 0.2


def auto_update(self, context):
    if self.history_auto and not bpy.app.timers.is_registered(_watcher):
        bpy.app.timers.register(_watcher, first_interval=0.2)


# ---------------------------------------------------------------------------
# Keep in file


@persistent
def save_pre(_dummy):
    for mesh in [m for m in bpy.data.meshes if m.name.startswith(FILE_PREFIX)]:
        bpy.data.meshes.remove(mesh)
    scene = bpy.context.scene
    if scene is None or not scene.sculpt_helper.history_keep_in_file:
        return
    for obj in bpy.data.objects:
        key = obj.get(ID_PROP)
        hist = _histories.get(key) if key else None
        if hist is None:
            continue
        for snap in hist.snaps.values():
            mesh = bpy.data.meshes.new(f"{FILE_PREFIX}{key} {snap.id}")
            snap.bm.to_mesh(mesh)
            mesh.use_fake_user = True
            mesh["sh_key"] = key
            mesh["sh_id"] = snap.id
            mesh["sh_parent"] = -1 if snap.parent is None else snap.parent
            mesh["sh_label"] = snap.label
            mesh["sh_auto"] = snap.auto
            mesh["sh_time"] = snap.time
            mesh["sh_head"] = hist.head == snap.id


@persistent
def save_post(_dummy):
    # The stored copies only need to exist inside the saved file.
    for mesh in [m for m in bpy.data.meshes if m.name.startswith(FILE_PREFIX)]:
        bpy.data.meshes.remove(mesh)


@persistent
def load_post(_dummy):
    for h in _histories.values():
        h.clear()
    _histories.clear()
    _blend_base.clear()
    stored = sorted((m for m in bpy.data.meshes if m.name.startswith(FILE_PREFIX)),
                    key=lambda m: (m.get("sh_key", ""), m.get("sh_id", 0)))
    for mesh in stored:
        key = mesh.get("sh_key")
        hist = _histories.setdefault(key, History())
        positions, bm = capture(mesh)
        sid = int(mesh.get("sh_id", hist.next_id))
        parent = int(mesh.get("sh_parent", -1))
        snap = Snapshot(sid, None if parent < 0 else parent, mesh.get("sh_label", f"#{sid}"),
                        positions, bm, bool(mesh.get("sh_auto", False)))
        snap.time = float(mesh.get("sh_time", time.time()))
        hist.snaps[sid] = snap
        hist.next_id = max(hist.next_id, sid + 1)
        if mesh.get("sh_head"):
            hist.head = hist.selected = sid
    for mesh in stored:
        bpy.data.meshes.remove(mesh)
    scene = bpy.context.scene
    if scene is not None and scene.sculpt_helper.history_auto:
        auto_update(scene.sculpt_helper, bpy.context)


def _start_watcher():
    scene = bpy.context.scene
    if scene is not None and scene.sculpt_helper.history_auto:
        auto_update(scene.sculpt_helper, bpy.context)
    return None


def register():
    bpy.app.handlers.save_pre.append(save_pre)
    bpy.app.handlers.save_post.append(save_post)
    bpy.app.handlers.load_post.append(load_post)
    bpy.app.timers.register(_start_watcher, first_interval=0.5)


def unregister():
    for handlers, fn in ((bpy.app.handlers.save_pre, save_pre),
                         (bpy.app.handlers.save_post, save_post),
                         (bpy.app.handlers.load_post, load_post)):
        if fn in handlers:
            handlers.remove(fn)
    if bpy.app.timers.is_registered(_watcher):
        bpy.app.timers.unregister(_watcher)
    for h in _histories.values():
        h.clear()
    _histories.clear()

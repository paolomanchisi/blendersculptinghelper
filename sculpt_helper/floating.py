# SPDX-License-Identifier: GPL-3.0-or-later
"""Floating panels: custom-drawn cards you can place anywhere in the viewport.

Start them from the S popup or the sidebar ("Floating Panels"). A tab bar on
the right edge opens and closes cards. Drag a card by its header; the header
buttons collapse it, show help (?), open the full sidebar panel as a popup
(≡) and close it (×). Cards only appear in the viewport they were started
in, and only in Sculpt Mode. Everything outside the cards behaves as usual.

Card contents are the most used controls of each sidebar panel; the full
panel is always one click away (≡).
"""

import json

import bpy

from . import panels, utils

TAB_LABELS = {
    "BRUSH": "Brush", "MASK_HIDE": "Mask", "VIEW_MODE": "View", "DEFORM": "Deform",
    "FACE_SETS": "Face Sets", "VERTEX_COLOR": "Color", "MATERIAL": "Material",
    "MULTIRES": "Multires", "LAYERS": "Layers", "EXTRACT": "Extract", "REMESH": "Remesh",
    "BOOLEAN": "Boolean", "HISTORY": "History",
}


# ---------------------------------------------------------------------------
# Widgets


class Button:
    def __init__(self, label, op, props=None, invoke=False):
        self.label, self.op, self.props, self.invoke = label, op, props or {}, invoke

    def active(self, context):
        return False

    def act(self, context, frac=None):
        mod, name = self.op.split(".")
        fn = getattr(getattr(bpy.ops, mod), name)
        try:
            if self.invoke:
                fn('INVOKE_DEFAULT', **self.props)
            else:
                fn(**self.props)
        except RuntimeError as exc:
            print("Sculpt Helper:", exc)


class Toggle:
    def __init__(self, label, owner, prop):
        self.label, self.owner, self.prop = label, owner, prop

    def active(self, context):
        o = self.owner(context)
        return bool(o is not None and getattr(o, self.prop))

    def act(self, context, frac=None):
        o = self.owner(context)
        if o is not None:
            setattr(o, self.prop, not getattr(o, self.prop))


class Choice:
    """One value of an enum property, shown as a button that stays pressed."""

    def __init__(self, label, owner, prop, value):
        self.label, self.owner, self.prop, self.value = label, owner, prop, value

    def active(self, context):
        o = self.owner(context)
        return o is not None and getattr(o, self.prop) == self.value

    def act(self, context, frac=None):
        o = self.owner(context)
        if o is not None:
            setattr(o, self.prop, self.value)


class Slider:
    draggable = True

    def __init__(self, label, owner, prop, lo, hi, fmt="{:.2f}"):
        self.label, self.owner, self.prop, self.lo, self.hi, self.fmt = label, owner, prop, lo, hi, fmt

    def active(self, context):
        return False

    def value(self, context):
        o = self.owner(context)
        return getattr(o, self.prop) if o is not None else self.lo

    def fraction(self, context):
        return (self.value(context) - self.lo) / ((self.hi - self.lo) or 1)

    def act(self, context, frac=None):
        o = self.owner(context)
        if o is None or frac is None:
            return
        v = self.lo + max(0.0, min(1.0, frac)) * (self.hi - self.lo)
        current = getattr(o, self.prop)
        setattr(o, self.prop, int(round(v)) if isinstance(current, int) else v)

    def text(self, context):
        return f"{self.label} {self.fmt.format(self.value(context))}"


class Label:
    def __init__(self, label):
        self.label = label

    def active(self, context):
        return False

    def act(self, context, frac=None):
        pass


# ---------------------------------------------------------------------------
# Owners


def _paint(context):
    return context.tool_settings.sculpt


def _size_owner(context):
    p = _paint(context)
    ups = p.unified_paint_settings
    return ups if ups.use_unified_size or p.brush is None else p.brush


def _strength_owner(context):
    p = _paint(context)
    ups = p.unified_paint_settings
    return ups if ups.use_unified_strength or p.brush is None else p.brush


def _automask(context):
    return _paint(context).mesh_automasking_settings


def _mesh(context):
    obj = context.active_object
    return obj.data if obj is not None and obj.type == 'MESH' else None


def _overlay(context):
    space = context.space_data
    return space.overlay if space is not None and space.type == 'VIEW_3D' else None


def _shading(context):
    space = context.space_data
    return space.shading if space is not None and space.type == 'VIEW_3D' else None


def _settings(context):
    return context.scene.sculpt_helper


def _multires(context):
    obj = context.active_object
    return next((m for m in obj.modifiers if m.type == 'MULTIRES'), None) if obj else None


# ---------------------------------------------------------------------------
# Card contents: id -> function(context) -> rows of widgets


def _mask_flood(label, mode, value=0.0):
    return Button(label, "paint.mask_flood_fill", {"mode": mode, "value": value})


def _mask_filter(label, ftype):
    return Button(label, "sculpt.mask_filter", {"filter_type": ftype, "auto_iteration_count": True})


def _deform(label, ftype, sign=1.0):
    return Button(label, "sculpt_helper.deform_filter", {"type": ftype, "sign": sign})


def card_brush(context):
    return [
        [Slider("Radius", _size_owner, "size", 1, 500, "{:d}px")],
        [Slider("Strength", _strength_owner, "strength", 0.0, 1.0, "{:.2f}")],
        [Toggle("Front", _automask, "use_automasking_view_normal"),
         Toggle("Topology", _automask, "use_automasking_topology"),
         Toggle("Face Set", _automask, "use_automasking_face_sets")],
        [Toggle("Boundary", _automask, "use_automasking_boundary_edges"),
         Toggle("Cavity", _automask, "use_automasking_cavity"),
         Button("Thickness", "sculpt_helper.thickness_protect")],
        [Button("Brush Wheel", "sculpt_helper.brush_wheel", invoke=True)],
    ]


def card_mask(context):
    return [
        [_mask_flood("Invert", 'INVERT'), _mask_flood("Clear", 'VALUE', 0.0)],
        [_mask_filter("Blur", 'SMOOTH'), _mask_filter("Sharpen", 'SHARPEN')],
        [_mask_filter("Grow", 'GROW'), _mask_filter("Shrink", 'SHRINK')],
        [Button("Show All", "paint.hide_show_all", {"action": 'SHOW'}),
         Button("Invert Vis.", "paint.visibility_invert")],
        [Button("Hide Masked", "paint.hide_show_masked", {"action": 'HIDE'}),
         Button("Show Masked", "paint.hide_show_masked", {"action": 'SHOW'})],
        [Button("Save Mask…", "sculpt_helper.mask_save", invoke=True)],
    ]


def card_view(context):
    return [
        [Toggle("X", _mesh, "use_mirror_x"), Toggle("Y", _mesh, "use_mirror_y"),
         Toggle("Z", _mesh, "use_mirror_z")],
        [Button("Symmetrize", "sculpt.symmetrize")],
        [Toggle("Mask", _overlay, "show_sculpt_mask"),
         Toggle("Face Sets", _overlay, "show_sculpt_face_sets"),
         Toggle("Wire", _overlay, "show_wireframes")],
        [Button("Dyntopo On/Off", "sculpt.dynamic_topology_toggle")],
    ]


def card_deform(context):
    return [
        [Slider("Strength", _settings, "deform_strength", 0.0, 2.0)],
        [_deform("Smooth", 'SMOOTH'), _deform("Inflate", 'INFLATE'),
         _deform("Deflate", 'INFLATE', -1.0)],
        [_deform("Expand", 'SCALE'), _deform("Shrink", 'SCALE', -1.0), _deform("Sphere", 'SPHERE')],
        [Button("Pivot Bend", "sculpt_helper.pivot_bend", invoke=True),
         Button("Gizmo", "sculpt_helper.gizmo_transform", {"pivot": 'UNMASKED'})],
        [Button("Record Shape", "sculpt_helper.shape_record"),
         Button("Morph", "sculpt_helper.morph", {"invert": False})],
    ]


def card_face_sets(context):
    return [
        [Button("From Mask", "sculpt.face_sets_create", {"mode": 'MASKED'}),
         Button("From Visible", "sculpt.face_sets_create", {"mode": 'VISIBLE'})],
        [Button("Loose Parts", "sculpt.face_sets_init", {"mode": 'LOOSE_PARTS'}),
         Button("Normals", "sculpt.face_sets_init", {"mode": 'NORMALS'})],
        [Button("New Colors", "sculpt.face_sets_randomize_colors"),
         Button("Show All", "paint.hide_show_all", {"action": 'SHOW'})],
    ]


def card_color(context):
    return [
        [Button("Paint Brush", "brush.asset_activate",
                {"asset_library_type": 'ESSENTIALS',
                 "relative_asset_identifier": utils.ESSENTIALS_SCULPT + "Paint Hard"}),
         Button("Fill", "sculpt_helper.color_fill")],
    ]


def card_material(context):
    return [
        [Choice("MatCap", _shading, "light", 'MATCAP'), Choice("Studio", _shading, "light", 'STUDIO'),
         Choice("Flat", _shading, "light", 'FLAT')],
        [Toggle("Cavity", _shading, "show_cavity")],
        [Button("Assign to Masked", "sculpt_helper.material_assign_masked")],
    ]


def card_multires(context):
    mod = _multires(context)
    rows = [[Button("Subdivide", "sculpt_helper.multires_subdivide", {"mode": 'CATMULL_CLARK'}),
             Button("Simple", "sculpt_helper.multires_subdivide", {"mode": 'SIMPLE'})]]
    if mod is not None:
        rows.append([Button("Level −", "sculpt_helper.multires_level", {"delta": -1}),
                     Label(f"{mod.sculpt_levels} / {mod.total_levels}"),
                     Button("Level +", "sculpt_helper.multires_level", {"delta": 1})])
        rows.append([Toggle("Link Levels", _settings, "multires_link_levels")])
    return rows


def card_layers(context):
    obj = context.active_object
    rows = [[Button("Add Layer", "sculpt_helper.layer_add"),
             Button("Update", "sculpt_helper.layer_sync")]]
    for i, layer in enumerate(obj.sculpt_helper_layers if obj else ()):
        rows.append([Slider(("● " if i == obj.sculpt_helper_layer_recording else "") + layer.name,
                            (lambda c, i=i: c.active_object.sculpt_helper_layers[i]),
                            "strength", 0.0, 1.0)])
    if obj is not None and len(obj.sculpt_helper_layers):
        rows.append([Button("Apply All", "sculpt_helper.layer_apply_all")])
    return rows


def card_extract(context):
    return [
        [Button("Extract Mask", "sculpt.paint_mask_extract"),
         Button("Slice Mask", "sculpt.paint_mask_slice")],
    ]


def card_remesh(context):
    return [
        [Slider("Voxel", _mesh, "remesh_voxel_size", 0.001, 0.2, "{:.3f}")],
        [Button("Voxel Remesh", "object.voxel_remesh")],
        [Button("Remesh (Keep Detail)", "sculpt_helper.remesh_keep_detail")],
    ]


def card_boolean(context):
    return [
        [Button("Sphere", "sculpt_helper.boolean_add", {"shape": 'SPHERE'}),
         Button("Cube", "sculpt_helper.boolean_add", {"shape": 'CUBE'}),
         Button("Cylinder", "sculpt_helper.boolean_add", {"shape": 'CYLINDER'})],
        [Button("Confirm", "sculpt_helper.boolean_confirm"),
         Button("Cancel", "sculpt_helper.boolean_cancel")],
    ]


def card_history(context):
    return [
        [Button("+ Snapshot", "sculpt_helper.history_snapshot"),
         Button("Timeline", "sculpt_helper.history_timeline", invoke=True)],
        [Button("Jump", "sculpt_helper.history_jump"),
         Button("Paint Back", "sculpt_helper.history_paint_back")],
        [Slider("Blend", _settings, "history_blend", 0.0, 1.0)],
        [Button("Morph Target Brush", "sculpt_helper.morph_brush", invoke=True)],
    ]


CARDS = {
    "BRUSH": card_brush, "MASK_HIDE": card_mask, "VIEW_MODE": card_view,
    "DEFORM": card_deform, "FACE_SETS": card_face_sets, "VERTEX_COLOR": card_color,
    "MATERIAL": card_material, "MULTIRES": card_multires, "LAYERS": card_layers,
    "EXTRACT": card_extract, "REMESH": card_remesh, "BOOLEAN": card_boolean,
    "HISTORY": card_history,
}


# ---------------------------------------------------------------------------
# State (stored as JSON in the preferences)

DEFAULT_OPEN = ("VIEW_MODE", "BRUSH", "MASK_HIDE")


def load_state(prefs):
    try:
        state = json.loads(prefs.floating_state) if prefs and prefs.floating_state else {}
    except ValueError:
        state = {}
    state.setdefault("cards", {})
    return state


def save_state(prefs, state):
    if prefs is not None:
        prefs.floating_state = json.dumps(state)


def default_card(index, region_w, region_h, scale):
    w = 230 * scale
    return {"open": True, "collapsed": False,
            "x": region_w - w - 110 * scale, "y": region_h - 40 * scale - index * 210 * scale}


# ---------------------------------------------------------------------------
# Layout (pure; tested)


class Metrics:
    def __init__(self, scale):
        self.scale = scale
        self.width = 230 * scale
        self.header = 22 * scale
        self.row = 22 * scale
        self.pad = 5 * scale
        self.gap = 3 * scale
        self.tab_w = 78 * scale
        self.tab_h = 20 * scale


def layout_cards(state, rows_by_id, region_w, region_h, m):
    """Return (hits, cards) for the open cards.

    hits: list of (x, y, w, h, kind, card_id, payload) from top-most down.
    cards: list of (card_id, x, y_bottom, w, h, header_y) for drawing."""
    hits, cards = [], []
    for cid, card in state["cards"].items():
        if not card.get("open") or cid not in rows_by_id:
            continue
        x, top = card["x"], card["y"]
        rows = [] if card.get("collapsed") else rows_by_id[cid]
        body = len(rows) * (m.row + m.gap) + (m.pad * 2 if rows else 0)
        h = m.header + body
        y0 = top - h
        header_y = top - m.header
        cards.append((cid, x, y0, m.width, h, header_y))
        # Header buttons (right to left): close, more, help; then the drag area.
        bw = m.header
        for i, kind in enumerate(("close", "more", "help")):
            hits.append((x + m.width - bw * (i + 1), header_y, bw, m.header, kind, cid, None))
        hits.append((x, header_y, bw, m.header, "collapse", cid, None))
        hits.append((x + bw, header_y, m.width - bw * 4, m.header, "drag", cid, None))
        y = header_y - m.pad - m.row
        for row in rows:
            n = len(row)
            cw = (m.width - m.pad * 2 - m.gap * (n - 1)) / n
            for j, widget in enumerate(row):
                hits.append((x + m.pad + j * (cw + m.gap), y, cw, m.row, "widget", cid, widget))
            y -= m.row + m.gap
        hits.append((x, y0, m.width, h, "card", cid, None))
    return hits, cards


def layout_tabs(state, region_w, region_h, m):
    hits = []
    x = region_w - m.tab_w - 8 * m.scale
    y = region_h - 40 * m.scale
    hits.append((x, y, m.tab_w, m.tab_h * 1.4, "exit", None, None))
    y -= m.tab_h * 1.4 + 6 * m.scale
    for cid, _label in panels.PANELS:
        hits.append((x, y, m.tab_w, m.tab_h, "tab", cid, None))
        y -= m.tab_h + 2 * m.scale
    return hits


def find_hit(hits, px, py):
    for h in hits:
        x, y, w, hh = h[:4]
        if x <= px <= x + w and y <= py <= y + hh:
            return h
    return None


# ---------------------------------------------------------------------------
# Host operator

_running = {"on": False}


class SCULPT_HELPER_OT_floating_panels(bpy.types.Operator):
    bl_idname = "sculpt_helper.floating_panels"
    bl_label = "Floating Panels"
    bl_description = ("Show the Sculpt Helper panels as cards you can drag anywhere in this "
                      "viewport (run again to turn them off)")

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        if _running["on"]:
            _running["on"] = False
            return {'FINISHED'}
        from . import gpu_draw
        _running["on"] = True
        self._area = context.area
        self._region = next(r for r in context.area.regions if r.type == 'WINDOW')
        self._m = Metrics(gpu_draw.ui_scale())
        self._prefs = utils.addon_prefs(context)
        self._state = load_state(self._prefs)
        for i, cid in enumerate(DEFAULT_OPEN):
            if cid not in self._state["cards"]:
                self._state["cards"][cid] = default_card(i, self._region.width, self._region.height,
                                                         self._m.scale)
        self._hover = None
        self._drag = None      # ("card", cid, dx, dy) or ("slider", hit)
        self._hits = []
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self._area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _stop(self):
        _running["on"] = False
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        save_state(self._prefs, self._state)
        try:
            self._area.tag_redraw()
        except ReferenceError:
            pass
        return {'FINISHED'}

    def _active(self, context):
        return (context.mode == 'SCULPT' and context.active_object is not None
                and context.active_object.type == 'MESH')

    def _compute(self, context):
        rows = {}
        for cid, card in self._state["cards"].items():
            if card.get("open") and cid in CARDS:
                try:
                    rows[cid] = CARDS[cid](context)
                except Exception:  # noqa: BLE001 - a broken card must not stop the host
                    rows[cid] = [[Label("(unavailable)")]]
        hits, cards = layout_cards(self._state, rows, self._region.width, self._region.height, self._m)
        tabs = layout_tabs(self._state, self._region.width, self._region.height, self._m)
        self._hits, self._cards = hits + tabs, cards
        return self._hits

    def modal(self, context, event):
        if not _running["on"]:
            return self._stop()
        try:
            self._area.tag_redraw()
        except ReferenceError:
            return self._stop()
        if not self._active(context):
            return {'PASS_THROUGH'}

        px = event.mouse_x - self._region.x
        py = event.mouse_y - self._region.y
        inside = 0 <= px <= self._region.width and 0 <= py <= self._region.height

        if self._drag is not None:
            kind = self._drag[0]
            if event.type == 'MOUSEMOVE':
                if kind == "card":
                    _k, cid, dx, dy = self._drag
                    self._state["cards"][cid]["x"] = px - dx
                    self._state["cards"][cid]["y"] = py - dy
                else:
                    x, _y, w = self._drag[1][:3]
                    self._drag[1][6].act(context, (px - x) / w)
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self._drag = None
                save_state(self._prefs, self._state)
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}

        if not inside:
            return {'PASS_THROUGH'}
        hit = find_hit(self._compute(context), px, py)
        self._hover = hit
        if hit is None:
            return {'PASS_THROUGH'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._click(context, hit, px, py)
            return {'RUNNING_MODAL'}
        if event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'RUNNING_MODAL'}  # don't sculpt or rotate through a card
        return {'PASS_THROUGH'}

    def _click(self, context, hit, px, py):
        x, y, w, h, kind, cid, widget = hit
        cards = self._state["cards"]
        if kind == "exit":
            _running["on"] = False
        elif kind == "tab":
            card = cards.get(cid)
            if card is None:
                index = len([c for c in cards.values() if c.get("open")])
                cards[cid] = default_card(index % 4, self._region.width, self._region.height,
                                          self._m.scale)
            else:
                card["open"] = not card.get("open")
        elif kind == "close":
            cards[cid]["open"] = False
        elif kind == "collapse":
            cards[cid]["collapsed"] = not cards[cid].get("collapsed")
        elif kind == "help":
            bpy.ops.sculpt_helper.panel_help('INVOKE_DEFAULT', panel=cid)
        elif kind == "more":
            bpy.ops.wm.call_panel(name=f"SCULPT_HELPER_PT_{cid.lower()}", keep_open=True)
        elif kind == "drag":
            self._drag = ("card", cid, px - cards[cid]["x"], py - cards[cid]["y"])
        elif kind == "widget":
            if getattr(widget, "draggable", False):
                self._drag = ("slider", hit)
                widget.act(context, (px - x) / w)
            else:
                widget.act(context)
        save_state(self._prefs, self._state)

    # -- drawing ----------------------------------------------------------

    def _draw(self):
        context = bpy.context
        if context.area != self._area or not self._active(context):
            return
        from . import gpu_draw as g
        m = self._m
        self._compute(context)
        hover = self._hover
        for cid, x, y0, w, h, header_y in self._cards:
            card = self._state["cards"][cid]
            g.rect(x, y0, w, h, g.BG)
            g.rect(x, header_y, w, m.header, g.HEADER_COLOURS.get(cid, g.ACCENT))
            g.text(x + m.header * 0.35, header_y + m.header * 0.3,
                   "▸" if card.get("collapsed") else "▾", 11)
            g.text(x + m.header * 1.1, header_y + m.header * 0.3,
                   dict(panels.PANELS).get(cid, cid), 11)
            for i, glyph in enumerate(("×", "≡", "?")):
                g.text(x + w - m.header * (i + 0.5), header_y + m.header * 0.3, glyph, 11,
                       align='CENTER')
        for hx, hy, hw, hh, kind, cid, widget in self._hits:
            if kind == "widget":
                hovered = hover is not None and hover[:4] == (hx, hy, hw, hh)
                self._draw_widget(g, widget, hx, hy, hw, hh, hovered, context)
            elif kind in {"tab", "exit"}:
                is_open = kind == "tab" and self._state["cards"].get(cid, {}).get("open")
                colour = g.HEADER_COLOURS.get(cid, g.ACCENT) if is_open else g.BUTTON
                if kind == "exit":
                    colour = g.ACCENT
                g.rect(hx, hy, hw, hh, colour)
                label = "SH  ON" if kind == "exit" else TAB_LABELS.get(cid, cid)
                g.text(hx + hw / 2, hy + hh * 0.3, label, 10, align='CENTER', max_width=hw - 4)

    def _draw_widget(self, g, widget, x, y, w, h, hovered, context):
        if isinstance(widget, Label):
            g.text(x + w / 2, y + h * 0.3, widget.label, 10, g.TEXT_DIM, align='CENTER')
            return
        try:
            on = widget.active(context)
        except Exception:  # noqa: BLE001
            on = False
        g.rect(x, y, w, h, g.ACCENT if on else (g.BUTTON_HOVER if hovered else g.BUTTON))
        if isinstance(widget, Slider):
            try:
                frac = max(0.0, min(1.0, widget.fraction(context)))
                label = widget.text(context)
            except Exception:  # noqa: BLE001
                frac, label = 0.0, widget.label
            g.rect(x, y, w * frac, h, (0.30, 0.45, 0.75, 0.9))
            g.text(x + 6, y + h * 0.3, label, 10, max_width=w - 8)
        else:
            g.text(x + w / 2, y + h * 0.3, widget.label, 10, align='CENTER', max_width=w - 6)


def is_running():
    return _running["on"]


classes = (SCULPT_HELPER_OT_floating_panels,)

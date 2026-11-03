# SPDX-License-Identifier: GPL-3.0-or-later
"""Sculpt Helper: hold keys, quick menus and helper tools for Sculpt Mode."""

import bpy

from bpy.app.handlers import persistent

from . import (history, history_ui, keymap, menus, ops_boolean, ops_gravity, ops_hold_isolate, ops_hold_mask,
               ops_layers, ops_masks, ops_material, ops_multi, ops_pivot, ops_shape, ops_stamp,
               ops_transfer, ops_transform, panels, prefs, props, ui, wheel, floating)

_modules = (props, prefs, ops_hold_mask, ops_hold_isolate, ops_masks, ops_shape,
            ops_gravity, ops_stamp, ops_material, ops_multi, ops_pivot, ops_layers,
            ops_transform, ops_transfer, ops_boolean, history_ui, ui, panels, menus, wheel, floating)


@persistent
def _on_load(_dummy):
    # Restart the Auto Depth Limit watcher for files saved with it on.
    scene = bpy.context.scene
    if scene is not None and scene.sculpt_helper.depth_limit_auto:
        ops_shape.depth_auto_update(scene.sculpt_helper, bpy.context)


def register():
    for mod in _modules:
        for cls in mod.classes:
            bpy.utils.register_class(cls)
    props.register()
    ops_layers.register()
    keymap.register()
    history.register()
    bpy.app.handlers.load_post.append(_on_load)


def unregister():
    floating._running["on"] = False
    wheel.clear_cache()
    history_ui._strip["on"] = False
    history.unregister()
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    ops_shape.unregister()
    ops_layers.unregister()
    keymap.unregister()
    props.unregister()
    for mod in reversed(_modules):
        for cls in reversed(mod.classes):
            bpy.utils.unregister_class(cls)

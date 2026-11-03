# SPDX-License-Identifier: GPL-3.0-or-later
"""Sculpt Helper: hold keys, quick menus and helper tools for Sculpt Mode."""

import bpy

from . import keymap, ops_hold_isolate, ops_hold_mask, prefs, ui

_modules = (prefs, ops_hold_mask, ops_hold_isolate, ui)


def register():
    for mod in _modules:
        for cls in mod.classes:
            bpy.utils.register_class(cls)
    keymap.register()


def unregister():
    keymap.unregister()
    for mod in reversed(_modules):
        for cls in reversed(mod.classes):
            bpy.utils.unregister_class(cls)

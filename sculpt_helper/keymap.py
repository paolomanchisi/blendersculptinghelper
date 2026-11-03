# SPDX-License-Identifier: GPL-3.0-or-later
"""Add-on keymap. Every entry is shown (and rebindable) in the preferences."""

import bpy

KEYMAP_NAME = "Sculpt"

# (operator idname, key, modifiers, properties, label)
DEFAULT_ITEMS = (
    ("sculpt_helper.hold_mask", 'C', {}, {}, "Hold: Mask brush"),
    ("sculpt_helper.hold_isolate", 'C', {"shift": True}, {}, "Hold: Isolate area / face set"),
    ("sculpt_helper.shortcut_list", 'F1', {}, {}, "Shortcut list"),
)

_addon_keymaps = []


def register():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:  # background mode without key configs
        return
    km = kc.keymaps.new(name=KEYMAP_NAME, space_type='EMPTY')
    for idname, key, mods, props, _label in DEFAULT_ITEMS:
        kmi = km.keymap_items.new(idname, key, 'PRESS', repeat=False, **mods)
        for name, value in props.items():
            setattr(kmi.properties, name, value)
        _addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in _addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _addon_keymaps.clear()


def find_user_items():
    """Yield (label, keymap, keymap item) from the user key config, so that
    edits made in the preferences are what we show and draw."""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user
    if kc is None:
        return
    km = kc.keymaps.get(KEYMAP_NAME)
    if km is None:
        return
    for idname, key, mods, _props, label in DEFAULT_ITEMS:
        for kmi in km.keymap_items:
            if kmi.idname == idname:
                yield label, km, kmi
                break


def conflicts():
    """Return {our kmi.idname: [other operator names]} sharing the same key in
    the Sculpt keymap of the active key config. Default Blender bindings that
    we intentionally replace (C = Clay Strips, Shift+C = Crease) are included
    so users know what they shadow."""
    result = {}
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user
    if kc is None:
        return result
    km = kc.keymaps.get(KEYMAP_NAME)
    if km is None:
        return result
    ours = [kmi for _l, _km, kmi in find_user_items()]
    for mine in ours:
        if not mine.active:
            continue
        for other in km.keymap_items:
            if other == mine or not other.active or other.idname.startswith("sculpt_helper."):
                continue
            if (other.type == mine.type and other.value == mine.value
                    and other.shift == mine.shift and other.ctrl == mine.ctrl
                    and other.alt == mine.alt and other.oskey == mine.oskey):
                result.setdefault(mine.idname, []).append(other.name or other.idname)
    return result

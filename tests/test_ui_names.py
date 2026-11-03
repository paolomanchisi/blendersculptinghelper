# SPDX-License-Identifier: GPL-3.0-or-later
"""Draw every panel, pie and popup into a recording layout and check that each
property, operator (and its arguments), menu and panel name exists in this
Blender version. Catches typos and API renames without needing a viewport.

    python tests/test_ui_names.py            # with `pip install bpy`
    blender -b --python tests/test_ui_names.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import addon_utils  # noqa: E402

errors = []


class RNAProxy:
    """Stands in for a struct that only exists with a UI (overlay, shading)."""

    def __init__(self, rna_type):
        self.bl_rna = rna_type.bl_rna

    def __getattr__(self, name):
        prop = self.bl_rna.properties.get(name)
        if prop is None:
            raise AttributeError(name)
        if prop.type == 'ENUM':
            return prop.default
        if prop.type == 'BOOLEAN':
            return prop.default
        return getattr(prop, "default", None)


class OpProps:
    def __init__(self, idname):
        self._idname = idname
        mod, name = idname.split(".")
        self._rna = getattr(getattr(bpy.ops, mod), name).get_rna_type()

    def __setattr__(self, key, value):
        if key.startswith("_"):
            return object.__setattr__(self, key, value)
        prop = self._rna.properties.get(key)
        if prop is None:
            errors.append(f"operator {self._idname} has no property '{key}'")
        elif prop.type == 'ENUM' and not prop.is_enum_flag and prop.enum_items \
                and value not in prop.enum_items.keys():
            errors.append(f"operator {self._idname}.{key}: '{value}' not in enum")


class Layout:
    def __getattr__(self, name):
        if name.startswith("template_") or name in {"label", "separator", "context_pointer_set"}:
            return lambda *a, **k: Layout()
        if name in {"row", "column", "box", "split", "grid_flow", "column_flow", "menu_pie"}:
            return lambda *a, **k: Layout()
        raise AttributeError(name)

    # Attributes UI code sets on layouts.
    active = enabled = alert = True
    scale_x = scale_y = 1.0
    use_property_split = use_property_decorate = False
    operator_context = 'INVOKE_DEFAULT'

    def prop(self, data, name, **kw):
        rna = getattr(data, "bl_rna", None)
        if rna is None or name not in rna.properties:
            errors.append(f"no property '{name}' on {getattr(rna, 'identifier', data)}")
        return Layout()

    def operator(self, idname, **kw):
        mod, name = idname.split(".")
        if not hasattr(getattr(bpy.ops, mod, None), name):
            errors.append(f"no operator {idname}")
            return type("Any", (), {"__setattr__": lambda *a: None})()
        try:
            OpProps(idname)._rna
        except KeyError:
            errors.append(f"no operator {idname}")
            return type("Any", (), {"__setattr__": lambda *a: None})()
        return OpProps(idname)

    def popover(self, panel, **kw):
        if not hasattr(bpy.types, panel):
            errors.append(f"no panel {panel}")

    def menu(self, menu, **kw):
        if not hasattr(bpy.types, menu):
            errors.append(f"no menu {menu}")


class Context:
    def __init__(self):
        self.space_data = type("Space", (), {})()
        self.space_data.overlay = RNAProxy(bpy.types.View3DOverlay)
        self.space_data.shading = RNAProxy(bpy.types.View3DShading)
        self.space_data.show_region_ui = True
        self.space_data.type = 'VIEW_3D'

    def __getattr__(self, name):
        return getattr(bpy.context, name)


addon_utils.enable("sculpt_helper", default_set=True, handle_error=None)
bpy.ops.mesh.primitive_uv_sphere_add()
bpy.ops.object.mode_set(mode='SCULPT')

from sculpt_helper import menus, panels  # noqa: E402

ctx = Context()
for pid, draw in panels.DRAW.items():
    try:
        draw(Layout(), ctx)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"panel {pid}: {type(exc).__name__}: {exc}")

# Multires branch with a modifier present.
bpy.context.active_object.modifiers.new("Multires", 'MULTIRES')
panels.draw_multires(Layout(), ctx)

for cls in menus.classes:
    if hasattr(cls, "draw"):
        try:
            cls.draw(type("Self", (), {"layout": Layout()})(), ctx)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{cls.__name__}: {type(exc).__name__}: {exc}")

for e in errors:
    print("FAIL", e)
print(f"{len(errors)} problem(s)")
sys.exit(1 if errors else 0)

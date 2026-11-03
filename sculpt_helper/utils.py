# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared helpers: hit testing, brush switching, overlay drawing."""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils

ESSENTIALS_SCULPT = "brushes/essentials_brushes-mesh_sculpt.blend/Brush/"

# Distance in pixels the mouse must travel before a press counts as a drag.
DRAG_THRESHOLD = 4


def addon_prefs(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def in_sculpt_mode(context):
    obj = context.active_object
    return (
        obj is not None
        and obj.type == 'MESH'
        and context.mode == 'SCULPT'
        and context.area is not None
        and context.area.type == 'VIEW_3D'
    )


def hit_active_object(context, coord):
    """Return True when the region-space ``coord`` lies over the active mesh."""
    region = context.region
    rv3d = context.region_data
    obj = context.active_object
    if region is None or rv3d is None or obj is None:
        return False
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    depsgraph = context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    inv = obj_eval.matrix_world.inverted()
    local_origin = inv @ origin
    local_dir = (inv.to_3x3() @ direction).normalized()
    try:
        hit, *_ = obj_eval.ray_cast(local_origin, local_dir)
    except RuntimeError:
        return False
    return hit


def dragged(start, current):
    return (abs(current[0] - start[0]) > DRAG_THRESHOLD
            or abs(current[1] - start[1]) > DRAG_THRESHOLD)


# ---------------------------------------------------------------------------
# Brush / tool state


def capture_brush_state(context):
    """Remember the active tool and brush so they can be restored later."""
    tool = context.workspace.tools.from_space_view3d_mode('SCULPT', create=False)
    ref = context.tool_settings.sculpt.brush_asset_reference
    brush = None
    if ref and ref.relative_asset_identifier:
        brush = (ref.asset_library_type, ref.asset_library_identifier,
                 ref.relative_asset_identifier)
    return {"tool": tool.idname if tool else None, "brush": brush}


def activate_brush(library_type, library_id, relative_id):
    kwargs = {"asset_library_type": library_type,
              "relative_asset_identifier": relative_id}
    if library_id:
        kwargs["asset_library_identifier"] = library_id
    try:
        bpy.ops.brush.asset_activate(**kwargs)
        return True
    except RuntimeError:
        return False


def activate_essential_brush(name):
    return activate_brush('ESSENTIALS', "", ESSENTIALS_SCULPT + name)


def restore_brush_state(state):
    if state.get("brush"):
        activate_brush(*state["brush"])
    tool = state.get("tool")
    if tool and tool != "builtin.brush":
        try:
            bpy.ops.wm.tool_set_by_id(name=tool, space_type='VIEW_3D')
        except RuntimeError:
            pass


def stroke_running(context):
    win = context.window
    if win is None:
        return False
    return any(op.bl_idname == "SCULPT_OT_brush_stroke"
               for op in win.modal_operators)


# ---------------------------------------------------------------------------
# Overlay drawing


def draw_polyline(points, color, closed=False, width=1.5):
    if len(points) < 2:
        return
    pts = list(points) + ([points[0]] if closed else [])
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": [(x, y, 0.0) for x, y in pts]})
    region = bpy.context.region
    gpu.state.blend_set('ALPHA')
    shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("lineWidth", width)
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def rect_points(a, b):
    return [(a[0], a[1]), (b[0], a[1]), (b[0], b[1]), (a[0], b[1])]


def in_region(context, coord):
    region = context.region
    return region is not None and 0 <= coord[0] < region.width and 0 <= coord[1] < region.height


def sculpting_mesh(context):
    """Like in_sculpt_mode, but without needing a 3D viewport (for operators
    that only touch object data)."""
    obj = context.active_object
    return obj is not None and obj.type == 'MESH' and context.mode == 'SCULPT'


def raycast_active(context, coord):
    """Ray-cast the active object at region ``coord``.

    Returns (location, normal, face_index) in object space, or None."""
    region = context.region
    rv3d = context.region_data
    obj = context.active_object
    if region is None or rv3d is None or obj is None:
        return None
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    obj_eval = obj.evaluated_get(context.evaluated_depsgraph_get())
    inv = obj_eval.matrix_world.inverted()
    try:
        hit, loc, normal, index = obj_eval.ray_cast(inv @ origin,
                                                    (inv.to_3x3() @ direction).normalized())
    except RuntimeError:
        return None
    return (loc, normal, index) if hit else None


def pixel_radius_to_object(context, coord, local_location, pixels):
    """Convert a screen radius at a surface point to object-space length."""
    obj = context.active_object
    world = obj.matrix_world @ local_location
    region, rv3d = context.region, context.region_data
    centre = view3d_utils.location_3d_to_region_2d(region, rv3d, world)
    if centre is None:
        return 0.0
    edge = view3d_utils.region_2d_to_location_3d(
        region, rv3d, (centre[0] + pixels, centre[1]), world)
    world_len = (edge - world).length
    scale = max(obj.matrix_world.to_scale())
    return world_len / scale if scale else world_len

# SPDX-License-Identifier: GPL-3.0-or-later
"""Small immediate-mode drawing helpers for the custom viewport UI."""

import math

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

# Colours (RGBA). Header colours follow the reference screenshots.
BG = (0.11, 0.12, 0.14, 0.96)
BUTTON = (0.21, 0.22, 0.25, 1.0)
BUTTON_HOVER = (0.29, 0.31, 0.35, 1.0)
ACCENT = (0.26, 0.50, 0.92, 1.0)
TEXT = (0.92, 0.93, 0.95, 1.0)
TEXT_DIM = (0.62, 0.65, 0.70, 1.0)
HEADER_COLOURS = {
    "BRUSH": (0.20, 0.42, 0.80, 1.0),
    "MASK_HIDE": (0.48, 0.30, 0.70, 1.0),
    "VIEW_MODE": (0.12, 0.55, 0.52, 1.0),
    "DEFORM": (0.82, 0.48, 0.15, 1.0),
    "FACE_SETS": (0.25, 0.58, 0.30, 1.0),
    "VERTEX_COLOR": (0.78, 0.28, 0.52, 1.0),
    "MATERIAL": (0.70, 0.58, 0.15, 1.0),
    "MULTIRES": (0.30, 0.62, 0.82, 1.0),
    "LAYERS": (0.45, 0.40, 0.82, 1.0),
    "EXTRACT": (0.80, 0.38, 0.25, 1.0),
    "REMESH": (0.15, 0.50, 0.55, 1.0),
    "BOOLEAN": (0.62, 0.28, 0.22, 1.0),
}

FONT = 0


def ui_scale():
    prefs = bpy.context.preferences
    return prefs.system.ui_scale if prefs else 1.0


def _uniform():
    return gpu.shader.from_builtin('UNIFORM_COLOR')


def rect(x, y, w, h, colour):
    shader = _uniform()
    verts = ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=((0, 1, 2), (0, 2, 3)))
    gpu.state.blend_set('ALPHA')
    shader.uniform_float("color", colour)
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def outline(x, y, w, h, colour):
    shader = _uniform()
    verts = ((x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y))
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": verts})
    gpu.state.blend_set('ALPHA')
    shader.uniform_float("color", colour)
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def disc(cx, cy, r, colour, segments=48):
    shader = _uniform()
    pts = [(cx, cy)] + [(cx + r * math.cos(a), cy + r * math.sin(a))
                        for a in (2 * math.pi * i / segments for i in range(segments + 1))]
    tris = [(0, i, i + 1) for i in range(1, segments + 1)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": pts}, indices=tris)
    gpu.state.blend_set('ALPHA')
    shader.uniform_float("color", colour)
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def ring(cx, cy, r_in, r_out, colour, segments=64):
    shader = _uniform()
    pts, tris = [], []
    for i in range(segments + 1):
        a = 2 * math.pi * i / segments
        c, s = math.cos(a), math.sin(a)
        pts += [(cx + r_in * c, cy + r_in * s), (cx + r_out * c, cy + r_out * s)]
    for i in range(segments):
        j = 2 * i
        tris += [(j, j + 1, j + 3), (j, j + 3, j + 2)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": pts}, indices=tris)
    gpu.state.blend_set('ALPHA')
    shader.uniform_float("color", colour)
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def text(x, y, string, size=11, colour=TEXT, align='LEFT', max_width=None):
    size = size * ui_scale()
    blf.size(FONT, size)
    if max_width is not None:
        while string and blf.dimensions(FONT, string)[0] > max_width:
            string = string[:-2] + "…" if len(string) > 2 else ""
    w, _h = blf.dimensions(FONT, string)
    if align == 'CENTER':
        x -= w / 2
    elif align == 'RIGHT':
        x -= w
    blf.position(FONT, x, y, 0)
    blf.color(FONT, *colour)
    blf.draw(FONT, string)


def texture(tex, x, y, w, h):
    shader = gpu.shader.from_builtin('IMAGE')
    batch = batch_for_shader(
        shader, 'TRI_FAN',
        {"pos": ((x, y), (x + w, y), (x + w, y + h), (x, y + h)),
         "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1))})
    gpu.state.blend_set('ALPHA')
    shader.uniform_sampler("image", tex)
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def preview_texture(preview):
    """GPUTexture from an ImagePreview, or None."""
    if preview is None:
        return None
    w, h = preview.image_size
    if not w or not h:
        return None
    pixels = preview.image_pixels_float[:]
    if len(pixels) != w * h * 4:
        return None
    buf = gpu.types.Buffer('FLOAT', w * h * 4, pixels)
    return gpu.types.GPUTexture((w, h), format='RGBA16F', data=buf)

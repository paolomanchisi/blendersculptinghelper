# Sculpt Helper

A Blender 5.x extension that makes Sculpt Mode faster: hold keys for masking and
isolating, quick panels, and helper tools that stock Blender lacks.

Status: **step 1 of 4** (foundation, hold keys, Mask/Hide panel). See the plan
below.

## Install

1. Build the zip: `python build.py` (creates `dist/sculpt_helper-<version>.zip`).
   Blender's own builder works too: `blender --command extension build --source-dir sculpt_helper`.
2. In Blender: *Edit > Preferences > Get Extensions > ∨ > Install from Disk…*
   and pick the zip.

## Shortcuts (Sculpt Mode)

All of them can be rebound in *Preferences > Add-ons > Sculpt Helper*. **F1**
shows the current list in the viewport.

| Key | Action |
| --- | --- |
| **C** (hold) | Mask brush while held, previous brush comes back on release. Drag on mesh paints mask, **Ctrl**+drag removes it. Click on mesh blurs the mask, **Ctrl**+click sharpens it. Click on background inverts the mask, drag on background clears it. |
| **Shift+C** (hold) | Isolate. Drag a box / lasso / line to show only that area (**Ctrl** on release hides it instead). **Tab** or the mouse wheel changes the shape. Click a face set to show only it, click again to show all. Click the background to show everything. |
| **F1** | Shortcut list. |

C and Shift+C replace Blender's default Clay Strips and Crease Polish keys
while the add-on is enabled; the preferences show which default bindings are
overridden.

The sidebar (**N**) gets a *Sculpt Helper* tab with a Mask / Hide panel:
invert, clear, blur, sharpen, grow and shrink the mask; show all, invert,
hide/show masked, grow and shrink visibility.

## Plan

1. **Foundation and hold keys** (this release).
2. **Menus and panels**: native pie menus (Q brushes, A mask, Shift+W hide,
   Alt+W face sets, Z display/mirror/Dyntopo/Multires, S panels) and sidebar
   panels for Brush, Mask/Hide, View/Mode, Deform, Face Sets, Vertex Color,
   Material, Multires, Layers, Extract, Remesh and Boolean. A custom-drawn
   brush wheel and floating panels come after the native version.
3. **Sculpt helpers**: Depth Limit, Gravity, Morph, Copy Stamp, named masks
   (add / subtract / intersect), thickness-protect auto-mask.
4. **Advanced**: pivot bend and twist, sculpt layers, shape transfer after
   remesh, boolean layers.

## Testing

`tests/test_headless.py` checks registration, keymap and brush switching. Run
it with `blender -b --python tests/test_headless.py` or with the `bpy` module
from PyPI (`pip install bpy==5.2.3`, Python 3.13).

Interactive behaviour needs a real viewport. Manual checklist:

- [ ] Hold C, drag on mesh: mask is painted; release C: previous brush is back.
- [ ] Hold C, Ctrl+drag: mask is removed.
- [ ] Hold C, click mesh: mask edges blur; Ctrl+click sharpens.
- [ ] Hold C, click background: mask inverts; drag background: mask clears.
- [ ] Hold Shift+C, drag box: only the boxed area stays visible.
- [ ] Hold Shift+C, Tab to Lasso / Line, drag: same with those shapes.
- [ ] Hold Shift+C, click a face set: it is isolated; click background: all shown.
- [ ] F1 lists the shortcuts; rebinding in Preferences updates the list.

## License

GPL-3.0-or-later.

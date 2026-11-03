# Sculpt Helper

A Blender 5.x extension that makes Sculpt Mode faster: hold keys for masking and
isolating, quick panels, and helper tools that stock Blender lacks.

Status: **step 3 of 4** (hold keys, pie menus, sidebar panels, sculpt helpers). See the plan
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
| **Q** | Brush pie. Seven favourite brushes get a slot; the bottom slot opens the full brush browser and lists any extra favourites. Edit the list in Preferences. |
| **A** | Mask pie: invert, clear, fill, blur, sharpen, grow, shrink, contrast, from cavity. |
| **Shift+W** | Hide / Show pie: show all, invert, hide / show masked, grow / shrink visible, hide tools. |
| **Alt+W** | Face Sets pie: from mask / visible, auto create, new colours, Draw Face Sets brush. |
| **Z** | View / Mode popup: mirror, display overlays, Dyntopo and Multires in one place. |
| **S** | Choose which sidebar panels are shown. |
| **F1** | Shortcut list. |

These replace some Blender defaults in Sculpt Mode while the add-on is enabled
(C Clay Strips, Shift+C Crease Polish, S Smooth, Q Quick Favourites, Z shading
pie, A / Alt+W Blender's own mask and face set pies). The preferences show
every default binding that is overridden, and any key can be changed there.

## Sidebar panels (N > Sculpt Helper)

Each panel has a **?** button explaining it, and **S** hides the ones you
don't need.

| Panel | Contents |
| --- | --- |
| Brush | Brush picker, radius and strength with pressure toggles, Texture / Stroke / Falloff popovers, auto-masking toggles. |
| Mask / Hide | Mask invert / clear / blur / sharpen / grow / shrink; show all, invert, hide / show masked, grow / shrink visible; hold-isolate shape. |
| View / Mode | Mirror X / Y / Z and Symmetrize; mask, face set and wireframe overlays; Dyntopo toggle, detail settings and flood fill. |
| Deform | Mesh filters with strength and iterations: smooth, surface smooth, inflate / deflate, expand / shrink, sphere, random, sharpen, enhance, relax. |
| Face Sets | Create from mask / visible, auto create, new colours, overlay opacity, Edit Face Set tool. |
| Vertex Color | Colour wheel, primary / secondary colour, palette swatches, Paint brush, fill. |
| Material | MatCap / Studio / Flat lighting, MatCap picker and flip, object colour, cavity. |
| Multires | Subdivide (smooth / simple / linear, adds the modifier if needed), level − / + with linked levels, delete higher, apply base. |
| Extract | Extract or slice the masked area, extract a face set. |
| Remesh | Voxel size and options, Voxel Remesh, QuadriFlow. |

## Sculpt helpers

| Tool | Where | What it does |
| --- | --- | --- |
| Thickness Protect | Brush > Auto-Masking | Front faces only plus occlusion masking, so strokes don't reach through thin parts. |
| Depth Limit | Brush > Depth Limit | Record Shape, then nothing can rise more than Max Height or sink more than Max Depth from it. Auto applies it after every stroke; Apply Now does it once. |
| Gravity | Brush > Gravity | Gravity strength, aimed at the screen bottom, into the screen, world down, or a dragged direction. |
| Save / Load masks | Mask / Hide > Save / Load | Named masks stored on the mesh; load, add, subtract or intersect them with the current mask. |
| Morph | Deform > Morph | Record Shape, sculpt, mask where you want the old shape back, press Morph Masked (or Morph Unmasked). |
| Copy Stamp | Deform > Copy Stamp | Click to sample the surface detail under the brush, click elsewhere to stamp it (Shift+click resamples). Detail Size decides how large a feature counts as detail; Replace Detail swaps the target's own detail for the copy. |
| Material by mask | Material | Assign the active material slot to the masked faces, or mask the faces using it. |
| Sculpt Together | View / Mode > Sculpt Together | Select several meshes and Combine: copies are joined into one object (one face set each) and the originals hidden. Split Back writes each part into its original object, keeping name, transform, modifiers and materials. |

Depth Limit, Morph, Copy Stamp, saved masks and material by mask edit vertex
data directly, so they briefly leave Sculpt Mode and come back (each use is one
undo step). Like the reference add-on, they don't work with Dyntopo on, a
Multires modifier, or shape keys; the panel says so when that's the case.
Sculpt Together doesn't keep vertex groups, and it needs topology to stay
per-object (voxel remesh merges the parts).

## Plan

1. **Foundation and hold keys** (done).
2. **Menus and panels** (done, native UI): native pie menus (Q brushes, A mask, Shift+W hide,
   Alt+W face sets, Z display/mirror/Dyntopo/Multires, S panels) and sidebar
   panels for Brush, Mask/Hide, View/Mode, Deform, Face Sets, Vertex Color,
   Material, Multires, Layers, Extract, Remesh and Boolean. A custom-drawn
   brush wheel and floating panels come after the native version.
3. **Sculpt helpers** (done): Depth Limit, Gravity, Morph, Copy Stamp, named masks
   (add / subtract / intersect), thickness-protect auto-mask, material by
   mask, sculpt several objects together.
4. **Advanced**: pivot bend and twist, sculpt layers, shape transfer after
   remesh, boolean layers.

## Testing

`tests/test_headless.py` checks registration, keymap, brush switching and the
Multires helpers. `tests/test_tools.py` checks the sculpt helpers on real mesh
data (mask combine modes, Morph, Depth Limit, Copy Stamp, material by mask,
Sculpt Together round trip). `tests/test_ui_names.py` draws every panel, pie and popup into
a recording layout and fails on any property, operator argument, panel or menu
name this Blender version doesn't have. Run them with
`blender -b --python tests/<file>` or with the `bpy` module from PyPI
(`pip install bpy==5.2.3`, Python 3.13).

Interactive behaviour needs a real viewport. Manual checklist:

- [ ] Hold C, drag on mesh: mask is painted; release C: previous brush is back.
- [ ] Hold C, Ctrl+drag: mask is removed.
- [ ] Hold C, click mesh: mask edges blur; Ctrl+click sharpens.
- [ ] Hold C, click background: mask inverts; drag background: mask clears.
- [ ] Hold Shift+C, drag box: only the boxed area stays visible.
- [ ] Hold Shift+C, Tab to Lasso / Line, drag: same with those shapes.
- [ ] Hold Shift+C, click a face set: it is isolated; click background: all shown.
- [ ] F1 lists the shortcuts; rebinding in Preferences updates the list.
- [ ] Q, A, Shift+W, Alt+W open their pies and each entry works.
- [ ] Z opens the View / Mode popup; S hides and shows sidebar panels.
- [ ] Every sidebar panel draws, and its ? button shows help.
- [ ] Deform buttons change the mesh; masked areas stay still.
- [ ] Multires Subdivide on a fresh mesh adds the modifier; level − / + work.
- [ ] Depth Limit with Auto on: a heavy Clay stroke stops at Max Height.
- [ ] Gravity Screen ↓ / Into Screen / Drag Direction change how strokes sag.
- [ ] Copy Stamp: sample a detailed area, stamp it on a smooth one.
- [ ] Sculpt Together: combine two meshes, sculpt across both, split back.

## License

GPL-3.0-or-later.
